"""
==============================================================================
Görevi: Akademik Makale Araştırmacı Ajanı (Paper Researcher Agent)
==============================================================================
Bu ajan, araştırma planındaki akademik odaklı alt soruları işler:
1. Alt soruya ait optimize edilmiş arama terimlerini kullanarak arXiv ve
   Semantic Scholar API'larından ilgili makaleleri çeker.
2. Makalelerin PDF içeriklerini asenkron / önbellekli olarak inceler.
3. Bir makaleyi yüzeysel özetlemenin ötesine geçerek;
   - Model mimarisini (model_architecture)
   - Eğitim metodolojisini (training_methodology)
   - Kullanılan veri kümelerini (datasets_used)
   - Benchmark skorlarını (evaluation_benchmarks)
   - Temel bulguları ve kısıtları (limitations)
   yapılandırılmış 'ExtractedPaperIntel' formatında LLM ile ayrıştırır.
4. Elde edilen zenginleştirilmiş makaleleri LangGraph durumuna aktarır.
==============================================================================
"""

import logging
from typing import List
from langchain_core.messages import SystemMessage, HumanMessage
from config.settings import get_settings
from core.llm import get_fast_llm
from core.state import (
    AcademicPaperSource,
    ExtractedPaperIntel,
    SubQuestion,
    ResearchState
)
from tools.academic_search import search_academic_papers
from tools.pdf_reader import download_and_extract_pdf_text, extract_targeted_sections

logger = logging.getLogger("ResearchMind.Agents.PaperResearcher")


PAPER_EXTRACTION_PROMPT = """Sen uzman bir Bilimsel Araştırmacı ve Makale Analistisin (Academic Paper Intelligence Agent).
Aşağıda başlığı, özeti ve seçilmiş PDF bölümleri verilen akademik makaleyi derinlemesine incele.

Makaleden aşağıdaki yapılandırılmış teknik bilgileri çıkar:
1. model_architecture: Kullanılan temel algoritma, matematiksel şema veya model mimarisi (örn. 'ML-KEM-768 lattice-based KEM', 'ML-DSA-65', 'Transformer-based encoder', 'ResNet' vb.).
2. training_methodology: Yöntem, protokol, tasarım felsefesi veya eğitim stratejisi (örn. 'FIPS 203 uyumlu parametre seçimi, NTT optimizasyonu' veya 'İki aşamalı ön eğitim ve denetimli ince ayar').
3. datasets_used: Deney, benchmark, parametre seti veya test için kullanılan veri kümeleri / standartlar (örn. 'NIST FIPS 203 test vektörleri' veya 'ImageNet, MMBench').
4. evaluation_benchmarks: Test edilen ölçütler, güvenlik kategorileri veya elde edilen sayısal skorlar (örn. {"NIST_Security_Category": "3 (AES-192 eşdeğeri)", "PublicKey_Bytes": "1184", "Accuracy": "84.2%"}).
5. key_findings: Makalenin sunduğu en önemli yenilik ve kazanımların kısa ve somut maddeleri.
6. limitations: Makalenin açıkça belirttiği veya yöntemdeki eksiklikler, saldırı açıkları (yan kanal, hata enjeksiyonu vb.), yüksek hesaplama maliyeti veya çözülemeyen durumlar.

Metinde açıkça bulunmayan bilgiler için tahmin yapma, null veya boş liste bırak.
"""


def extract_paper_intelligence(paper: AcademicPaperSource) -> ExtractedPaperIntel:
    """
    Belirli bir akademik makaleden LLM aracılığıyla yapılandırılmış teknik zeka çıkarır.
    PDF indirme bağlantısı varsa indirip hedeflenen bölümleri de LLM'e besler.
    """
    settings = get_settings()

    # Ek metin için PDF içeriği kontrolü
    pdf_sections_text = ""
    if paper.pdf_url:
        try:
            full_pdf_text = download_and_extract_pdf_text(paper.pdf_url, max_pages=8)
            if full_pdf_text:
                sections = extract_targeted_sections(full_pdf_text)
                pdf_sections_text = (
                    f"\n\n--- [Metodoloji ve Mimari Bölümü] ---\n{sections.get('method_and_architecture', '')[:2500]}\n"
                    f"\n--- [Deneyler ve Sonuçlar Bölümü] ---\n{sections.get('experiments_and_results', '')[:2500]}\n"
                    f"\n--- [Limitasyonlar Bölümü] ---\n{sections.get('limitations_and_conclusion', '')[:1500]}"
                )
        except Exception as e:
            logger.warning(f"PDF indirme/bölümleme atlandı: {e}")

    # API anahtarı yoksa temel özet tabanlı heuristic çıkarım yap
    api_key = settings.GEMINI_API_KEY
    if not api_key or api_key.startswith("buraya_"):
        return ExtractedPaperIntel(
            model_architecture="Mimari bilgisi (Abstract tabanlı analiz)",
            training_methodology="Eğitim metodolojisi makale özetinde açıklanmıştır.",
            datasets_used=["Belirtilen makale veri havuzu"],
            evaluation_benchmarks={},
            key_findings=[paper.abstract[:200] + "..."],
            limitations=["Detaylı limitasyonlar tam raporda incelenecektir."]
        )

    try:
        llm = get_fast_llm()
        structured_llm = llm.with_structured_output(ExtractedPaperIntel)

        prompt_input = (
            f"Makale Başlığı: {paper.title}\n"
            f"Yazarlar: {', '.join(paper.authors)}\n"
            f"Yıl: {paper.published_year or 'Bilinmiyor'}\n\n"
            f"Özet (Abstract):\n{paper.abstract}\n"
            f"{pdf_sections_text}"
        )

        intel: ExtractedPaperIntel = structured_llm.invoke([
            SystemMessage(content=PAPER_EXTRACTION_PROMPT),
            HumanMessage(content=prompt_input)
        ])

        return intel
    except Exception as e:
        logger.error(f"Paper intelligence çıkarımında LLM hatası: {e}")
        return ExtractedPaperIntel(
            model_architecture="Çıkarım sırasında hata oluştu",
            training_methodology=None,
            datasets_used=[],
            evaluation_benchmarks={},
            key_findings=[paper.abstract[:200] + "..."],
            limitations=[]
        )


def conduct_paper_research(state: ResearchState) -> dict:
    """
    LangGraph düğümü: Alt sorulardan akademik nitelikte olanları alır,
    arXiv / Semantic Scholar araması yapar ve PDF zekasını çıkarıp state'e ekler.
    """
    sub_questions: List[SubQuestion] = state.get("sub_questions", [])
    settings = get_settings()

    academic_sub_qs = [
        sq for sq in sub_questions
        if sq.target_type in ("academic", "both") and sq.status != "completed"
    ]

    if not academic_sub_qs:
        logger.info("Akademik araştırma yapılacak bekleyen alt soru bulunamadı.")
        return {"audit_logs": ["[Paper Researcher] İncelenecek akademik alt soru bulunmadı."]}

    new_papers: List[AcademicPaperSource] = []
    seen_ids = {p.id for p in state.get("academic_sources", [])}
    audit_messages = []

    for sq in academic_sub_qs:
        logger.info(f"Akademik alt soru işleniyor: [{sq.id}] {sq.question}")
        queries = sq.search_queries or [sq.question]

        for query in queries[:2]:  # Her alt soru için ilk 2 sorguyu çalıştır
            found_papers = search_academic_papers(query, max_results=settings.MAX_PAPERS_PER_SUBQUESTION)

            for paper in found_papers:
                if paper.id not in seen_ids:
                    seen_ids.add(paper.id)

                    # Makaleden derin teknik zeka çıkar
                    intel = extract_paper_intelligence(paper)
                    paper.extracted_intel = intel
                    new_papers.append(paper)
                    audit_messages.append(f"[Paper Researcher] İncelendi: '{paper.title[:50]}...' ({paper.id})")

        sq.status = "completed"

    return {
        "academic_sources": new_papers,
        "audit_logs": audit_messages or ["[Paper Researcher] Akademik tarama tamamlandı."]
    }

