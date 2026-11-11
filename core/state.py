"""
==============================================================================
Görevi: LangGraph Merkezi Durum (State) ve Pydantic Veri Modelleri
==============================================================================
Bu dosya, ResearchMind'ın çok ajanlı iş akışında dolaşan ortak hafıza (State)
yapısını tanımlar. Her ajan (Planner, Paper Researcher, Web Researcher,
Analysis Agent, Fact Checker, Report Agent) bu durum nesnesinden veri okur
ve kendi ürettiği bulguları bu nesneye yazar.

Tip güvenliği için Pydantic v2 modelleri ile LangGraph uyumlu TypedDict
birlikte kullanılmıştır.
==============================================================================
"""

import operator
from typing import Annotated, Dict, List, Literal, Optional
from pydantic import BaseModel, Field
from typing_extensions import TypedDict


# ==============================================================================
# 1. Pydantic Veri Modelleri (Yapılandırılmış Çıktılar & Doğrulama)
# ==============================================================================

class SubQuestion(BaseModel):
    """
    Planner Agent tarafından ana araştırma sorusundan türetilen
    her bir alt araştırma konusunu temsil eder.
    """
    id: str = Field(description="Alt soru için benzersiz kimlik (örn. 'SQ-1')")
    question: str = Field(description="Spesifik ve hedefe yönelik alt soru metni")
    rationale: str = Field(description="Bu alt sorunun ana hedefe nasıl hizmet ettiği")
    target_type: Literal["academic", "web", "both"] = Field(
        default="both",
        description="Bu konunun akademik makalelerden mi yoksa web kaynaklarından mı taranacağı"
    )
    search_queries: List[str] = Field(
        default_factory=list,
        description="Arama motorları ve akademik API'lar için optimize edilmiş arama terimleri"
    )
    status: Literal["pending", "in_progress", "completed"] = Field(
        default="pending",
        description="Alt sorunun tamamlanma durumu"
    )


class ExtractedPaperIntel(BaseModel):
    """
    Bir akademik makaleden Paper Researcher ve Analysis Agent tarafından
    ayrıştırılan teknik zeka çıktısı.
    """
    model_architecture: Optional[str] = Field(
        default=None,
        description="Kullanılan temel model mimarisi (örn. ViT-L/14 + Llama-3-8B)"
    )
    training_methodology: Optional[str] = Field(
        default=None,
        description="Eğitim yöntemi, aşamaları ve hizalama teknikleri (SFT, RLHF, DPO vb.)"
    )
    datasets_used: List[str] = Field(
        default_factory=list,
        description="Eğitim veya değerlendirmede kullanılan veri kümeleri"
    )
    evaluation_benchmarks: Dict[str, str] = Field(
        default_factory=dict,
        description="Benchmark adı ve elde edilen skor çiftleri (örn. {'MME': '1850', 'MMBench': '76.4'})"
    )
    key_findings: List[str] = Field(
        default_factory=list,
        description="Makalenin ortaya koyduğu ana yenilikler ve bulgular"
    )
    limitations: List[str] = Field(
        default_factory=list,
        description="Yazarların belirttiği veya tespit edilen eksiklikler ve limitler"
    )


class AcademicPaperSource(BaseModel):
    """
    arXiv veya Semantic Scholar üzerinden tespit edilen ve incelenen
    akademik makale kaydı.
    """
    id: str = Field(description="arXiv ID, DOI veya kaynak kimliği")
    title: str = Field(description="Makale başlığı")
    authors: List[str] = Field(default_factory=list, description="Yazar listesi")
    published_year: Optional[str] = Field(default=None, description="Yayın yılı")
    url: str = Field(description="Makale açılış sayfası URL'i")
    pdf_url: Optional[str] = Field(default=None, description="Doğrudan PDF indirme bağlantısı")
    abstract: str = Field(description="Makale özeti (Abstract)")
    extracted_intel: Optional[ExtractedPaperIntel] = Field(
        default=None,
        description="PDF içerisinden çıkarılan derinleştirilmiş teknik veriler"
    )
    relevance_score: float = Field(
        default=1.0,
        description="Sorgu ile olan anlamsal örtüşme skoru (0.0 - 1.0)"
    )


class WebSource(BaseModel):
    """
    Tavily veya web aramasından elde edilen güncel internet kaynağı.
    """
    url: str = Field(description="Web sitesi URL adresi")
    title: str = Field(description="Sayfa başlığı")
    snippet: str = Field(description="Arama sonucundan gelen özet metin")
    full_content: Optional[str] = Field(
        default=None,
        description="Web sayfasından ayıklanan temiz markdown/metin içeriği"
    )
    relevance_score: float = Field(
        default=1.0,
        description="Sorgu ile olan anlamsal örtüşme skoru"
    )


class ClaimVerification(BaseModel):
    """
    Fact Checker Ajanı tarafından üretilen iddia-kaynak doğrulama kartı.
    """
    claim_id: str = Field(description="İddia kimliği (örn. 'CLM-01')")
    claim_text: str = Field(description="Doğrulanan olgusal iddia metni")
    source_reference: str = Field(
        description="İddiayı destekleyen kaynak başlığı, URL'i veya makale bölümü (örn. 'Paper A, Table 2')"
    )
    evidence_quote: str = Field(
        description="Kaynaktan doğrudan alınan kanıt cümlesi veya alıntı"
    )
    verification_status: Literal["VERIFIED", "CONTRADICTED", "NEEDS_VERIFICATION"] = Field(
        description="Doğrulama kararı"
    )
    confidence_score: float = Field(
        default=1.0,
        description="Modelin bu eşleştirmeden emin olma oranı (0.0 - 1.0)"
    )
    notes: Optional[str] = Field(
        default=None,
        description="Çelişki veya eksiklik durumunda düşülen açıklama notu"
    )


class ResearchReport(BaseModel):
    """
    Report Generation Agent tarafından derlenen nihai kaynakçalı rapor.
    """
    title: str = Field(description="Kapsamlı araştırma raporu başlığı")
    executive_summary: str = Field(description="Yönetici özeti ve ana çıkarımlar")
    sections: List[Dict[str, str]] = Field(
        default_factory=list,
        description="Rapor bölümleri. Her eleman {'heading': '...', 'content': '...'} içerir"
    )
    comparative_analysis_markdown: Optional[str] = Field(
        default=None,
        description="Modeller/Yöntemler arası karşılaştırma tablosu (Markdown formatında)"
    )
    verification_matrix_markdown: Optional[str] = Field(
        default=None,
        description="Doğrulanan iddiaların kanıt tablosu"
    )
    limitations_and_future_directions: str = Field(
        description="Tespit edilen kısıtlar ve gelecekteki araştırma önerileri"
    )
    bibliography: List[Dict[str, str]] = Field(
        default_factory=list,
        description="Numaralandırılmış kaynakça listesi [{'id': 1, 'citation': '...'}]"
    )


# ==============================================================================
# 2. LangGraph ResearchState (Merkezi Graf Hafızası)
# ==============================================================================

class ResearchState(TypedDict):
    """
    LangGraph iş akışında adım adım aktarılan durum verisi.
    Ajanlar bu nesne üzerinden veri paylaşır.
    """
    # Kullanıcı Girdisi
    research_query: str
    user_guidance: Optional[str]

    # Planlama Katmanı
    sub_questions: List[SubQuestion]
    current_subquestion_index: int

    # Toplanan Kanıtlar (Annotated + operator.add ile listelere ekleme yapılır)
    academic_sources: Annotated[List[AcademicPaperSource], operator.add]
    web_sources: Annotated[List[WebSource], operator.add]

    # Analiz ve Sentez
    analysis_summary: str
    comparative_data: Dict[str, any]

    # Doğrulama (Fact-Checking)
    claim_verifications: List[ClaimVerification]

    # İterasyon ve Boşluk Doldurma Kontrolü
    iteration_count: int
    missing_information_queries: List[str]
    is_research_sufficient: bool

    # Nihai Çıktı
    final_report: Optional[ResearchReport]

    # Denetim ve Adım Logları
    audit_logs: Annotated[List[str], operator.add]

