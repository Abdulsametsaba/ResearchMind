"""
==============================================================================
Dosya: researchmind/database/models.py
Görevi: SQLAlchemy 2.0 ORM Veritabanı Modelleri
==============================================================================
Bu dosya, araştırma oturumlarının (sessions), bulunan akademik makalelerin,
web kaynaklarının, kanıt kartlarının (fact-check claims) ve nihai raporların
PostgreSQL üzerinde kalıcı olarak saklanmasını sağlayan tabloları tanımlar.

Faz-6 (Semantic Memory) eklemeleri:
  - AcademicPaperModel.embedding  → VECTOR(768) — makale özet vektörü
  - WebSourceModel.embedding      → VECTOR(768) — kaynak snippet vektörü
  Vektörler araştırma tamamlandıktan sonra Gemini text-embedding-004 ile
  üretilip pgvector'a kaydedilir. Yeni araştırmalarda Memory Retriever
  Agent benzer kaynakları bu sütunlar üzerinden cosine similarity ile bulur.
==============================================================================
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import (
    String,
    Text,
    Float,
    DateTime,
    ForeignKey,
    JSON,
    Index,
    UniqueConstraint
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector

# Gemini text-embedding-004 ve pgvector boyutu
EMBEDDING_DIM = 768


def _utcnow() -> datetime:
    """timezone-aware UTC şimdiki zamanı döner (Python 3.12+ uyumlu)."""
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Tüm veritabanı modelleri için temel sınıf."""
    pass


class ResearchSession(Base):
    """
    Her bir kullanıcı araştırmasını ve yürütme durumunu temsil eder.
    """
    __tablename__ = "research_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    query: Mapped[str] = mapped_column(Text, nullable=False, comment="Kullanıcının araştırma sorusu")
    status: Mapped[str] = mapped_column(
        String(30),
        default="pending",
        comment="pending, running, cancelling, completed, failed, cancelled"
    )
    iteration_count: Mapped[int] = mapped_column(default=0)
    result_summary: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        comment="Persisted counts and evaluation metrics for completed research"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    __table_args__ = (
        Index("ix_sessions_status", "status"),
    )

    # İlişkiler
    academic_papers: Mapped[List["AcademicPaperModel"]] = relationship(
        "AcademicPaperModel", back_populates="session", cascade="all, delete-orphan"
    )
    web_sources: Mapped[List["WebSourceModel"]] = relationship(
        "WebSourceModel", back_populates="session", cascade="all, delete-orphan"
    )
    claim_verifications: Mapped[List["ClaimVerificationModel"]] = relationship(
        "ClaimVerificationModel", back_populates="session", cascade="all, delete-orphan"
    )
    report: Mapped[Optional["ResearchReportModel"]] = relationship(
        "ResearchReportModel", back_populates="session", uselist=False, cascade="all, delete-orphan"
    )


class AcademicPaperModel(Base):
    """
    İncelenen akademik makalelerin meta verileri ve çıkarılan teknik bilgiler.
    """
    __tablename__ = "academic_papers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("research_sessions.id", ondelete="CASCADE"))
    paper_id: Mapped[str] = mapped_column(String(100), comment="arXiv ID veya DOI")
    title: Mapped[str] = mapped_column(Text, nullable=False)
    authors: Mapped[Optional[List[str]]] = mapped_column(JSON, default=list)
    published_year: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    pdf_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    abstract: Mapped[str] = mapped_column(Text, nullable=False)
    extracted_intel: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        comment="Model mimarisi, veri seti, metrikler ve limitasyonlar"
    )
    relevance_score: Mapped[float] = mapped_column(Float, default=1.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    # Faz-6: Semantic Memory — makale başlık+abstract vektörü (nullable, sonradan doldurulur)
    embedding: Mapped[Optional[Any]] = mapped_column(
        Vector(EMBEDDING_DIM),
        nullable=True,
        comment="Gemini text-embedding-004 ile üretilen 768-boyutlu anlamsal vektör"
    )

    __table_args__ = (
        UniqueConstraint("session_id", "paper_id", name="uq_session_paper"),
    )

    # İlişki
    session: Mapped["ResearchSession"] = relationship("ResearchSession", back_populates="academic_papers")


class WebSourceModel(Base):
    """
    Arama motorlarından çekilen web kaynakları.
    """
    __tablename__ = "web_sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("research_sessions.id", ondelete="CASCADE"))
    url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    snippet: Mapped[str] = mapped_column(Text, nullable=False)
    relevance_score: Mapped[float] = mapped_column(Float, default=1.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    # Faz-6: Semantic Memory — web kaynağı başlık+snippet vektörü
    embedding: Mapped[Optional[Any]] = mapped_column(
        Vector(EMBEDDING_DIM),
        nullable=True,
        comment="Gemini text-embedding-004 ile üretilen 768-boyutlu anlamsal vektör"
    )

    # İlişki
    session: Mapped["ResearchSession"] = relationship("ResearchSession", back_populates="web_sources")


class ClaimVerificationModel(Base):
    """
    Fact-Checker ajanının kanıt doğrulama kayıtları.
    """
    __tablename__ = "claim_verifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("research_sessions.id", ondelete="CASCADE"))
    claim_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_reference: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_quote: Mapped[str] = mapped_column(Text, nullable=False)
    verification_status: Mapped[str] = mapped_column(
        String(30), comment="VERIFIED, CONTRADICTED, NEEDS_VERIFICATION"
    )
    confidence_score: Mapped[float] = mapped_column(Float, default=1.0)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        Index("ix_claims_verification_status", "verification_status"),
    )

    # İlişki
    session: Mapped["ResearchSession"] = relationship("ResearchSession", back_populates="claim_verifications")


class ResearchReportModel(Base):
    """
    Üretilen nihai araştırma raporları ve kaynakçaları.
    """
    __tablename__ = "research_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("research_sessions.id", ondelete="CASCADE"), unique=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    executive_summary: Mapped[str] = mapped_column(Text, nullable=False)
    report_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    report_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    # İlişki
    session: Mapped["ResearchSession"] = relationship("ResearchSession", back_populates="report")

