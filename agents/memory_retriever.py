"""
==============================================================================
Dosya: researchmind/agents/memory_retriever.py
Görevi: Semantic Memory Retriever Agent (Faz-6: pgvector Hafıza Katmanı)
==============================================================================
Bu ajan, yeni bir araştırmada Paper Researcher çalışmadan önce devreye girer
ve PostgreSQL/pgvector üzerindeki geçmiş araştırma verilerini sorgular.

ÇALIŞMA MANTIĞI:
  1. Planner'ın ürettiği sub_questions alınır.
  2. Her alt soru için Gemini text-embedding-004 ile 768-boyutlu vektör üretilir.
  3. academic_papers ve web_sources tablolarında cosine benzerliği araması yapılır.
  4. Benzerlik eşiğini (varsayılan: 0.78) geçen geçmiş kaynaklar state'e eklenir.
  5. Paper Researcher zaten gelen kaynakları seen_ids ile atlar → tekrar indirilmez.

ÖNEMLI MİMARİ NOT:
  Bu ajan LangGraph tarafından thread pool'da (senkron) çağrılır. İçeride
  asyncio.run() ile yeni bir event loop oluşturulur ve taze bir DB engine
  bağlantısı açılır. Bu, FastAPI'nin event loop'uyla çakışmayı önler.
  (FastAPI event loop'u ayrı thread'de çalışır, bu ajan ayrı thread'de)

HATA TOLERANSI:
  - Gemini API yoksa: embedding üretilemez → sessizce atlanır, pipeline devam eder
  - DB bağlantısı yoksa: exception yakalanır → boş sonuç döner, pipeline devam eder
  - Hiç geçmiş veri yoksa: boş liste döner → normal araştırma başlar
==============================================================================
"""

import asyncio
import logging
from typing import List, Optional

from config.settings import get_settings

from core.state import (
    AcademicPaperSource,
    ExtractedPaperIntel,
    WebSource,
    ResearchState,
)
from tools.embeddings import (
    generate_embedding,
    build_query_text,
)

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from database import service as db_service

logger = logging.getLogger("ResearchMind.Agents.MemoryRetriever")


SIMILARITY_THRESHOLD = 0.78
MAX_PAPERS_FROM_MEMORY  = 5   # Hafızadan getirilecek maks. makale
MAX_SOURCES_FROM_MEMORY = 3   # Hafızadan getirilecek maks. web kaynağı


def _db_paper_to_state(paper_model) -> AcademicPaperSource:
    """
    Veritabanı AcademicPaperModel'ini state'te kullanılan
    AcademicPaperSource Pydantic modeline dönüştürür.
    """
    intel = None
    if paper_model.extracted_intel:
        try:
            intel = ExtractedPaperIntel(**paper_model.extracted_intel)
        except Exception:
            intel = None

    return AcademicPaperSource(
        id=paper_model.paper_id,
        title=paper_model.title,
        authors=paper_model.authors or [],
        published_year=paper_model.published_year,
        url=paper_model.url,
        pdf_url=paper_model.pdf_url,
        abstract=paper_model.abstract,
        extracted_intel=intel,
        relevance_score=paper_model.relevance_score or 1.0,
    )


def _db_web_to_state(web_model) -> WebSource:
    """
    Veritabanı WebSourceModel'ini state'te kullanılan
    WebSource Pydantic modeline dönüştürür.
    """
    return WebSource(
        url=web_model.url,
        title=web_model.title,
        snippet=web_model.snippet,
        full_content=None,
        relevance_score=web_model.relevance_score or 1.0,
    )


async def _async_retrieve_from_memory(
    sub_question_texts: List[str],
    research_query: str,
    current_session_id: Optional[str],
) -> dict:
    """
    pgvector üzerinde semantik arama yapan async iç fonksiyon.

    Bu fonksiyon asyncio.run() ile çağrılır; kendi event loop'unda
    taze bir DB bağlantısı açar (FastAPI engine'iyle çakışma olmaz).
    """

    settings = get_settings()

    # Taze engine — bu event loop'a ait, FastAPI engine'inden bağımsız
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
        pool_size=2,
        max_overflow=0,
    )
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    found_papers: List[AcademicPaperSource] = []
    found_sources: List[WebSource] = []
    seen_paper_ids: set = set()
    seen_source_urls: set = set()
    audit_logs: List[str] = []

    try:
        async with async_session() as db:

            # Ana araştırma sorgusu + alt sorular birleştirilir
            all_queries = [research_query] + sub_question_texts

            for query_text in all_queries:
                # 1. Sorgu için embedding üret (senkron, ayrı thread'de zaten)
                embedding = generate_embedding(build_query_text(query_text))
                if embedding is None:
                    logger.debug(f"Embedding üretilemedi, sorgu atlandı: {query_text[:60]}")
                    continue

                # 2. Semantik makale araması
                if len(found_papers) < MAX_PAPERS_FROM_MEMORY:
                    similar_papers = await db_service.search_similar_papers(
                        db=db,
                        query_embedding=embedding,
                        exclude_session_id=current_session_id,
                        limit=MAX_PAPERS_FROM_MEMORY,
                        min_similarity=SIMILARITY_THRESHOLD,
                    )
                    for p in similar_papers:
                        if p.paper_id not in seen_paper_ids:
                            seen_paper_ids.add(p.paper_id)
                            found_papers.append(_db_paper_to_state(p))

                # 3. Semantik web kaynağı araması
                if len(found_sources) < MAX_SOURCES_FROM_MEMORY:
                    similar_sources = await db_service.search_similar_web_sources(
                        db=db,
                        query_embedding=embedding,
                        exclude_session_id=current_session_id,
                        limit=MAX_SOURCES_FROM_MEMORY,
                        min_similarity=SIMILARITY_THRESHOLD,
                    )
                    for s in similar_sources:
                        if s.url not in seen_source_urls:
                            seen_source_urls.add(s.url)
                            found_sources.append(_db_web_to_state(s))

    finally:
        await engine.dispose()

    if found_papers or found_sources:
        audit_logs.append(
            f"[Memory Retriever] Hafızadan {len(found_papers)} makale, "
            f"{len(found_sources)} web kaynağı getirildi "
            f"(eşik: {SIMILARITY_THRESHOLD})."
        )
        logger.info(
            f"Semantic memory: {len(found_papers)} makale + "
            f"{len(found_sources)} web kaynağı hafızadan yüklendi."
        )
    else:
        audit_logs.append(
            "[Memory Retriever] Hafızada yeterli benzerlikte kaynak bulunamadı. "
            "Normal araştırma akışı başlatılıyor."
        )
        logger.info("Semantic memory: eşiği geçen kaynak bulunamadı.")

    return {
        "academic_sources": found_papers,
        "web_sources": found_sources,
        "audit_logs": audit_logs,
    }


def retrieve_from_memory(state: ResearchState) -> dict:
    """
    LangGraph düğümü: Semantic Memory Retriever Agent.

    Planner'ın ürettiği alt sorular ve ana araştırma sorusu için pgvector'da
    semantik arama yapar. Bulunan kaynaklar academic_sources ve web_sources
    state'lerine eklenir; Paper/Web Researcher mükerrer kaynakları atlar.

    Gemini yapılandırılmamışsa veya DB erişimi yoksa sessizce boş döner
    ve normal araştırma akışı başlar.
    """
    sub_questions = state.get("sub_questions", [])
    research_query = state.get("research_query", "")

    # Planner hiç soru üretmemişse geç
    if not sub_questions and not research_query:
        return {"audit_logs": ["[Memory Retriever] Sorgu bulunamadı, atlandı."]}

    sub_texts = [sq.question for sq in sub_questions]

    # Oturum ID'si: audit_logs'tan çıkar (varsa)
    current_session_id: Optional[str] = None
    for log in state.get("audit_logs", []):
        if log.startswith("[API] Oturum: "):
            short_id = log.replace("[API] Oturum: ", "").strip()
            # Kısa ID'den tam ID bulmak mümkün değil — session_id yok geçiyoruz
            # (Sadece kendi session'ımızı exclude etmek için kullanılıyordu)
            break

    # asyncio.run() için coroutine oluştur
    _coro = _async_retrieve_from_memory(
        sub_question_texts=sub_texts,
        research_query=research_query,
        current_session_id=current_session_id,
    )

    try:
        result = asyncio.run(_coro)
        return result
    except RuntimeError as exc:
        # asyncio.run() hali hazırda çalışan bir loop içinden çağrıldı.
        # Bu durum test ortamında oluşabilir. Gerçek çalışmada (thread pool)
        # bu hata oluşmaz. Coroutine'i kapat ve güvenli fallback döndür.
        try:
            _coro.close()  # RuntimeWarning: coroutine was never awaited → önle
        except Exception:
            pass
        logger.warning(
            f"Memory retriever: event loop çakışması ({exc}). "
            "Üretim ortamında bu hata oluşmaz — thread pool'da çalışılmalı."
        )
        return {
            "audit_logs": [
                "[Memory Retriever] Event loop çakışması — atlandı. "
                "Normal araştırma başlatılıyor."
            ]
        }
    except Exception as exc:
        logger.warning(f"Memory retriever genel hata (atlanıyor): {exc}")
        return {
            "audit_logs": [
                f"[Memory Retriever] Hafıza erişimi atlandı (hata: {type(exc).__name__}). "
                "Normal araştırma başlatılıyor."
            ]
        }
