
"""
==============================================================================
Görevi: Nihai Araştırma Raporu Üretim Ajanı
==============================================================================

Sorumluluklar:
- Araştırma çıktılarından akademik rapor oluşturmak.
- Kaynak numaralarını deterministik biçimde yönetmek.
- Analiz, narrative, karşılaştırma ve doğrulama çıktılarını birleştirmek.
- Aynı bulguların farklı bölümlerde tekrarlanmasını önlemek.
- Kanıtlarla desteklenmeyen bilgi üretmemek.
- LLM kullanılamadığında güvenli ve kanıta dayalı fallback üretmek.

Mevcut ResearchReport ve ResearchState arayüzleri korunmuştur.
"""

import logging
from typing import Any, Dict, List

from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage, HumanMessage

from config.settings import get_settings
from core.llm import get_planner_llm
from core.state import (
    ResearchReport,
    ResearchState,
    AcademicPaperSource,
    WebSource,
    ClaimVerification,
)
from prompts.report_agent import create_report_prompt
import re


logger = logging.getLogger("ResearchMind.Agents.ReportAgent")


def clean_executive_summary(text: str) -> str:
    """
    Yönetici özetindeki araya giren kaynak/atıf numaralarını ve köşeli parantez referanslarını temizler.
    
    Örnekler:
      - '[20], [35]. Bu mimari dönüşüm...' -> 'Bu mimari dönüşüm...'
      - 'Bu araştırma [1], modellerin [2, 3] gelişimini analiz eder.' -> 'Bu araştırma, modellerin gelişimini analiz eder.'
      - 'Büyük ölçekli veri setleri [Kaynak 1-3] kullanılarak...' -> 'Büyük ölçekli veri setleri kullanılarak...'
      - 'Başarı oranı 2024 yılında %92 olarak ölçülmüştür.' -> (Tarih ve yüzdelere dokunulmaz!)
    """
    if not text:
        return ""

    # 1. Parantezler arasındaki ayırıcı virgülleri temizle: [20], [35] -> [20] [35]
    cleaned = re.sub(
        r'(\[\s*(?:kaynak|source|ref|referans)?\s*\d+(?:\s*[,-–]\s*\d+)*\s*\])\s*,\s*(?=\[)',
        r'\1 ',
        text,
        flags=re.IGNORECASE
    )

    # 2. Köşeli parantez içindeki kaynak/sayı referansları: [1], [1, 2], [1-3], [Kaynak 1], [Source 1]
    cleaned = re.sub(
        r'\[\s*(?:kaynak|source|ref|referans)?\s*\d+(?:\s*[,-–]\s*\d+)*\s*\]',
        '',
        cleaned,
        flags=re.IGNORECASE
    )

    # 3. Art arda gelen veya tekil köşeli parantezli sayılar: [1][2]
    cleaned = re.sub(r'\[\s*\d+\s*\]', '', cleaned)

    # 4. Parantez içindeki açık kaynak referansları: (Kaynak 1), (Source 1), (Ref 2)
    cleaned = re.sub(
        r'\(\s*(?:kaynak|source|ref|referans)\s*\d+\s*\)',
        '',
        cleaned,
        flags=re.IGNORECASE
    )

    # 5. Cümle başlarında veya satır başlarında sarkan noktalama işaretlerini (. , ; : -) temizle
    cleaned = re.sub(r'(^|\n|[.!?]\s+)[\s,.;:-]+([A-ZÇĞİÖŞÜa-zçğıöşü])', r'\1\2', cleaned)

    # 6. Metnin en başındaki olası sarkan noktalama işaretlerini temizle
    cleaned = re.sub(r'^[ \t,.;:-]+', '', cleaned)

    # 7. Noktalama işaretlerinden önce oluşan gereksiz boşlukları düzelt: 'geliştirilmiştir . Bu' -> 'geliştirilmiştir. Bu'
    cleaned = re.sub(r'\s+([.,;:!?])', r'\1', cleaned)

    # 8. Silinen atıflar sonrası oluşan çift/çoklu boşlukları teke indir
    cleaned = re.sub(r'[ \t]{2,}', ' ', cleaned)

    return cleaned.strip()


def clean_report_citations(text: str) -> str:
    """
    Raporun teknik alt bölümlerindeki atıf sözdizimini akademik ve akıcı hale getirir.
    
    Örnekler:
      - '[20], [35]' -> '[20, 35]'
      - '[20, 35]. Bu mimari dönüşüm...' -> 'İlgili araştırmalarda [20, 35], bu mimari dönüşüm...'
      - '[1]. Model omurgası...' -> 'İlgili araştırmada [1], model omurgası...'
    """
    if not text:
        return ""

    # 1. Bitişik parantezleri tek parantezde birleştir: [20], [35] -> [20, 35]
    pattern_brackets = r'\[\s*([\d\s,-–]+)\s*\]\s*,\s*\[\s*([\d\s,-–]+)\s*\]'
    while re.search(pattern_brackets, text):
        text = re.sub(pattern_brackets, r'[\1, \2]', text)

    # 2. Cümle veya satır başında izole noktalı atıf varsa ('[20, 35]. Bu mimari...') bunu akıcı Türkçe yapıya dönüştür
    def repl_leading_cite(m):
        prefix = m.group(1) or ""
        cites = m.group(2).strip()
        first_char = m.group(3).lower()
        word = "İlgili araştırmada" if ("," not in cites and "-" not in cites and "–" not in cites) else "İlgili araştırmalarda"
        return f"{prefix}{word} [{cites}], {first_char}"

    text = re.sub(r'(^|\n|[.!?]\s+)\[\s*([\d\s,-–]+)\s*\]\.\s+([A-ZÇĞİÖŞÜa-zçğıöşü])', repl_leading_cite, text)

    # 3. Noktalama işaretlerinden önce oluşan gereksiz boşlukları toparla
    text = re.sub(r'\s+([.,;:!?])', r'\1', text)
    text = re.sub(r'[ \t]{2,}', ' ', text)

    return text.strip()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _value(obj: Any, key: str, default: Any = None) -> Any:
    """Pydantic model veya dict üzerinden güvenli alan erişimi."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _as_text(value: Any) -> str:
    """None ve diğer değerleri güvenli metne dönüştürür."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _markdown_cell(value: Any) -> str:
    """Markdown tablo hücresindeki özel karakterleri düzenler."""
    text = _as_text(value)
    return (
        text.replace("|", "\\|")
        .replace("\r", " ")
        .replace("\n", " ")
    )


def _format_list(values: Any) -> str:
    if not values:
        return "Belirtilmemiş"

    if isinstance(values, str):
        return values

    return ", ".join(_as_text(item) for item in values if item is not None)


def _build_bibliography(
    papers: List[AcademicPaperSource],
    web_sources: List[WebSource],
) -> List[Dict[str, str]]:
    """
    Kaynakları tek bir numaralandırılmış listede toplar.

    Önemli:
    Bu listedeki sıra, rapor içerisindeki [1], [2] atıflarının
    karşılığıdır. LLM'e de aynı sıra ile gönderilir.
    """
    bibliography: List[Dict[str, str]] = []

    for paper in papers:
        authors = _value(paper, "authors", []) or []
        title = _as_text(_value(paper, "title", "Başlıksız çalışma"))
        year = _value(paper, "published_year", None)
        url = _as_text(_value(paper, "url", ""))

        authors_text = ", ".join(authors[:3]) if authors else "Yazar belirtilmemiş"

        if len(authors) > 3:
            authors_text += " vd."

        citation = (
            f"{authors_text} ({year or 'Yıl belirtilmemiş'}). "
            f"\"{title}\"."
        )

        if url:
            citation += f" {url}"

        bibliography.append({
            "index": str(len(bibliography) + 1),
            "citation": citation,
        })

    for source in web_sources:
        title = _as_text(_value(source, "title", "Başlıksız web kaynağı"))
        url = _as_text(_value(source, "url", ""))

        citation = f"{title}. Web kaynağı."

        if url:
            citation += f" {url}"

        bibliography.append({
            "index": str(len(bibliography) + 1),
            "citation": citation,
        })

    return bibliography


def _build_source_evidence(
    papers: List[AcademicPaperSource],
    web_sources: List[WebSource],
    bibliography: List[Dict[str, str]],
) -> str:
    """
    LLM'e kaynakların yalnızca başlıklarını değil, mevcut kanıt
    içeriklerini de verir.

    Her kaynak için bibliography index'i açıkça belirtilir.
    """
    evidence_blocks: List[str] = []

    for index, paper in enumerate(papers):
        extracted = _value(paper, "extracted_intel")
        abstract = _as_text(_value(paper, "abstract", ""))

        title = _as_text(_value(paper, "title", "Başlıksız çalışma"))
        year = _value(paper, "published_year", "Belirtilmemiş")
        url = _as_text(_value(paper, "url", ""))

        block = [
            f"[{index + 1}] {title}",
            f"Yıl: {year}",
            f"URL: {url or 'Belirtilmemiş'}",
            f"Abstract: {abstract[:4500] or 'Mevcut değil'}",
        ]

        if extracted:
            block.extend([
                "Çıkarılan bilimsel bilgiler:",
                f"- Mimari: {_as_text(_value(extracted, 'model_architecture', '')) or 'Belirtilmemiş'}",
                f"- Eğitim yöntemi: {_as_text(_value(extracted, 'training_methodology', '')) or 'Belirtilmemiş'}",
                f"- Veri setleri: {_format_list(_value(extracted, 'datasets_used', []))}",
                f"- Benchmarklar: {_format_list(_value(extracted, 'evaluation_benchmarks', []))}",
                f"- Bulgular: {_format_list(_value(extracted, 'key_findings', []))}",
                f"- Sınırlılıklar: {_format_list(_value(extracted, 'limitations', []))}",
            ])

        evidence_blocks.append("\n".join(block))

    offset = len(papers)

    for index, source in enumerate(web_sources):
        source_index = offset + index + 1

        title = _as_text(_value(source, "title", "Başlıksız web kaynağı"))
        url = _as_text(_value(source, "url", ""))
        snippet = _as_text(_value(source, "snippet", ""))
        full_content = _as_text(_value(source, "full_content", ""))

        block = [
            f"[{source_index}] {title}",
            f"URL: {url or 'Belirtilmemiş'}",
            f"Snippet: {snippet[:1500] or 'Mevcut değil'}",
            f"Sayfa içeriği: {full_content[:4500] or 'Mevcut değil'}",
        ]

        evidence_blocks.append("\n".join(block))

    return "\n\n---\n\n".join(evidence_blocks) or (
        "Araştırma kapsamında kullanılabilecek kaynak içeriği bulunamadı."
    )


def _build_verification_matrix(
    verifications: List[ClaimVerification],
) -> str:
    """İddia doğrulama kayıtlarından Markdown matrisi oluşturur."""

    headers = (
        "| İddia ID | İddia | Kaynak | Kanıt | Durum | Güven | Koşul / Açıklama |\n"
        "|---|---|---|---|---|---|---|\n"
    )

    if not verifications:
        return headers + (
            "| - | Doğrulanmış iddia kaydı bulunmuyor | - | - | - | - | - |"
        )

    rows = []

    for verification in verifications:
        status = _as_text(
            _value(verification, "verification_status", "NEEDS_VERIFICATION")
        )

        confidence = _value(verification, "confidence_score", None)

        if confidence is not None:
            confidence_text = f"{float(confidence) * 100:.0f}%"
        else:
            confidence_text = "Belirtilmemiş"

        quote = _as_text(
            _value(verification, "evidence_quote", "")
        )

        # Alıntıyı keserken doğrudan alıntı olduğunu koruyoruz.
        if len(quote) > 240:
            quote = quote[:237] + "..."

        notes = _as_text(_value(verification, "notes", "-"))

        rows.append(
            "| "
            + " | ".join([
                _markdown_cell(_value(verification, "claim_id", "-")),
                _markdown_cell(_value(verification, "claim_text", "-")),
                _markdown_cell(_value(verification, "source_reference", "-")),
                _markdown_cell(f'"{quote}"' if quote else "Kanıt alıntısı yok"),
                _markdown_cell(status),
                _markdown_cell(confidence_text),
                _markdown_cell(notes),
            ])
            + " |"
        )

    return headers + "\n".join(rows)


def _get_comparison_table(comp_data: Any) -> str:
    if not isinstance(comp_data, dict):
        return ""

    table = comp_data.get("markdown_table", "")
    return _as_text(table)


def _get_narrative_context(narrative: Any) -> str:
    """
    Narrative Agent çıktısını yalnızca bağlamsal girdi olarak hazırlar.

    Bu içerik doğrudan rapora section olarak eklenmez.
    """
    if not narrative:
        return "Narrative Agent çıktısı mevcut değil."

    field_context = _as_text(
        _value(narrative, "field_context", "")
    )

    research_story = _as_text(
        _value(narrative, "research_story", "")
    )

    key_insights = _value(narrative, "key_insights", []) or []

    synthesis = _as_text(
        _value(narrative, "synthesis_paragraph", "")
    )

    insights_text = "\n".join(
        f"- {_as_text(item)}" for item in key_insights
    )

    return (
        f"Alan bağlamı:\n{field_context or 'Belirtilmemiş'}\n\n"
        f"Araştırma anlatısı:\n{research_story or 'Belirtilmemiş'}\n\n"
        f"Kritik içgörüler:\n{insights_text or 'Belirtilmemiş'}\n\n"
        f"Sentez:\n{synthesis or 'Belirtilmemiş'}"
    )


def _build_gap_context(comp_data: Any) -> str:
    if not isinstance(comp_data, dict):
        return ""

    gaps = comp_data.get("gaps", [])
    if not gaps:
        return ""

    if isinstance(gaps, str):
        return gaps

    return "\n".join(f"- {_as_text(gap)}" for gap in gaps)


# ---------------------------------------------------------------------------
# Structured LLM Output
# ---------------------------------------------------------------------------

class ReportSectionOutput(BaseModel):
    """Raporun dinamik alt bölümü."""

    heading: str = Field(
        description="Araştırma konusuna uygun, açıklayıcı bölüm başlığı."
    )

    content: str = Field(
        description=(
            "İlgili bölümün akademik anlatımı. "
            "Kaynak gerektiren iddialar [1], [2] biçiminde atıflandırılmalıdır."
        )
    )


class ReportSynthesisOutput(BaseModel):
    """
    LLM tarafından oluşturulan rapor metni.

    Karşılaştırma tablosu, doğrulama matrisi ve kaynakça
    Python tarafında deterministik olarak oluşturulur.
    """

    title: str = Field(
        description="Araştırma konusunu doğru yansıtan akademik rapor başlığı."
    )

    executive_summary: str = Field(
        description=(
            "Araştırmanın amacı, kapsamı, temel bulguları ve genel sonucunu "
            "özetleyen kısa ve bütünlüklü yönetici özeti."
        )
    )

    sections: List[ReportSectionOutput] = Field(
        description=(
            "Araştırma konusuna özgü, birbirini tekrar etmeyen akademik "
            "bölümler. Metodoloji, tematik bulgular ve sonuç gibi "
            "ihtiyaç duyulan bölümleri içermelidir."
        )
    )

    limitations_and_future_directions: str = Field(
        description=(
            "Kanıtlardan çıkarılabilen sınırlılıklar, açık problemler "
            "ve gelecekte araştırılabilecek yönler."
        )
    )


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

REPORT_SYSTEM_PROMPT = create_report_prompt()

# ---------------------------------------------------------------------------
# Main LangGraph Node
# ---------------------------------------------------------------------------

def generate_research_report(state: ResearchState) -> dict:
    """
    LangGraph düğümü:
    Araştırma state'ini kullanarak nihai ResearchReport üretir.

    Mevcut state ve API sözleşmesi korunur.
    """

    query = _as_text(state.get("research_query", ""))
    analysis_text = _as_text(state.get("analysis_summary", ""))

    comp_data = state.get("comparative_data", {}) or {}
    verifications: List[ClaimVerification] = (
        state.get("claim_verifications", []) or []
    )
    papers: List[AcademicPaperSource] = (
        state.get("academic_sources", []) or []
    )
    web_sources: List[WebSource] = (
        state.get("web_sources", []) or []
    )

    narrative = state.get("research_narrative")

    settings = get_settings()

    logger.info("Report Agent: Nihai rapor hazırlanıyor.")

    # 1. Deterministik kaynakça
    bibliography = _build_bibliography(papers, web_sources)

    # 2. Karşılaştırma tablosu
    comp_table_md = _get_comparison_table(comp_data)

    # 3. Kanıt doğrulama matrisi
    verification_matrix_md = _build_verification_matrix(verifications)

    # 4. Kaynakların kanıt içerikleri
    evidence_context = _build_source_evidence(
        papers=papers,
        web_sources=web_sources,
        bibliography=bibliography,
    )

    # 5. Narrative bağlamı
    narrative_context = _get_narrative_context(narrative)

    # 6. Analiz boşlukları
    gaps_context = _build_gap_context(comp_data)

    # 7. API anahtarı kontrolü
    api_key = getattr(settings, "GEMINI_API_KEY", None)

    if not api_key or api_key.startswith("buraya_"):
        logger.warning(
            "GEMINI_API_KEY bulunamadı. "
            "Kanıta dayalı fallback raporu oluşturuluyor."
        )

        report = generate_heuristic_report(
            query=query,
            analysis_text=analysis_text,
            comp_table_md=comp_table_md,
            verification_matrix_md=verification_matrix_md,
            bibliography=bibliography,
            papers=papers,
            web_sources=web_sources,
            comp_data=comp_data,
        )

        return {
            "final_report": report,
            "audit_logs": [
                "[Report Agent] LLM kullanılamadığı için "
                "kanıta dayalı fallback raporu oluşturuldu."
            ],
        }

    try:
        llm = get_planner_llm()
        structured_llm = llm.with_structured_output(
            ReportSynthesisOutput
        )

        bibliography_context = "\n".join(
            f"[{item['index']}] {item['citation']}"
            for item in bibliography
        ) or "Kaynakça kaydı bulunamadı."

        user_content = f"""
ARAŞTIRMA SORUSU
{query}

ANALİZ AJANI ÇIKTISI
{analysis_text or 'Analiz özeti mevcut değil.'}

NARRATIVE AGENT BAĞLAMI
{narrative_context}

TESPİT EDİLEN ARAŞTIRMA BOŞLUKLARI
{gaps_context or 'Ayrı bir boşluk kaydı bulunmuyor.'}

KAYNAK KATALOĞU
{bibliography_context}

KAYNAK KANITLARI
{evidence_context}

KARŞILAŞTIRMALI ANALİZ TABLOSU
{comp_table_md or 'Karşılaştırma tablosu mevcut değil.'}

KANIT DOĞRULAMA MATRİSİ
{verification_matrix_md}

RAPOR ÜRETİM TALİMATI

1. Araştırma sorusunu doğrudan yanıtlayan bir başlık oluştur.
2. Yönetici özetini araştırmanın gerçek kapsamı ve mevcut bulgularıyla sınırla.
3. Araştırma konusuna özgü tematik bölümler oluştur.
4. Analiz bulgularını kaynak kanıtlarıyla sentezle.
5. Karşılaştırma tablosunu ve doğrulama matrisini tekrar yazma.
6. Narrative Agent çıktısını ayrı bir bölüm olarak kopyalama.
7. Kaynak numaralarını kaynak kataloğuyla birebir eşleştir.
8. Eksik bilgileri ve kanıt sınırlarını açıkça belirt.
9. Birbirini tekrar eden bölümler oluşturma.
10. Kaynaklarda bulunmayan hiçbir teknik veya sayısal iddia ekleme.

Çıktı yalnızca istenen yapılandırılmış rapor alanlarını içermelidir.
"""

        synthesis: ReportSynthesisOutput = structured_llm.invoke([
            SystemMessage(content=REPORT_SYSTEM_PROMPT),
            HumanMessage(content=user_content),
        ])

        # ÖNEMLİ:
        # Atıflar temizlenmiyor veya yeniden yazılmıyor.
        # Narrative Agent içeriği ayrıca section olarak eklenmiyor.
        sections_dict_list = [
            {
                "heading": section.heading.strip(),
                "content": clean_report_citations(section.content.strip()),
            }
            for section in synthesis.sections
            if section.heading.strip() and section.content.strip()
        ]

        report = ResearchReport(
            title=synthesis.title.strip() or f"Araştırma Raporu: {query}",
            executive_summary=clean_executive_summary(synthesis.executive_summary.strip()),
            sections=sections_dict_list,
            comparative_analysis_markdown=comp_table_md,
            verification_matrix_markdown=verification_matrix_md,
            limitations_and_future_directions=clean_report_citations(
                synthesis.limitations_and_future_directions.strip()
            ),
            bibliography=bibliography,
        )

        logger.info(
            "Report Agent: LLM ile nihai rapor başarıyla oluşturuldu. "
            "Bölüm sayısı: %d, kaynak sayısı: %d",
            len(sections_dict_list),
            len(bibliography),
        )

        return {
            "final_report": report,
            "audit_logs": [
                "[Report Agent] Kanıta dayalı akademik rapor "
                "başarıyla oluşturuldu."
            ],
        }

    except Exception as exc:
        logger.exception(
            "Report Agent LLM üretiminde hata oluştu. "
            "Fallback rapora geçiliyor."
        )

        report = generate_heuristic_report(
            query=query,
            analysis_text=analysis_text,
            comp_table_md=comp_table_md,
            verification_matrix_md=verification_matrix_md,
            bibliography=bibliography,
            papers=papers,
            web_sources=web_sources,
            comp_data=comp_data,
        )

        return {
            "final_report": report,
            "audit_logs": [
                "[Report Agent] LLM üretimi başarısız oldu. "
                f"Fallback rapor oluşturuldu ({type(exc).__name__})."
            ],
        }


# ---------------------------------------------------------------------------
# Safe Fallback
# ---------------------------------------------------------------------------

def generate_heuristic_report(
    query: str,
    analysis_text: str,
    comp_table_md: str,
    verification_matrix_md: str,
    bibliography: List[Dict[str, str]],
    papers: List[AcademicPaperSource],
    web_sources: List[WebSource],
    comp_data: Any = None,
) -> ResearchReport:
    """
    LLM kullanılamadığında güvenli rapor iskeleti üretir.

    Bu fonksiyonun amacı LLM kalitesinde akademik metin üretmek değildir.
    Mevcut kanıtları koruyan, uydurma bilgi eklemeyen bir fallback
    sağlamaktır.
    """

    paper_count = len(papers)
    web_count = len(web_sources)

    title = f"Araştırma Raporu: {query}"

    executive_summary = (
        f"Bu rapor, '{query}' araştırma sorusu kapsamında "
        f"toplanan mevcut kaynaklar ve analiz çıktıları kullanılarak "
        f"hazırlanmıştır. Araştırma kapsamında {paper_count} akademik "
        f"çalışma ve {web_count} web kaynağı bulunmaktadır. "
        f"Bu sürümde otomatik akademik sentez üretilemediğinden, "
        f"rapor içeriği mevcut analiz ve kanıt kayıtlarıyla sınırlıdır."
    )

    sections: List[Dict[str, str]] = []

    if analysis_text:
        sections.append({
            "heading": "Araştırma Bulguları ve Analiz",
            "content": analysis_text,
        })
    else:
        sections.append({
            "heading": "Araştırma Bulguları ve Analiz",
            "content": (
                "Analiz ajanından kullanılabilir bir araştırma özeti "
                "alınamadı. Bu nedenle mevcut raporda bilimsel bulgu "
                "veya sonuç iddiası oluşturulmamıştır."
            ),
        })

    limitations_parts = []

    gaps = _build_gap_context(comp_data)

    if gaps:
        limitations_parts.append(
            "Analiz aşamasında kaydedilen araştırma boşlukları:\n" + gaps
        )

    if not papers and not web_sources:
        limitations_parts.append(
            "Araştırma kapsamında kullanılabilir akademik veya web "
            "kaynağı bulunmamaktadır."
        )

    if not verifications_available(verification_matrix_md):
        limitations_parts.append(
            "İddialar için kullanılabilir doğrulama kaydı bulunmamaktadır."
        )

    if not limitations_parts:
        limitations_parts.append(
            "LLM tabanlı sentez üretimi gerçekleştirilemediği için "
            "kaynakların kapsamlı eleştirel değerlendirmesi ve gelecek "
            "araştırma yönleri bu fallback sürümünde oluşturulmamıştır."
        )

    limitations = "\n\n".join(limitations_parts)

    return ResearchReport(
        title=title,
        executive_summary=executive_summary,
        sections=sections,
        comparative_analysis_markdown=comp_table_md,
        verification_matrix_markdown=verification_matrix_md,
        limitations_and_future_directions=limitations,
        bibliography=bibliography,
    )


def verifications_available(matrix: str) -> bool:
    """Boş doğrulama matrisi durumunu kontrol eder."""
    return (
        bool(matrix)
        and "Doğrulanmış iddia kaydı bulunmuyor" not in matrix
    )
