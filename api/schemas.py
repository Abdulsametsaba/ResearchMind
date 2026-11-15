"""
==============================================================================
Dosya: researchmind/api/schemas.py
Görevi: FastAPI İstek (Request) ve Yanıt (Response) Pydantic Şemaları
==============================================================================
Bu dosya, ResearchMind REST API'ının tüm HTTP istek ve yanıt veri yapılarını
tanımlar. Pydantic v2 ile tip güvenliği ve otomatik OpenAPI dokümantasyonu
(Swagger UI) sağlanır.

Şema Hiyerarşisi:
  ResearchRequest        → POST /api/research isteği
  ResearchJobResponse    → Araştırma başlatma yanıtı (session_id + durum)
  ResearchStatusResponse → GET /api/research/{id} durum sorgulama yanıtı
  CancelResearchResponse → POST /api/research/{id}/cancel iptal yanıtı
  ReportResponse         → GET /api/research/{id}/report tam rapor yanıtı
  HealthResponse         → GET /health sistem durumu yanıtı
  MetricsResponse        → GET /api/research/{id}/metrics kalite metrikleri
==============================================================================
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class ResearchRequest(BaseModel):
    """Yeni araştırma başlatma isteği."""
    query: str = Field(
        description="Araştırılacak soru veya problem ifadesi",
        min_length=10,
        max_length=2000,
        examples=["2023-2026 yılları arasında geliştirilen Vision-Language modellerini karşılaştır."]
    )
    guidance: Optional[str] = Field(
        default=None,
        description="Araştırmayı yönlendirmek için opsiyonel ek direktifler",
        max_length=500
    )


class ResearchJobResponse(BaseModel):
    """Araştırma işi başlatıldığında dönen ilk yanıt."""
    session_id: str = Field(description="Araştırma oturumunun benzersiz kimliği")
    status: str = Field(description="İşin mevcut durumu: queued, running, completed, failed, cancelled")
    message: str = Field(description="Kullanıcıya yönelik bilgilendirme mesajı")
    created_at: datetime = Field(description="Oturum oluşturulma zamanı (UTC)")


class CancelResearchResponse(BaseModel):
    """Araştırma iptali yanıtı."""
    session_id: str = Field(description="İptal edilen araştırma oturumunun kimliği")
    status: str = Field(default="cancelled", description="Her zaman 'cancelled' döner")
    message: str = Field(description="İptal işlemi hakkında bilgi mesajı")
    cancelled_at: datetime = Field(description="İptal zamanı (UTC)")


class ClaimVerificationSummary(BaseModel):
    """Tekil iddia doğrulama özeti."""
    claim_id: str
    claim_text: str
    verification_status: str
    confidence_score: float
    source_reference: str


class ReportSectionSummary(BaseModel):
    """Rapor bölümü özeti."""
    heading: str
    content_preview: str = Field(description="Bölüm içeriğinin ilk 300 karakteri")


class ResearchStatusResponse(BaseModel):
    """Araştırma durumu sorgulama yanıtı."""
    session_id: str
    status: str = Field(description="pending, running, completed, failed, cancelled")
    query: str
    iteration_count: int = Field(default=0)
    academic_sources_count: int = Field(default=0)
    web_sources_count: int = Field(default=0)
    claim_verifications_count: int = Field(default=0)
    is_research_sufficient: bool = Field(default=False)
    created_at: datetime
    completed_at: Optional[datetime] = None
    audit_log_count: int = Field(default=0)
    has_report: bool = Field(default=False)


class ReportResponse(BaseModel):
    """Tamamlanmış araştırma raporunun tam yanıtı."""
    session_id: str
    title: str
    executive_summary: str
    sections: List[ReportSectionSummary]
    comparative_analysis_markdown: Optional[str] = None
    verification_matrix_markdown: Optional[str] = None
    limitations_and_future_directions: str
    bibliography: List[Dict[str, str]]
    claim_verifications: List[ClaimVerificationSummary]
    total_sources: int
    created_at: datetime


class EvaluationMetrics(BaseModel):
    """Araştırma kalite değerlendirme metrikleri."""
    session_id: str
    research_coverage_score: float = Field(
        description="Araştırma sorularının ne kadarının cevaplandığı (0.0-1.0)",
        ge=0.0, le=1.0
    )
    citation_accuracy_score: float = Field(
        description="İddiaların kaynaklarla örtüşme oranı (0.0-1.0)",
        ge=0.0, le=1.0
    )
    source_quality_score: float = Field(
        description="Kullanılan kaynakların ortalama kalitesi (0.0-1.0)",
        ge=0.0, le=1.0
    )
    factual_consistency_score: float = Field(
        description="VERIFIED iddia oranı / toplam iddia (0.0-1.0)",
        ge=0.0, le=1.0
    )
    retrieval_recall: float = Field(
        description="Toplam bulunan kaynak sayısına göre geri çağırma oranı",
        ge=0.0, le=1.0
    )
    research_completion_rate: float = Field(
        description="Araştırmanın tamamlanma yüzdesi (0.0-1.0)",
        ge=0.0, le=1.0
    )
    total_sources: int
    total_claims_verified: int
    iteration_count: int
    overall_score: float = Field(description="Ağırlıklı genel araştırma kalite skoru (0.0-1.0)")


class HealthResponse(BaseModel):
    """Sistem sağlık durumu yanıtı."""
    status: str = Field(description="healthy veya degraded")
    version: str = Field(default="0.4.0")
    database: str = Field(description="connected, disconnected veya not_started")
    gemini_api: str = Field(description="configured veya not_configured")
    tavily_api: str = Field(description="configured veya not_configured")
    uptime_seconds: Optional[float] = None
    details: Optional[Dict[str, Any]] = None


# ── Faz-6: Semantic Memory ────────────────────────────────────────────────────

class SemanticPaperResult(BaseModel):
    """Semantik arama sonucunda dönen tekil makale özeti."""
    paper_id: str = Field(description="arXiv ID veya DOI")
    title: str
    authors: List[str] = Field(default_factory=list)
    published_year: Optional[str] = None
    abstract_preview: str = Field(description="Özetin ilk 300 karakteri")
    url: str
    relevance_score: float
    source_session_id: str = Field(description="Bu makalenin ait olduğu araştırma oturumu")


class SemanticWebResult(BaseModel):
    """Semantik arama sonucunda dönen tekil web kaynağı özeti."""
    url: str
    title: str
    snippet_preview: str = Field(description="Snippet'ın ilk 200 karakteri")
    relevance_score: float
    source_session_id: str


class SemanticSearchResponse(BaseModel):
    """
    GET /api/research/memory/search yanıtı.
    pgvector cosine benzerliği ile bulunan kaynaklar döner.
    """
    query: str = Field(description="Kullanılan arama sorgusu")
    similarity_threshold: float = Field(description="Kullanılan minimum benzerlik eşiği")
    papers: List[SemanticPaperResult] = Field(default_factory=list)
    web_sources: List[SemanticWebResult] = Field(default_factory=list)
    total_found: int = Field(description="Toplam bulunan kaynak sayısı")



class ScopeGateResponse(BaseModel):
    """
    POST /api/research — Kapsam değerlendirmesi reddi veya netleştirme yanıtı.

    Bu şema yalnızca araştırma BAŞLATILMADIGI durumlarda (OUT_OF_SCOPE veya
    NEEDS_CLARIFICATION) döner. IN_SCOPE durumunda standart ResearchJobResponse
    döner — bu şema asla kullanılmaz.

    HTTP 200 ile döner (hata değil, beklenen bir sistem davranışı).
    """
    status: str = Field(
        description=(
            "'out_of_scope': İstek araştırma görevi değil. "
            "'needs_clarification': Araştırma hedefi netleştirme gerektiriyor."
        ),
        examples=["out_of_scope", "needs_clarification"]
    )
    message: str = Field(
        description="Kullanıcıya gösterilecek nazik Türkçe açıklama veya netleştirici soru."
    )
    session_id: None = Field(
        default=None,
        description="Araştırma başlatılmadığından her zaman null döner."
    )
    hint: Optional[str] = Field(
        default=None,
        description=(
            "Kullanıcının isteğini nasıl yeniden çerçeveleyebileceğine dair opsiyonel ipucu. "
            "Yalnızca OUT_OF_SCOPE durumunda eklenir."
        )
    )

