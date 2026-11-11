"""
==============================================================================
Görevi: SQLAlchemy 2.0 ORM Veritabanı Modelleri
==============================================================================
Bu dosya, araştırma oturumlarının (sessions), bulunan akademik makalelerin,
web kaynaklarının, kanıt kartlarının (fact-check claims) ve nihai raporların
PostgreSQL üzerinde kalıcı olarak saklanmasını sağlayan tabloları tanımlar.
==============================================================================
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy import (
    String,
    Text,
    Float,
    DateTime,
    ForeignKey,
    JSON,
    Boolean
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


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
        comment="pending, running, completed, failed"
    )
    iteration_count: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # İlişki
    session: Mapped["ResearchSession"] = relationship("ResearchSession", back_populates="report")

