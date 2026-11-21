"""
==============================================================================
Görevi: Veritabanı CRUD Servis Katmanı (Repository Pattern)
==============================================================================
Bu modül, ResearchMind'ın tüm PostgreSQL okuma/yazma işlemlerini tek bir
yerden yönetir. API katmanı (routes/) ve arka plan iş parçacıkları bu
servisi kullanarak veritabanına erişir.

Repository Pattern faydaları:
  - Veritabanı mantığı route'lardan ayrılır (single responsibility)
  - Test etmek için kolayca mock'lanabilir
  - Gelecekte ORM değiştirilirse sadece bu dosya güncellenir

Sağlanan Fonksiyonlar:
  Oturum (Session):
    create_session()       → Yeni araştırma oturumu oluştur
    update_session_status()→ Durumu güncelle (running/completed/failed/cancelled)
    get_session()          → ID ile tek oturum getir
    list_sessions()        → Tüm oturumları listele

  Kaynaklar (Sources):
    save_academic_papers() → Makale listesini DB'ye kaydet
    save_web_sources()     → Web kaynaklarını DB'ye kaydet

  Doğrulama (Claims):
    save_claim_verifications() → Fact-check sonuçlarını kaydet

  Rapor (Report):
    save_report()          → Nihai raporu kaydet
    get_report()           → Session ID ile raporu getir

    Semantic Memory (pgvector):
    save_paper_embeddings()    → Makalelerin embedding vektörlerini kaydet
    save_web_source_embeddings()→ Web kaynağı embedding vektörlerini kaydet
    search_similar_papers()    → Cosine benzerliği ile semantik makale arama
    search_similar_web_sources()→ Cosine benzerliği ile semantik kaynak arama
==============================================================================
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import (
    ResearchSession,
    AcademicPaperModel,
    WebSourceModel,
    ClaimVerificationModel,
    ResearchReportModel,
)
from core.state import (
    AcademicPaperSource,
    WebSource,
    ClaimVerification,
    ResearchReport,
)

logger = logging.getLogger("ResearchMind.Database.Service")


# ─── Oturum (Session) İşlemleri ─────────────────────────────────────────────

async def create_session(
    db: AsyncSession,
    session_id: str,
    query: str,
) -> ResearchSession:
    """
    Yeni bir araştırma oturumu kaydı oluşturur (status=pending).
    """
    session = ResearchSession(
        id=session_id,
        query=query,
        status="pending",
        iteration_count=0,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    logger.info(f"Yeni oturum oluşturuldu: {session_id[:8]}")
    return session


async def update_session_status(
    db: AsyncSession,
    session_id: str,
    status: str,
    iteration_count: int = 0,
    result_summary: Optional[dict] = None,
) -> None:
    """
    Araştırma oturumunun durumunu ve iterasyon sayısını günceller.
    Status değerleri: 'pending', 'running', 'cancelling', 'completed', 'failed', 'cancelled'
    """
    values = {
        "status": status,
        "iteration_count": iteration_count,
        "updated_at": datetime.now(timezone.utc),
    }
    if result_summary is not None:
        values["result_summary"] = result_summary

    stmt = (
        update(ResearchSession)
        .where(ResearchSession.id == session_id)
        .values(**values)
    )
    await db.execute(stmt)
    await db.commit()
    logger.debug(f"Oturum durumu güncellendi: {session_id[:8]} → {status}")


async def get_session(
    db: AsyncSession,
    session_id: str,
) -> Optional[ResearchSession]:
    """ID ile araştırma oturumunu getirir."""
    result = await db.execute(
        select(ResearchSession).where(ResearchSession.id == session_id)
    )
    return result.scalar_one_or_none()


async def list_sessions(
    db: AsyncSession,
    status_filter: Optional[str] = None,
    limit: int = 50,
) -> List[ResearchSession]:
    """
    Araştırma oturumlarını listeler.
    Opsiyonel durum filtresi ile filtrelenebilir.
    """
    query = select(ResearchSession).order_by(ResearchSession.created_at.desc()).limit(limit)
    if status_filter:
        query = query.where(ResearchSession.status == status_filter)
    result = await db.execute(query)
    return list(result.scalars().all())


# ─── Kaynak (Source) İşlemleri ──────────────────────────────────────────────

async def save_academic_papers(
    db: AsyncSession,
    session_id: str,
    papers: List[AcademicPaperSource],
) -> int:
    """
    Akademik makale listesini veritabanına kaydeder.
    Duplicate kontrolü: (session_id, paper_id) UNIQUE constraint sayesinde
    aynı makale iki kez eklenmez (ON CONFLICT IGNORE mantığı).
    Kaydedilen yeni makale sayısını döner.
    """
    saved = 0
    for paper in papers:
        # Mevcut kayıt var mı kontrol et
        existing = await db.execute(
            select(AcademicPaperModel).where(
                AcademicPaperModel.session_id == session_id,
                AcademicPaperModel.paper_id == paper.id,
            )
        )
        if existing.scalar_one_or_none():
            logger.debug(f"Makale zaten kayıtlı, atlandı: {paper.id}")
            continue

        intel_dict = None
        if paper.extracted_intel:
            intel_dict = paper.extracted_intel.model_dump()

        db_paper = AcademicPaperModel(
            session_id=session_id,
            paper_id=paper.id,
            title=paper.title,
            authors=paper.authors,
            published_year=paper.published_year,
            url=paper.url,
            pdf_url=paper.pdf_url,
            abstract=paper.abstract,
            extracted_intel=intel_dict,
            relevance_score=paper.relevance_score,
        )
        db.add(db_paper)
        saved += 1

    if saved > 0:
        await db.commit()
        logger.info(f"[{session_id[:8]}] {saved} yeni akademik makale kaydedildi.")
    return saved


async def save_web_sources(
    db: AsyncSession,
    session_id: str,
    web_sources: List[WebSource],
) -> int:
    """
    Web kaynaklarını veritabanına kaydeder.
    Kaydedilen yeni kaynak sayısını döner.
    """
    saved = 0
    seen_urls = set()

    # Mevcut URL'leri al
    existing = await db.execute(
        select(WebSourceModel.url).where(WebSourceModel.session_id == session_id)
    )
    for row in existing.fetchall():
        seen_urls.add(row[0])

    for source in web_sources:
        if source.url in seen_urls:
            continue
        seen_urls.add(source.url)

        db_source = WebSourceModel(
            session_id=session_id,
            url=source.url,
            title=source.title,
            snippet=source.snippet[:2000],  # Çok uzun snippet'leri kırp
            relevance_score=source.relevance_score,
        )
        db.add(db_source)
        saved += 1

    if saved > 0:
        await db.commit()
        logger.info(f"[{session_id[:8]}] {saved} yeni web kaynağı kaydedildi.")
    return saved


# ─── Doğrulama (Fact-Check) İşlemleri ──────────────────────────────────────

async def save_claim_verifications(
    db: AsyncSession,
    session_id: str,
    verifications: List[ClaimVerification],
) -> int:
    """
    Fact Checker ajan çıktılarını veritabanına kaydeder.
    Mevcut doğrulama kayıtları önce silinip yenileriyle değiştirilir
    (her çalıştırmada taze sonuçlar istenir).
    """
    # Önce bu session'ın eski doğrulamalarını sil
    existing = await db.execute(
        select(ClaimVerificationModel).where(
            ClaimVerificationModel.session_id == session_id
        )
    )
    for old in existing.scalars().all():
        await db.delete(old)

    saved = 0
    for v in verifications:
        db_claim = ClaimVerificationModel(
            session_id=session_id,
            claim_text=v.claim_text,
            source_reference=v.source_reference,
            evidence_quote=v.evidence_quote,
            verification_status=v.verification_status,
            confidence_score=v.confidence_score,
            notes=v.notes,
        )
        db.add(db_claim)
        saved += 1

    if saved > 0:
        await db.commit()
        logger.info(f"[{session_id[:8]}] {saved} iddia doğrulama kaydı yazıldı.")
    return saved


# ─── Rapor (Report) İşlemleri ───────────────────────────────────────────────

async def save_report(
    db: AsyncSession,
    session_id: str,
    report: ResearchReport,
    additional_metadata: Optional[dict] = None,
) -> ResearchReportModel:
    """
    Nihai araştırma raporunu veritabanına kaydeder.
    Session başına yalnızca bir rapor olabilir (UNIQUE constraint).
    Rapor zaten varsa günceller.
    """
    # Mevcut rapor var mı?
    existing = await db.execute(
        select(ResearchReportModel).where(
            ResearchReportModel.session_id == session_id
        )
    )
    db_report = existing.scalar_one_or_none()

    # Raporu Markdown formatında birleştir
    report_md = f"# {report.title}\n\n"
    report_md += f"## Yönetici Özeti\n{report.executive_summary}\n\n"
    for sec in report.sections:
        report_md += f"## {sec.get('heading', '')}\n{sec.get('content', '')}\n\n"
    if report.comparative_analysis_markdown:
        report_md += f"## Karşılaştırmalı Analiz\n{report.comparative_analysis_markdown}\n\n"
    if report.verification_matrix_markdown:
        report_md += f"## Doğrulama Matrisi\n{report.verification_matrix_markdown}\n\n"
    report_md += f"## Kısıtlar ve Gelecek\n{report.limitations_and_future_directions}\n\n"
    report_md += "## Kaynakça\n"
    for b in report.bibliography:
        report_md += f"- {b.get('citation', '')}\n"

    metadata = {
        "sections_count": len(report.sections),
        "bibliography_count": len(report.bibliography),
        "has_comparative_table": bool(report.comparative_analysis_markdown),
        "has_verification_matrix": bool(report.verification_matrix_markdown),
    }
    if additional_metadata:
        metadata.update(additional_metadata)

    if db_report:
        # Güncelle
        db_report.title = report.title
        db_report.executive_summary = report.executive_summary
        db_report.report_markdown = report_md
        db_report.report_metadata = metadata
        db_report.created_at = datetime.now(timezone.utc)
    else:
        # Yeni oluştur
        db_report = ResearchReportModel(
            session_id=session_id,
            title=report.title,
            executive_summary=report.executive_summary,
            report_markdown=report_md,
            report_metadata=metadata,
        )
        db.add(db_report)

    await db.commit()
    await db.refresh(db_report)
    logger.info(f"[{session_id[:8]}] Rapor veritabanına kaydedildi: '{report.title[:60]}'")
    return db_report


async def get_report(
    db: AsyncSession,
    session_id: str,
) -> Optional[ResearchReportModel]:
    """Session ID ile raporu getirir."""
    result = await db.execute(
        select(ResearchReportModel).where(
            ResearchReportModel.session_id == session_id
        )
    )
    return result.scalar_one_or_none()


async def get_papers_by_session(
    db: AsyncSession,
    session_id: str,
) -> List[AcademicPaperModel]:
    """Bir araştırmaya ait tüm akademik makaleleri getirir."""
    result = await db.execute(
        select(AcademicPaperModel).where(
            AcademicPaperModel.session_id == session_id
        ).order_by(AcademicPaperModel.relevance_score.desc())
    )
    return list(result.scalars().all())


async def get_web_sources_by_session(
    db: AsyncSession,
    session_id: str,
) -> List[WebSourceModel]:
    """Bir araştırmaya ait tüm web kaynaklarını getirir."""
    result = await db.execute(
        select(WebSourceModel).where(
            WebSourceModel.session_id == session_id
        ).order_by(WebSourceModel.relevance_score.desc())
    )
    return list(result.scalars().all())


async def get_verifications_by_session(
    db: AsyncSession,
    session_id: str,
) -> List[ClaimVerificationModel]:
    """Bir araştırmaya ait tüm iddia doğrulama kayıtlarını getirir."""
    result = await db.execute(
        select(ClaimVerificationModel).where(
            ClaimVerificationModel.session_id == session_id
        )
    )
    return list(result.scalars().all())


# ─── Faz-6: Semantic Memory — Embedding Kayıt ve Arama ───────────────────────

async def save_paper_embeddings(
    db: AsyncSession,
    session_id: str,
    embeddings_map: dict,
) -> int:
    """
    Akademik makalelerin embedding vektörlerini günceller.

    Args:
        db: Aktif veritabanı oturumu
        session_id: Araştırma oturumu ID'si
        embeddings_map: {paper_id: List[float]} formatında vektör haritası

    Returns:
        Güncellenen kayıt sayısı
    """
    if not embeddings_map:
        return 0

    updated = 0
    for paper_id, embedding in embeddings_map.items():
        if embedding is None:
            continue
        await db.execute(
            update(AcademicPaperModel)
            .where(
                AcademicPaperModel.session_id == session_id,
                AcademicPaperModel.paper_id == paper_id,
            )
            .values(embedding=embedding)
        )
        updated += 1

    await db.commit()
    logger.info(
        f"[{session_id[:8]}] {updated} makale embeddingi kaydedildi."
    )
    return updated


async def save_web_source_embeddings(
    db: AsyncSession,
    session_id: str,
    embeddings_map: dict,
) -> int:
    """
    Web kaynaklarının embedding vektörlerini günceller.

    Args:
        db: Aktif veritabanı oturumu
        session_id: Araştırma oturumu ID'si
        embeddings_map: {url: List[float]} formatında vektör haritası

    Returns:
        Güncellenen kayıt sayısı
    """
    if not embeddings_map:
        return 0

    updated = 0
    for url, embedding in embeddings_map.items():
        if embedding is None:
            continue
        await db.execute(
            update(WebSourceModel)
            .where(
                WebSourceModel.session_id == session_id,
                WebSourceModel.url == url,
            )
            .values(embedding=embedding)
        )
        updated += 1

    await db.commit()
    logger.info(
        f"[{session_id[:8]}] {updated} web kaynağı embeddingi kaydedildi."
    )
    return updated


async def search_similar_papers(
    db: AsyncSession,
    query_embedding: List[float],
    exclude_session_id: Optional[str] = None,
    limit: int = 5,
    min_similarity: float = 0.75,
) -> List[AcademicPaperModel]:
    """
    pgvector cosine benzerliği ile semantik akademik makale araması.

    Yalnızca embedding'i bulunan (is NOT NULL) makalelerde arama yapar.
    İsteğe bağlı olarak belirtilen oturumu hariç tutar (aynı araştırmanın
    kendi makalelerini tekrar getirmemek için).

    Args:
        db: Aktif veritabanı oturumu
        query_embedding: 768 boyutlu sorgu vektörü
        exclude_session_id: Hariç tutulacak oturum (opsiyonel)
        limit: Maksimum sonuç sayısı
        min_similarity: Minimum cosine benzerliği (0.0–1.0, varsayılan: 0.75)

    Returns:
        Benzerlik sırasına göre AcademicPaperModel listesi
    """
    # cosine_distance = 1 - cosine_similarity → max_distance = 1 - min_similarity
    max_distance = 1.0 - min_similarity

    stmt = (
        select(AcademicPaperModel)
        .where(AcademicPaperModel.embedding.isnot(None))
        .where(
            AcademicPaperModel.embedding.cosine_distance(query_embedding) <= max_distance
        )
        .order_by(
            AcademicPaperModel.embedding.cosine_distance(query_embedding)
        )
        .limit(limit)
    )

    if exclude_session_id:
        stmt = stmt.where(AcademicPaperModel.session_id != exclude_session_id)

    result = await db.execute(stmt)
    papers = result.scalars().all()
    logger.info(
        f"Semantik makale araması: {len(papers)} sonuç "
        f"(min_similarity={min_similarity}, hariç={exclude_session_id[:8] if exclude_session_id else 'yok'})"
    )
    return list(papers)


async def search_similar_web_sources(
    db: AsyncSession,
    query_embedding: List[float],
    exclude_session_id: Optional[str] = None,
    limit: int = 3,
    min_similarity: float = 0.75,
) -> List[WebSourceModel]:
    """
    pgvector cosine benzerliği ile semantik web kaynağı araması.

    Args:
        db: Aktif veritabanı oturumu
        query_embedding: 768 boyutlu sorgu vektörü
        exclude_session_id: Hariç tutulacak oturum (opsiyonel)
        limit: Maksimum sonuç sayısı
        min_similarity: Minimum cosine benzerliği (varsayılan: 0.75)

    Returns:
        Benzerlik sırasına göre WebSourceModel listesi
    """
    max_distance = 1.0 - min_similarity

    stmt = (
        select(WebSourceModel)
        .where(WebSourceModel.embedding.isnot(None))
        .where(
            WebSourceModel.embedding.cosine_distance(query_embedding) <= max_distance
        )
        .order_by(
            WebSourceModel.embedding.cosine_distance(query_embedding)
        )
        .limit(limit)
    )

    if exclude_session_id:
        stmt = stmt.where(WebSourceModel.session_id != exclude_session_id)

    result = await db.execute(stmt)
    sources = result.scalars().all()
    logger.info(
        f"Semantik web araması: {len(sources)} sonuç "
        f"(min_similarity={min_similarity})"
    )
    return list(sources)
