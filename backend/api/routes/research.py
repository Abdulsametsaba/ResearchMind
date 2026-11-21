"""
==============================================================================
Görevi: Araştırma İşlemleri REST API Endpoint'leri
==============================================================================
Endpoint'ler:
  POST /api/research                      → Yeni araştırma başlat 
  GET  /api/research                      → Tüm araştırmaları listele (DB)
  GET  /api/research/memory/search        → Semantik hafıza araması
  GET  /api/research/{id}                 → Durum sorgula
  POST /api/research/{id}/cancel          → Çalışan araştırmayı iptal et
  GET  /api/research/{id}/report          → Raporu getir
  GET  /api/research/{id}/metrics         → Kalite metrikleri

Mimari Notlar:
  - asyncio.create_task() → iptal edilebilir arka plan görevi
  - run_in_executor()     → LangGraph thread pool'da, event loop bloklanmaz
  - araştırma bitince Gemini embedding'leri üretilip pgvector'a kaydedilir
  - POST /api/research → Scope Gate değerlendirmesi → IN_SCOPE ise pipeline
==============================================================================
"""

import asyncio
import uuid
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas import (
    ResearchRequest,
    ResearchJobResponse,
    ResearchStatusResponse,
    CancelResearchResponse,
    SemanticSearchResponse,
    SemanticPaperResult,
    SemanticWebResult,
    ReportResponse,
    ReportSectionSummary,
    ClaimVerificationSummary,
    EvaluationMetrics,
    ScopeGateResponse,
    AcademicPaperDetail,
    WebSourceDetail,
)
from core.state import ResearchState
from agents.report_agent import clean_executive_summary
from database.connection import get_db_session
from database import service as db_service
from database.models import ResearchSession
from orchestrator.graph import (
    ResearchCancelled,
    clear_cancellation,
    close_cancellation,
    get_agent_events,
    get_agent_progress,
    get_research_graph,
    register_cancellation,
    request_cancellation,
)
from evaluation.metrics import calculate_research_metrics

from tools.embeddings import (
        generate_embedding, build_paper_text, build_web_source_text, build_query_text
    )

from agents.scope_gate import evaluate_research_scope, ScopeDecision
from fastapi.responses import JSONResponse

logger = logging.getLogger("ResearchMind.API.Research")

router = APIRouter(prefix="/api/research", tags=["Research"])

# ─── Uygulama genelinde paylaşılan state ─────────────────────────────────────

# Çalışan asyncio.Task'larını tutan sözlük {session_id → Task}
_running_tasks: dict[str, asyncio.Task] = {}

# Aktif işlem sürerken status ve metrik yanıtları için geçici state cache'i
_active_states: dict[str, dict] = {}

# LangGraph'ın senkron graph.invoke() çağrısını çalıştıran thread pool
# (FastAPI event loop'unu bloklamaz)
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="research-worker")


# ─── Yardımcı Fonksiyonlar ───────────────────────────────────────────────────

async def _generate_and_save_embeddings(
    session_id: str,
    final_state: ResearchState,
) -> None:
    """
    Araştırma tamamlandıktan sonra makale ve web kaynağı
    embedding'lerini Gemini text-embedding-004 ile üretir ve pgvector'a kaydeder.

    Hata toleranslı: Embedding hatası araştırmanın durumunu etkilemez.
    Thread pool'da (run_in_executor) çalıştırılır — Gemini API senkron çağrıdır.
    """

    papers      = final_state.get("academic_sources", [])
    web_sources = final_state.get("web_sources", [])

    if not papers and not web_sources:
        return

    loop = asyncio.get_event_loop()

    try:
        # ── Makale Embedding'leri ──────────────────────────────────────────
        paper_embeddings: dict = {}
        for paper in papers:
            text = build_paper_text(paper.title, paper.abstract)
            # Gemini API senkron → thread'de çalıştır
            embedding = await loop.run_in_executor(
                _executor, generate_embedding, text
            )
            if embedding:
                paper_embeddings[paper.id] = embedding

        # ── Web Kaynağı Embedding'leri ────────────────────────────────────
        web_embeddings: dict = {}
        for src in web_sources:
            text = build_web_source_text(src.title, src.snippet)
            embedding = await loop.run_in_executor(
                _executor, generate_embedding, text
            )
            if embedding:
                web_embeddings[src.url] = embedding

        # ── DB'ye Kaydet ──────────────────────────────────────────────────
        async for db in get_db_session():
            if paper_embeddings:
                await db_service.save_paper_embeddings(db, session_id, paper_embeddings)
            if web_embeddings:
                await db_service.save_web_source_embeddings(db, session_id, web_embeddings)

        logger.info(
            f"[{session_id[:8]}] Faz-6: {len(paper_embeddings)} makale + "
            f"{len(web_embeddings)} web kaynağı embedding'i pgvector'a kaydedildi."
        )

    except Exception as exc:
        logger.warning(
            f"[{session_id[:8]}] Embedding üretimi/kaydı başarısız (araştırma etkilenmez): {exc}"
        )


def _build_result_summary(session_id: str, final_state: ResearchState) -> dict:
    papers = final_state.get("academic_sources", [])
    web_sources = final_state.get("web_sources", [])
    verifications = final_state.get("claim_verifications", [])
    return {
        "academic_sources_count": len(papers),
        "web_sources_count": len(web_sources),
        "claim_verifications_count": len(verifications),
        "is_research_sufficient": bool(
            final_state.get("is_research_sufficient", False)
        ),
        "audit_log_count": len(final_state.get("audit_logs", [])),
        "metrics": calculate_research_metrics(
            session_id=session_id,
            state=final_state,
        ).model_dump(mode="json"),
    }


async def _persist_research_results(
    session_id: str,
    final_state: ResearchState,
) -> None:
    """
    Tamamlanmış araştırma sonuçlarını PostgreSQL'e kaydeder.
    FastAPI'nin event loop'unda async olarak çalışır — asyncpg ile tam uyumlu.

    Kayıt tamamlandıktan sonra Gemini text-embedding-004 ile her makale
    ve web kaynağı için embedding üretilir ve pgvector'a kaydedilir.
    """
    async for db in get_db_session():
        try:
            papers        = final_state.get("academic_sources", [])
            web_sources   = final_state.get("web_sources", [])
            verifications = final_state.get("claim_verifications", [])
            report        = final_state.get("final_report")
            iter_count    = final_state.get("iteration_count", 0)
            result_summary = _build_result_summary(session_id, final_state)
            result_summary["agent_statuses"] = get_agent_progress(session_id)
            result_summary["agent_events"] = get_agent_events(session_id)

            if papers:
                await db_service.save_academic_papers(db, session_id, papers)
            if web_sources:
                await db_service.save_web_sources(db, session_id, web_sources)
            if verifications:
                await db_service.save_claim_verifications(db, session_id, verifications)
            if report:
                await db_service.save_report(
                    db,
                    session_id,
                    report,
                    additional_metadata={"bibliography": report.bibliography},
                )

            await db_service.update_session_status(
                db,
                session_id,
                "completed",
                iter_count,
                result_summary=result_summary,
            )
            logger.info(f"[{session_id[:8]}] Tüm sonuçlar DB'ye kaydedildi.")

        except Exception as e:
            logger.error(f"[{session_id[:8]}] DB kayıt hatası: {e}")
            try:
                await db_service.update_session_status(db, session_id, "failed")
            except Exception:
                pass
            return  # Embedding aşamasına geçme

    # ── Embedding üretimi (ayrı DB session'ında) ─────────────────────
    # Kayıt başarılıysa asenkron olarak embedding'leri üret ve kaydet.
    # Embedding hatası araştırmayı başarısız yapmaz — sadece loglanır.
    await _generate_and_save_embeddings(session_id, final_state)


async def _run_research_background(
    session_id: str,
    query: str,
    guidance: Optional[str],
) -> None:
    """
    Araştırma iş akışını arka planda async olarak yürüten görev.

    Yaşam döngüsü:
      1. LangGraph graph.invoke() → thread pool'da çalıştırılır (non-blocking)
      2. CancelledError yakalanırsa → DB'de 'cancelled' olarak işaretlenir
      3. Başarı durumunda → tüm sonuçlar DB'ye yazılır
      4. Hata durumunda  → DB'de 'failed' olarak işaretlenir
      5. Her durumda     → _running_tasks sözlüğünden silinir
    """
    logger.info(f"[{session_id[:8]}] Araştırma başlatıldı: '{query[:60]}...'")

    initial_state: ResearchState = {
        "research_query": query,
        "user_guidance": guidance,
        "sub_questions": [],
        "current_subquestion_index": 0,
        "academic_sources": [],
        "web_sources": [],
        "analysis_summary": "",
        "comparative_data": {},
        "claim_verifications": [],
        "iteration_count": 0,
        "missing_information_queries": [],
        "is_research_sufficient": False,
        "final_report": None,
        "research_narrative": None,
        "audit_logs": [f"[API] Oturum: {session_id[:8]}"],
    }

    try:
        graph  = get_research_graph()
        config = {"configurable": {"thread_id": session_id}}
        loop   = asyncio.get_event_loop()

        # Synchronous nodes are allowed to finish; cancellation is checked at
        # each graph-node boundary to avoid abandoning an active worker thread.
        final_state = await loop.run_in_executor(
            _executor,
            lambda: graph.invoke(initial_state, config=config),
        )

        if close_cancellation(session_id):
            raise ResearchCancelled()

        # State'i cache'e yaz (metrik sorguları için)
        _active_states[session_id] = {
            "final_state": final_state,
            "completed_at": datetime.now(timezone.utc),
        }

        # DB'ye kaydet — aynı event loop, asyncio.run() YOK
        await _persist_research_results(session_id, final_state)
        logger.info(f"[{session_id[:8]}] Araştırma tamamlandı ve DB'ye kaydedildi.")

    except ResearchCancelled:
        close_cancellation(session_id)
        logger.info(f"[{session_id[:8]}] Araştırma kullanıcı isteğiyle iptal edildi.")
        try:
            async for db in get_db_session():
                await db_service.update_session_status(db, session_id, "cancelled")
        except Exception as db_err:
            logger.error(f"[{session_id[:8]}] İptal durumu DB'ye yazılamadı: {db_err}")

    except asyncio.CancelledError:
        logger.info(f"[{session_id[:8]}] Araştırma görevi uygulama kapanışıyla iptal edildi.")
        try:
            async for db in get_db_session():
                await db_service.update_session_status(db, session_id, "cancelled")
        except Exception as db_err:
            logger.error(f"[{session_id[:8]}] İptal durumu DB'ye yazılamadı: {db_err}")

    except Exception as e:
        cancelled = close_cancellation(session_id)
        terminal_status = "cancelled" if cancelled else "failed"
        if cancelled:
            logger.info(f"[{session_id[:8]}] Araştırma hata sırasında iptal isteği aldı.")
        else:
            logger.error(f"[{session_id[:8]}] Araştırma hatası: {e}", exc_info=True)
        try:
            async for db in get_db_session():
                await db_service.update_session_status(db, session_id, terminal_status)
        except Exception as db_err:
            logger.error(f"[{session_id[:8]}] Hata durumu DB'ye yazılamadı: {db_err}")

    finally:
        # Her durumda izleme listesinden kaldır
        _running_tasks.pop(session_id, None)
        clear_cancellation(session_id)
        _active_states.pop(session_id, None)
        logger.debug(f"[{session_id[:8]}] Görev izleme listesinden kaldırıldı.")


# ─── Endpoint'ler ─────────────────────────────────────────────────────────────

@router.post(
    "",
    summary="Yeni Araştırma Başlat",
    description=(
        "Verilen araştırma sorusu için çok ajanlı derin araştırma sürecini başlatır. "
        "İşlem arka planda yürütülür; dönen `session_id` ile durum takibi yapılabilir. "
        "Tamamlanan araştırmalar kalıcı olarak PostgreSQL'e kaydedilir.\n\n"
        "Research Scope Gate:** İstek önce kapsam değerlendirmesinden geçer. "
        "Araştırma görevi olmayan veya hedefi belirsiz istekler pipeline'a alınmaz; "
        "DB'ye yazılmaz. Olası HTTP yanıtları:\n"
        "- **202**: `IN_SCOPE` → araştırma başlatıldı (`ResearchJobResponse`).\n"
        "- **200**: `OUT_OF_SCOPE` veya `NEEDS_CLARIFICATION` → pipeline başlamadı (`ScopeGateResponse`)."
    ),
)
async def start_research(
    request: ResearchRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Yeni araştırma oturumu oluşturur, DB'ye kaydeder ve arka planda başlatır.

    Research Scope Gate entegrasyonu:
      1. Gate senkron olarak değerlendirir (thread pool'da — LLM çağrısı bloklar).
      2. OUT_OF_SCOPE / NEEDS_CLARIFICATION → 200 + ScopeGateResponse (DB yazılmaz).
      3. IN_SCOPE → mevcut pipeline devam eder (202 + ResearchJobResponse).

    asyncio.create_task() kullanılır (BackgroundTasks yerine) böylece dönen
    Task nesnesi _running_tasks üzerinden iptal edilebilir.
    """

    # LLM senkron çağrıdır — event loop'u bloklamaz diye thread pool'da çalıştır.
    loop = asyncio.get_event_loop()
    gate_result = await loop.run_in_executor(
        _executor,
        lambda: evaluate_research_scope(request.query, request.guidance),
    )

    if gate_result.decision != ScopeDecision.IN_SCOPE:
        # Pipeline başlamaz, DB'ye hiçbir şey yazılmaz.
        status_label = (
            "out_of_scope"
            if gate_result.decision == ScopeDecision.OUT_OF_SCOPE
            else "needs_clarification"
        )
        hint = None
        if gate_result.decision == ScopeDecision.OUT_OF_SCOPE:
            hint = (
                "İpucu: Konuyu değiştirmek zorunda değilsiniz — isteğinizi "
                "analitik bir araştırma sorusuna dönüştürmeyi deneyin. "
                "Örnek: 'X kimdir?' yerine 'X'in kariyer performansını "
                "istatistiksel kaynaklarla analiz et.' şeklinde sorun."
            )
        logger.info(
            f"[ScopeGate] İstek reddedildi ({gate_result.decision.value}): "
            f"'{request.query[:60]}...'"
        )
        response_body = ScopeGateResponse(
            status=status_label,
            message=gate_result.user_message,
            hint=hint,
        )
        return JSONResponse(
            status_code=200,
            content=response_body.model_dump(),
        )

    # ── IN_SCOPE: Mevcut pipeline devam eder ─────────────────────────────────
    session_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc)

    # DB'ye pending → running olarak kaydet
    await db_service.create_session(db, session_id, request.query)
    await db_service.update_session_status(db, session_id, "running")

    register_cancellation(session_id)
    task = asyncio.create_task(
        _run_research_background(session_id, request.query, request.guidance),
        name=f"research-{session_id[:8]}",
    )
    _running_tasks[session_id] = task

    logger.info(f"[{session_id[:8]}] Araştırma kuyruğa alındı: '{request.query[:60]}...'")

    from fastapi.responses import JSONResponse as _JSONResponse
    response_body = ResearchJobResponse(
        session_id=session_id,
        status="running",
        message=(
            f"Araştırma başlatıldı. İptal için POST /api/research/{session_id}/cancel, "
            f"durum için GET /api/research/{session_id} adresini kullanın."
        ),
        created_at=created_at,
    )
    return _JSONResponse(
        status_code=202,
        content=response_body.model_dump(mode="json"),
    )


@router.post(
    "/{session_id}/cancel",
    response_model=CancelResearchResponse,
    status_code=200,
    summary="Çalışan Araştırmayı İptal Et",
    description=(
        "Belirtilen session_id'ye ait aktif araştırmayı iptal eder. "
        "Devam eden senkron ajan adımı tamamlanınca yeni adımlar durdurulur. "
        "Bu sırada durum 'cancelling', durduktan sonra 'cancelled' olur."
    ),
)
async def cancel_research(
    session_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> CancelResearchResponse:
    """
    Çalışan araştırma görevini iptal eder.

    The active synchronous agent step is allowed to finish; later steps are
    stopped by the graph's cancellation checks.
    """
    # DB'den oturumu kontrol et
    session: Optional[ResearchSession] = await db_service.get_session(db, session_id)
    if not session:
        raise HTTPException(
            status_code=404,
            detail=f"Araştırma oturumu bulunamadı: {session_id}",
        )

    # Zaten sonuçlanmış durumlar
    terminal_statuses = {"completed", "failed", "cancelled"}
    if session.status in terminal_statuses:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Bu araştırma zaten sonuçlandı (durum: '{session.status}'). "
                f"Yalnızca 'running' durumundaki araştırmalar iptal edilebilir."
            ),
        )

    # Aktif görev var mı?
    task = _running_tasks.get(session_id)
    if task is None or task.done():
        await db_service.update_session_status(db, session_id, "cancelled")
        logger.warning(
            f"[{session_id[:8]}] Aktif görev bulunamadı ama DB 'cancelled' olarak işaretlendi."
        )
    else:
        if session.status != "cancelling":
            if not request_cancellation(session_id):
                raise HTTPException(
                    status_code=409,
                    detail="Araştırma sonlandırma aşamasına geçtiği için artık iptal edilemiyor.",
                )
            await db_service.update_session_status(db, session_id, "cancelling")
        logger.info(f"[{session_id[:8]}] İptal isteği kaydedildi.")

    cancelled_at = datetime.now(timezone.utc)
    cancellation_pending = task is not None and not task.done()
    return CancelResearchResponse(
        session_id=session_id,
        status="cancelling" if cancellation_pending else "cancelled",
        message=(
            "Araştırma, devam eden ajan adımı tamamlanınca durdurulacak."
            if cancellation_pending
            else "Araştırma iptal edildi."
        ),
        cancelled_at=cancelled_at,
    )


@router.get(
    "",
    summary="Tüm Araştırmaları Listele",
    description="PostgreSQL'deki tüm araştırma oturumlarını listeler.",
)
async def list_research_sessions(
    status: Optional[str] = Query(
        default=None,
        description="Filtre: pending / running / cancelling / completed / failed / cancelled",
    ),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db_session),
) -> List[dict]:
    """DB'deki tüm araştırma oturumlarını listeler."""
    sessions: List[ResearchSession] = await db_service.list_sessions(db, status, limit)
    return [
        {
            "session_id":      s.id,
            "query":           s.query[:100],
            "status":          s.status,
            "is_active":       s.id in _running_tasks,  # Gerçek zamanlı aktiflik bilgisi
            "iteration_count": s.iteration_count,
            "created_at":      s.created_at.isoformat() if s.created_at else None,
            "updated_at":      s.updated_at.isoformat() if s.updated_at else None,
        }
        for s in sessions
    ]


@router.get(
    "/memory/search",
    response_model=SemanticSearchResponse,
    summary="Semantik Hafıza Araması (Faz-6)",
    description=(
        "Verilen sorgu için pgvector cosine benzerliği kullanarak geçmiş "
        "araştırmalardaki benzer akademik makaleleri ve web kaynaklarını arar. "
        "Yalnızca embedding'i üretilmiş (tamamlanmış) araştırmalarda çalışır."
    ),
)
async def search_semantic_memory(
    q: str = Query(description="Aranacak soru veya konu metni", min_length=5),
    min_similarity: float = Query(
        default=0.75,
        ge=0.5,
        le=0.99,
        description="Minimum cosine benzerlik eşiği (0.5–0.99)",
    ),
    limit: int = Query(default=5, ge=1, le=20),
    db: AsyncSession = Depends(get_db_session),
) -> SemanticSearchResponse:
    """
    pgvector üzerinde semantik arama yapar ve benzer kaynakları döner.

    Bu endpoint kullanıcının araştırma başlatmadan önce mevcut hafızada
    ne olduğunu keşfetmesini sağlar.
    """

    loop = asyncio.get_event_loop()
    embedding = await loop.run_in_executor(
        _executor, generate_embedding, build_query_text(q)
    )

    if embedding is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "Embedding üretilemedi. Gemini API anahtarının yapılandırıldığından "
                "emin olun (GEMINI_API_KEY)."
            ),
        )

    similar_papers = await db_service.search_similar_papers(
        db=db,
        query_embedding=embedding,
        exclude_session_id=None,
        limit=limit,
        min_similarity=min_similarity,
    )

    similar_sources = await db_service.search_similar_web_sources(
        db=db,
        query_embedding=embedding,
        exclude_session_id=None,
        limit=limit,
        min_similarity=min_similarity,
    )

    paper_results = [
        SemanticPaperResult(
            paper_id=p.paper_id,
            title=p.title,
            authors=p.authors or [],
            published_year=p.published_year,
            abstract_preview=p.abstract[:300],
            url=p.url,
            relevance_score=p.relevance_score,
            source_session_id=p.session_id,
        )
        for p in similar_papers
    ]

    web_results = [
        SemanticWebResult(
            url=s.url,
            title=s.title,
            snippet_preview=s.snippet[:200],
            relevance_score=s.relevance_score,
            source_session_id=s.session_id,
        )
        for s in similar_sources
    ]

    return SemanticSearchResponse(
        query=q,
        similarity_threshold=min_similarity,
        papers=paper_results,
        web_sources=web_results,
        total_found=len(paper_results) + len(web_results),
    )


@router.get(
    "/{session_id}",
    response_model=ResearchStatusResponse,
    summary="Araştırma Durumunu Sorgula",
    description="Belirtilen session_id'ye ait araştırmanın durumunu DB'den döner.",
)
async def get_research_status(
    session_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> ResearchStatusResponse:
    """Araştırma oturumunun mevcut durumunu DB'den sorgular."""
    session: Optional[ResearchSession] = await db_service.get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Oturum bulunamadı: {session_id}")

    db_report = await db_service.get_report(db, session_id)
    result_summary = session.result_summary or {}
    cached = _active_states.get(session_id, {})
    final_state = cached.get("final_state")

    if final_state:
        academic_count = len(final_state.get("academic_sources", []))
        web_count = len(final_state.get("web_sources", []))
        claim_count = len(final_state.get("claim_verifications", []))
        is_sufficient = final_state.get("is_research_sufficient", False)
        audit_count = len(final_state.get("audit_logs", []))
    else:
        academic_count = result_summary.get("academic_sources_count")
        web_count = result_summary.get("web_sources_count")
        claim_count = result_summary.get("claim_verifications_count")
        is_sufficient = result_summary.get("is_research_sufficient", False)
        audit_count = result_summary.get("audit_log_count", 0)

        if any(value is None for value in (academic_count, web_count, claim_count)):
            academic_count = len(await db_service.get_papers_by_session(db, session_id))
            web_count = len(await db_service.get_web_sources_by_session(db, session_id))
            claim_count = len(await db_service.get_verifications_by_session(db, session_id))

        academic_count = academic_count or 0
        web_count = web_count or 0
        claim_count = claim_count or 0
        is_sufficient = bool(is_sufficient)
        audit_count = audit_count or 0

    if session.status in {"running", "cancelling"}:
        agent_statuses = get_agent_progress(session_id)
        agent_events = get_agent_events(session_id)
    else:
        agent_statuses = result_summary.get("agent_statuses") or (
            {key: "completed" for key in get_agent_progress(session_id)}
            if session.status == "completed"
            else get_agent_progress(session_id)
        )
        agent_events = result_summary.get("agent_events", [])

    return ResearchStatusResponse(
        session_id=session_id,
        status=session.status,
        query=session.query,
        iteration_count=session.iteration_count,
        academic_sources_count=academic_count,
        web_sources_count=web_count,
        claim_verifications_count=claim_count,
        is_research_sufficient=is_sufficient,
        created_at=session.created_at,
        completed_at=session.updated_at if session.status in {"completed", "cancelled", "failed"} else None,
        audit_log_count=audit_count,
        has_report=bool(db_report),
        agent_statuses=agent_statuses,
        agent_events=agent_events,
    )


@router.get(
    "/{session_id}/report",
    response_model=ReportResponse,
    summary="Araştırma Raporunu Getir",
    description="Tamamlanmış araştırmanın raporunu DB'den getirir.",
)
async def get_research_report(
    session_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> ReportResponse:
    """Tamamlanmış araştırmanın nihai raporunu DB'den getirir."""
    session = await db_service.get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Oturum bulunamadı: {session_id}")

    if session.status != "completed":
        raise HTTPException(
            status_code=409,
            detail=(
                f"Rapor yalnızca tamamlanmış araştırmalar için alınabilir. "
                f"Mevcut durum: '{session.status}'."
            ),
        )

    db_report = await db_service.get_report(db, session_id)
    if not db_report:
        raise HTTPException(status_code=404, detail="Rapor henüz DB'ye kaydedilmedi.")

    # DB'den kaynakları ve doğrulamaları yükle (güvenli fallback koruması ile)
    try:
        if hasattr(db_service, "get_papers_by_session"):
            db_papers = await db_service.get_papers_by_session(db, session_id)
        else:
            try:
                from database.models import AcademicPaperModel
            except ImportError:
                from database.models import AcademicPaperModel
            from sqlalchemy import select
            res = await db.execute(select(AcademicPaperModel).where(AcademicPaperModel.session_id == session_id))
            db_papers = list(res.scalars().all())
    except Exception as e:
        logger.warning(f"Makaleler DB'den çekilemedi: {e}")
        db_papers = []

    try:
        if hasattr(db_service, "get_web_sources_by_session"):
            db_web = await db_service.get_web_sources_by_session(db, session_id)
        else:
            try:
                from database.models import WebSourceModel
            except ImportError:
                from database.models import WebSourceModel
            from sqlalchemy import select
            res = await db.execute(select(WebSourceModel).where(WebSourceModel.session_id == session_id))
            db_web = list(res.scalars().all())
    except Exception as e:
        logger.warning(f"Web kaynakları DB'den çekilemedi: {e}")
        db_web = []

    try:
        if hasattr(db_service, "get_verifications_by_session"):
            db_claims = await db_service.get_verifications_by_session(db, session_id)
        else:
            try:
                from database.models import ClaimVerificationModel
            except ImportError:
                from database.models import ClaimVerificationModel
            from sqlalchemy import select
            res = await db.execute(select(ClaimVerificationModel).where(ClaimVerificationModel.session_id == session_id))
            db_claims = list(res.scalars().all())
    except Exception as e:
        logger.warning(f"Doğrulamalar DB'den çekilemedi: {e}")
        db_claims = []

    cached = _active_states.get(session_id, {})
    final_state = cached.get("final_state", {})
    final_report = final_state.get("final_report")

    cleaned_exec_summary = clean_executive_summary(db_report.executive_summary)

    sections: List[ReportSectionSummary] = []
    comp_md = None
    verif_md = None
    limitations = "Akademik literatür analizi tamamlanmıştır."

    if final_report:
        for sec in getattr(final_report, "sections", []):
            h = sec.get("heading") if isinstance(sec, dict) else getattr(sec, "heading", "")
            c = sec.get("content") if isinstance(sec, dict) else getattr(sec, "content", "")
            sections.append(
                ReportSectionSummary(
                    heading=h,
                    content=c,
                    content_preview=c[:300] + "..." if c else "",
                )
            )
        comp_md = getattr(final_report, "comparative_analysis_markdown", None)
        verif_md = getattr(final_report, "verification_matrix_markdown", None)
        limitations = getattr(final_report, "limitations_and_future_directions", limitations)
    elif db_report.report_markdown:
        # DB'deki tam markdown metninden bölümleri ve tabloları çözümle
        parts = db_report.report_markdown.split("\n## ")
        for part in parts[1:]:
            lines = part.split("\n", 1)
            heading = lines[0].strip()
            content = lines[1].strip() if len(lines) > 1 else ""
            h_lower = heading.lower()
            if "yönetici özeti" in h_lower:
                continue
            elif "karşılaştırmalı analiz" in h_lower:
                comp_md = content
            elif "doğrulama matrisi" in h_lower:
                verif_md = content
            elif "kısıtlar ve gelecek" in h_lower:
                limitations = content
            elif "kaynakça" in h_lower:
                continue
            else:
                sections.append(
                    ReportSectionSummary(
                        heading=heading,
                        content=content,
                        content_preview=content[:300] + "..." if content else "",
                    )
                )

    # İddia doğrulamaları
    claim_summaries = []
    if db_claims:
        for v in db_claims:
            claim_summaries.append(
                ClaimVerificationSummary(
                    claim_id=v.id[:8] if v.id else "C-1",
                    claim_text=v.claim_text,
                    verification_status=v.verification_status,
                    confidence_score=v.confidence_score,
                    source_reference=v.source_reference,
                    notes=getattr(v, "notes", None),
                )
            )
    else:
        for v in final_state.get("claim_verifications", []):
            claim_summaries.append(
                ClaimVerificationSummary(
                    claim_id=v.claim_id,
                    claim_text=v.claim_text,
                    verification_status=v.verification_status,
                    confidence_score=v.confidence_score,
                    source_reference=v.source_reference,
                    notes=getattr(v, "notes", None),
                )
            )

    # Akademik makale detayları
    paper_details = [
        AcademicPaperDetail(
            paper_id=p.paper_id,
            title=p.title,
            authors=p.authors or [],
            published_year=p.published_year,
            url=p.url,
            pdf_url=p.pdf_url,
            abstract=p.abstract,
            extracted_intel=p.extracted_intel,
            relevance_score=p.relevance_score,
        )
        for p in db_papers
    ]

    # Web kaynağı detayları
    web_details = [
        WebSourceDetail(
            url=w.url,
            title=w.title,
            snippet=w.snippet,
            relevance_score=w.relevance_score,
        )
        for w in db_web
    ]

    bib_list = db_report.report_metadata.get("bibliography", []) if db_report.report_metadata else []

    return ReportResponse(
        session_id=session_id,
        title=db_report.title,
        executive_summary=cleaned_exec_summary,
        sections=sections,
        report_markdown=db_report.report_markdown,
        comparative_analysis_markdown=comp_md,
        verification_matrix_markdown=verif_md,
        limitations_and_future_directions=limitations,
        bibliography=bib_list,
        claim_verifications=claim_summaries,
        academic_papers=paper_details,
        web_sources=web_details,
        total_sources=len(paper_details) + len(web_details),
        created_at=db_report.created_at,
    )


@router.get(
    "/{session_id}/metrics",
    response_model=EvaluationMetrics,
    summary="Araştırma Kalite Metriklerini Hesapla",
)
async def get_research_metrics(
    session_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> EvaluationMetrics:
    """Araştırma kalite değerlendirme metriklerini hesaplar."""
    session = await db_service.get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Oturum bulunamadı: {session_id}")

    if session.status != "completed":
        raise HTTPException(
            status_code=409,
            detail=(
                f"Metrikler yalnızca tamamlanmış araştırmalar için hesaplanabilir. "
                f"Mevcut durum: '{session.status}'."
            ),
        )

    cached = _active_states.get(session_id, {})
    final_state = cached.get("final_state")
    if final_state:
        return calculate_research_metrics(session_id=session_id, state=final_state)

    result_summary = session.result_summary or {}
    stored_metrics = result_summary.get("metrics")
    if stored_metrics:
        return EvaluationMetrics.model_validate(stored_metrics)

    if not result_summary:
        papers = await db_service.get_papers_by_session(db, session_id)
        web_sources = await db_service.get_web_sources_by_session(db, session_id)
        verifications = await db_service.get_verifications_by_session(db, session_id)
        return EvaluationMetrics(
            session_id=session_id,
            research_coverage_score=0.0,
            citation_accuracy_score=0.0,
            source_quality_score=0.0,
            factual_consistency_score=0.0,
            retrieval_recall=0.0,
            research_completion_rate=1.0,
            total_sources=len(papers) + len(web_sources),
            total_claims_verified=sum(
                1 for claim in verifications
                if claim.verification_status == "VERIFIED"
            ),
            iteration_count=session.iteration_count,
            overall_score=0.0,
        )

    return EvaluationMetrics(
        session_id=session_id,
        research_coverage_score=0.0,
        citation_accuracy_score=0.0,
        source_quality_score=0.0,
        factual_consistency_score=0.0,
        retrieval_recall=0.0,
        research_completion_rate=1.0,
        total_sources=result_summary.get("academic_sources_count", 0)
        + result_summary.get("web_sources_count", 0),
        total_claims_verified=0,
        iteration_count=session.iteration_count,
        overall_score=0.0,
    )
