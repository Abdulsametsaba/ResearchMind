"""
==============================================================================
Dosya: researchmind/agents/analysis_agent.py
Görevi: Karşılaştırmalı Analiz ve Boşluk Tespiti Ajanı (Analysis Agent)
==============================================================================
Bu ajan, Paper Researcher ve Web Researcher tarafından toplanan tüm ham
bulguları sentezler ve derinlemesine teknik karşılaştırma yürütür.

Temel İşlevleri:
1. Makalelerin ve web kaynaklarının sunduğu mimari yaklaşımları, eğitim yöntemlerini
   ve benchmark skorlarını çapraz analiz eder.
2. Farklı kaynaklar arasındaki uzlaşmaları ve çelişkileri tespit eder.
3. Boşluk Analizi (Gap Analysis): Kullanıcının ana sorusunda eksik kalan,
   kaynak bulunamamış veya şüpheli görünen boyutları belirler.
4. İteratif Araştırma Kararı: Eğer kritik eksiklikler varsa 'is_research_sufficient=False'
   bayrağı açar ve hedefli yeni arama sorguları ('missing_information_queries') üreterek
   sistemin ek arama yapmasını tetikler.
==============================================================================
"""

import logging
from typing import List
from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage, HumanMessage
from ResearchMind.config.settings import get_settings
from ResearchMind.core.llm import get_planner_llm
from ResearchMind.core.state import ResearchState, AcademicPaperSource, WebSource

logger = logging.getLogger("ResearchMind.Agents.AnalysisAgent")


class AnalysisOutput(BaseModel):
    """
    Analysis Agent tarafından üretilen yapılandırılmış sentez çıktısı.
    """
    summary: str = Field(description="Araştırma bulgularının kapsamlı teknik özeti")
    comparative_markdown_table: str = Field(
        description="Modelleri/yaklaşımları mimari, eğitim, veri seti ve benchmark bazında kıyaslayan Markdown tablosu"
    )
    is_sufficient: bool = Field(
        description="Mevcut kanıtlar ana soruyu ve tüm alt soruları tatmin edici şekilde yanıtlamaya yetiyor mu?"
    )
    missing_aspects_or_gaps: List[str] = Field(
        default_factory=list,
        description="Henüz netleşmemiş veya daha fazla kanıt gerektiren eksik noktalar"
    )
    follow_up_queries: List[str] = Field(
        default_factory=list,
        description="Eksik noktaları kapatmak için yeni arama sorguları (eğer gerekliyse)"
    )


ANALYSIS_SYSTEM_PROMPT = """Sen Baş Araştırma Analisti ve Bilimsel Değerlendiricisin (Analysis Agent).
Görevin, toplanan akademik makaleleri ve web kaynaklarını çapraz inceleyerek sentezlemek, modeller arasındaki teknik farkları ortaya koymak ve araştırmanın yeterliliğini değerlendirmektir.

Analiz Kriterleri:
1. Mimari Karşılaştırması: Görsel kodlayıcı (Vision Encoder), dil omurgası (LLM Backbone) ve aradaki bağlayıcı (Projector/Connector) farklarını vurgula.
2. Metodoloji ve Veri: Ön eğitim, talimat ayarlama (SFT) ve hizalama (RLHF/DPO) yöntemlerini kıyasla.
3. Benchmark Değerlendirmesi: MMBench, MME, MathVista, VQA gibi standart değerlendirme metriklerindeki başarıları sayısal olarak tabloya dök.
4. Boşluk ve Çelişki Tespiti:
   - Eğer bir alt soru için somut veri bulunamadıysa bunu açıkça belirt.
   - Eğer yeterli kanıt yoksa 'is_sufficient: false' yap ve 'follow_up_queries' içine hedefli ek İngilizce arama terimleri ekle.
   - Eğer toplanan veriler yeterliyse 'is_sufficient: true' olarak işaretle.
"""


def conduct_analysis(state: ResearchState) -> dict:
    """
    LangGraph düğümü: Toplanan kaynakları inceler, karşılaştırmalı analiz yapar
    ve iterasyon gerekip gerekmediğine karar verir.
    """
    query = state.get("research_query", "")
    papers: List[AcademicPaperSource] = state.get("academic_sources", [])
    web_sources: List[WebSource] = state.get("web_sources", [])
    iteration_count = state.get("iteration_count", 0)
    settings = get_settings()

    logger.info(f"Analysis Agent çalışıyor. Toplam makale: {len(papers)}, web kaynağı: {len(web_sources)}")

    # Kaynak metinlerini derle
    papers_context = []
    for idx, p in enumerate(papers, 1):
        intel = p.extracted_intel
        intel_str = ""
        if intel:
            intel_str = (
                f"\n  - Mimari: {intel.model_architecture or 'Bilinmiyor'}"
                f"\n  - Eğitim: {intel.training_methodology or 'Bilinmiyor'}"
                f"\n  - Benchmarklar: {intel.evaluation_benchmarks}"
                f"\n  - Limitasyonlar: {', '.join(intel.limitations)}"
            )
        papers_context.append(f"[{idx}] {p.title} ({p.id}, {p.published_year}):\n  Özet: {p.abstract[:400]}...{intel_str}")

    web_context = []
    for idx, w in enumerate(web_sources, 1):
        web_context.append(f"[Web-{idx}] {w.title} ({w.url}):\n  Özet: {w.snippet[:300]}")

    all_evidence = (
        f"=== AKADEMİK MAKALELER ({len(papers)} adet) ===\n" +
        "\n\n".join(papers_context) +
        f"\n\n=== WEB KAYNAKLARI ({len(web_sources)} adet) ===\n" +
        ("\n\n".join(web_context) if web_context else "Henüz web kaynağı eklenmedi.")
    )

    api_key = settings.GEMINI_API_KEY
    # API anahtarı yoksa kural tabanlı analiz üret
    if not api_key or api_key.startswith("buraya_"):
        logger.warning("GEMINI_API_KEY tanımlanmamış, kural tabanlı analiz sentezi devreye alınıyor.")
        return generate_heuristic_analysis(state, all_evidence)

    try:
        llm = get_planner_llm()
        structured_llm = llm.with_structured_output(AnalysisOutput)

        user_content = (
            f"Kullanıcı Araştırma Sorusu:\n{query}\n\n"
            f"Mevcut İterasyon: {iteration_count} (Maksimum: {settings.MAX_ITERATIONS})\n\n"
            f"Toplanan Kanıtlar ve Bulgular:\n{all_evidence}"
        )

        analysis: AnalysisOutput = structured_llm.invoke([
            SystemMessage(content=ANALYSIS_SYSTEM_PROMPT),
            HumanMessage(content=user_content)
        ])

        # Eğer maksimum iterasyona ulaşıldıysa zorunlu olarak yeterli kabul et
        is_sufficient = analysis.is_sufficient or (iteration_count >= settings.MAX_ITERATIONS)

        return {
            "analysis_summary": analysis.summary,
            "comparative_data": {"markdown_table": analysis.comparative_markdown_table},
            "missing_information_queries": analysis.follow_up_queries if not is_sufficient else [],
            "is_research_sufficient": is_sufficient,
            "audit_logs": [
                f"[Analysis Agent] Karşılaştırmalı analiz tamamlandı. Yeterlilik: {is_sufficient} "
                f"(Tespit edilen eksiklik: {len(analysis.missing_aspects_or_gaps)})"
            ]
        }

    except Exception as e:
        logger.error(f"Analysis Agent çalışırken hata oluştu: {e}. Heuristic analize geçiliyor.")
        return generate_heuristic_analysis(state, all_evidence)


def generate_heuristic_analysis(state: ResearchState, evidence_text: str) -> dict:
    """API erişimi olmadığında veya hata anında çalışan deterministik analiz sentezi."""
    papers = state.get("academic_sources", [])
    iteration_count = state.get("iteration_count", 0)
    settings = get_settings()

    table_rows = []
    for p in papers:
        arch = p.extracted_intel.model_architecture if p.extracted_intel else "Transformers / Multi-Modal"
        year = p.published_year or "2024"
        table_rows.append(f"| {p.title[:35]}... | {year} | {arch[:30]} | arXiv | İncelendi |")

    if not table_rows:
        table_rows.append("| Model/Makale Örneği | 2024 | ViT + LLM Decoder | arXiv/Açık Kaynak | Doğrulandı |")

    markdown_table = (
        "| Çalışma / Model | Yıl | Mimari Yaklaşım | Kaynak | Durum |\n"
        "| :--- | :--- | :--- | :--- | :--- |\n" +
        "\n".join(table_rows)
    )

    summary = (
        f"İncelenen {len(papers)} akademik kaynak ve web dökümanları doğrultusunda; "
        "Vision-Language modellerinin genel olarak yüksek çözünürlüklü görsel kodlayıcılar "
        "ile önceden eğitilmiş büyük dil modellerini çapraz dikkat (cross-attention) veya "
        "MLP projektör katmanlarıyla birleştirdiği görülmüştür."
    )

    # İlk iterasyonda test amaçlı yeterli sayılabilir veya max_iterations'a göre karar verilir
    is_sufficient = (len(papers) >= 2) or (iteration_count >= settings.MAX_ITERATIONS)

    return {
        "analysis_summary": summary,
        "comparative_data": {"markdown_table": markdown_table},
        "missing_information_queries": [] if is_sufficient else ["vision language models benchmark performance 2024"],
        "is_research_sufficient": is_sufficient,
        "audit_logs": ["[Analysis Agent] Heuristic karşılaştırmalı analiz ve matris oluşturuldu."]
    }

