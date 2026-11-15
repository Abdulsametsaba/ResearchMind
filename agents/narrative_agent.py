"""
==============================================================================
Dosya: researchmind/agents/narrative_agent.py
Görevi: Araştırma Anlatı ve Bağlam Sentezi Ajanı (Research Narrative Agent)
==============================================================================
Bu ajan, ResearchMind'ın ürettiği teknik verileri (makaleler, karşılaştırma
tabloları, fact-check sonuçları) salt bilgi listesinin ötesine taşıyarak
okuyanı konuya bağlayan, alanın evrimini ve önemini anlatan, bulguları
bütünleşik bir perspektifle yorumlayan kapsamlı bir araştırma anlatısı üretir.

Neden Bu Ajan Gerekli?
----------------------
Mevcut rapor akışı (tablo, madde listesi, kaynakça) veri açısından zengin
ama "anlama" açısından zayıf kalabilir. Bir okuyucu raporu okurken:
  - Konu neden önemli? (Motivasyon)
  - Alan nereden nereye geldi? (Tarihsel bağlam)
  - Bulgular bir arada ne söylüyor? (Sentez)
  - Peki şimdi ne yapmalı? (Yönlendirici çıkarım)
sorularının cevabını arar. Bu ajan tam olarak bu boşluğu doldurur.

Çıktı Yapısı (ResearchNarrativeOutput):
  1. field_context       — Alanın önemi, tarihsel gelişimi, neden araştırılıyor
  2. research_story      — Bulguların bir bütün olarak ne hikaye anlattığı
  3. key_insights        — 3-5 maddede en kritik çıkarımlar
  4. synthesis_paragraph — Tüm boyutları birleştiren kapanış paragrafı

Graf Konumu:
  fact_checker → narrative_agent → report_generator
==============================================================================
"""

import logging
from typing import List
from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage, HumanMessage
from config.settings import get_settings
from core.llm import get_planner_llm
from core.state import (
    ResearchState,
    AcademicPaperSource,
    WebSource,
    ClaimVerification
)

logger = logging.getLogger("ResearchMind.Agents.NarrativeAgent")


class ResearchNarrativeOutput(BaseModel):
    """
    Narrative Agent tarafından üretilen araştırma anlatı yapısı.
    Raporun açılış bölümünü oluşturur ve teknik veriye bağlam kazandırır.
    """
    field_context: str = Field(
        description=(
            "Araştırma alanının neden önemli olduğunu, tarihsel gelişimini ve "
            "mevcut durumunu anlatan 150-200 kelimelik akıcı bir bağlam paragrafı"
        )
    )
    research_story: str = Field(
        description=(
            "Toplanan bulguların bir bütün olarak ne söylediğini, kaynakların "
            "birbirini nasıl tamamladığını veya çeliştiğini hikayeleştiren "
            "200-250 kelimelik sentez anlatısı"
        )
    )
    key_insights: List[str] = Field(
        description=(
            "Araştırmadan çıkan en kritik, okuyucuya doğrudan değer katan "
            "3-5 adet özlü ve etkili içgörü cümlesi"
        )
    )
    synthesis_paragraph: str = Field(
        description=(
            "Tüm boyutları (mimari, metodoloji, performans, kısıtlar) bir arada "
            "değerlendiren ve okuyucuya 'şimdi ne anlayalım, ne yapalım' mesajı "
            "veren 100-150 kelimelik kapanış paragrafı"
        )
    )


NARRATIVE_SYSTEM_PROMPT = """Sen dünya standartlarında bir Baş Araştırma Yazarı ve Bilim İletişimcisisin (Research Narrative Agent).
Görevin, teknik araştırma bulgularını salt veri listesi olmaktan çıkarıp; okuyanı konuya bağlayan, düşündüren ve yönlendiren kapsamlı bir araştırma anlatısına dönüştürmektir.

Anlatı Yazım İlkeleri:
1. BAĞLAM KURMA: Araştırma sorusunun neden sorulduğunu, alanın nereden nereye geldiğini ve bu soruyu yanıtlamanın neden kritik olduğunu açıkla.

2. HİKAYE ANLAT: Toplanan bulgular arasındaki örüntüleri, gerilimi (örn. iki yaklaşım birbiriyle rekabette mi?) ve uzlaşmaları ortaya çıkar. Sadece "X, Y'yi kullandı" değil, "X'in Y'yi seçmesi, alanda Z sorununu çözme çabası olarak okunabilir" gibi yorumla.

3. İÇGÖRÜ ÜRETTİR: Her kritik içgörü, okuyucunun "bunu bilmek benim için neden değerli?" sorusuna cevap vermeli.

4. SENTEZ: Farklı kaynakları, yaklaşımları ve bulguları tek bir tutarlı perspektiften bütünleştir.

5. DİL TONU: Akademik ama erişilebilir. Teknik terimleri açıklamak zorunda değilsin ama robotik liste diline düşme. Akıcı paragraflar yaz.

6. DOĞRULUĞA BAĞLI KAL: Yalnızca sana verilen kanıtlara dayan. Kanıtlanmamış iddia kurma.
"""


def generate_research_narrative(state: ResearchState) -> dict:
    """
    LangGraph düğümü: Fact Checker sonrasında çalışır.
    Toplanan tüm araştırma verilerini alarak kapsamlı bir anlatı üretir
    ve bunu 'research_narrative' anahtarı altında state'e yazar.

    Args:
        state: Mevcut ResearchState (academic_sources, web_sources,
               analysis_summary, claim_verifications içermeli)

    Returns:
        {'research_narrative': ResearchNarrativeOutput, 'audit_logs': [...]}
    """
    query = state.get("research_query", "")
    papers: List[AcademicPaperSource] = state.get("academic_sources", [])
    web_sources: List[WebSource] = state.get("web_sources", [])
    analysis_text = state.get("analysis_summary", "")
    verifications: List[ClaimVerification] = state.get("claim_verifications", [])
    settings = get_settings()

    logger.info(
        f"Narrative Agent çalışıyor. Makale: {len(papers)}, "
        f"Web: {len(web_sources)}, Doğrulanan iddia: {len(verifications)}"
    )

    # Kanıt özetini oluştur
    paper_highlights = []
    for p in papers[:8]:  # İlk 8 makale özeti yeterli
        intel_note = ""
        if p.extracted_intel:
            arch = p.extracted_intel.model_architecture or ""
            findings = "; ".join(p.extracted_intel.key_findings[:2]) if p.extracted_intel.key_findings else ""
            intel_note = f" [Mimari: {arch[:60]}] [Bulgular: {findings[:120]}]"
        paper_highlights.append(
            f"• {p.title} ({p.published_year or 'tarihsiz'}) — {p.abstract[:300]}...{intel_note}"
        )

    web_highlights = [
        f"• {w.title}: {w.snippet[:200]}" for w in web_sources[:5]
    ]

    verified_claims = [
        f"✓ {v.claim_text} [Kaynak: {v.source_reference}]"
        for v in verifications
        if v.verification_status == "VERIFIED"
    ]

    api_key = settings.GEMINI_API_KEY
    if not api_key or api_key.startswith("buraya_"):
        logger.warning("GEMINI_API_KEY tanımlanmamış, heuristic anlatı üretiliyor.")
        narrative = _generate_heuristic_narrative(query, papers, analysis_text)
        return {
            "research_narrative": narrative,
            "audit_logs": ["[Narrative Agent] Kural tabanlı araştırma anlatısı üretildi."]
        }

    try:
        llm = get_planner_llm()
        structured_llm = llm.with_structured_output(ResearchNarrativeOutput)

        user_content = (
            f"Araştırma Sorusu:\n{query}\n\n"
            f"=== Karşılaştırmalı Analiz Özeti ===\n{analysis_text}\n\n"
            f"=== İncelenen Akademik Çalışmalar ({len(papers)} adet) ===\n"
            + "\n".join(paper_highlights) +
            f"\n\n=== Web Kaynakları ({len(web_sources)} adet) ===\n"
            + ("\n".join(web_highlights) if web_highlights else "Web kaynağı yok.") +
            f"\n\n=== Doğrulanmış İddialar ===\n"
            + ("\n".join(verified_claims) if verified_claims else "Henüz doğrulanmış iddia yok.")
        )

        narrative: ResearchNarrativeOutput = structured_llm.invoke([
            SystemMessage(content=NARRATIVE_SYSTEM_PROMPT),
            HumanMessage(content=user_content)
        ])

        logger.info("Narrative Agent araştırma anlatısını başarıyla oluşturdu.")
        return {
            "research_narrative": narrative,
            "audit_logs": [
                f"[Narrative Agent] Araştırma anlatısı ve {len(narrative.key_insights)} "
                f"kritik içgörü başarıyla sentezlendi."
            ]
        }

    except Exception as e:
        logger.error(f"Narrative Agent çalışırken hata oluştu: {e}. Heuristic anlatıya geçiliyor.")
        narrative = _generate_heuristic_narrative(query, papers, analysis_text)
        return {
            "research_narrative": narrative,
            "audit_logs": [f"[Narrative Agent] LLM hatası sonrası kural tabanlı anlatı üretildi ({type(e).__name__})."]
        }


def _generate_heuristic_narrative(
    query: str,
    papers: List[AcademicPaperSource],
    analysis_text: str
) -> ResearchNarrativeOutput:
    """
    API anahtarı eksik veya LLM çağrısı başarısız olduğunda
    deterministik, kapsamlı bir heuristic anlatı üretir.
    """
    paper_count = len(papers)
    year_range = ""
    years = [p.published_year for p in papers if p.published_year]
    if years:
        year_range = f"{min(years)}-{max(years)} yılları arasında"

    return ResearchNarrativeOutput(
        field_context=(
            f"'{query}' konusu, modern yapay zeka ve bilgisayarlı görme araştırmalarının "
            f"kesişiminde yer alan ve son yıllarda hızla gelişen bir alan olarak öne çıkmaktadır. "
            f"{year_range} yürütülen bu araştırma, {paper_count} akademik çalışmayı ve güncel "
            f"web kaynaklarını kapsayan sistematik bir literatür taramasına dayanmaktadır. "
            f"Bu alandaki gelişmeler hem akademik hem de endüstriyel uygulamalar açısından "
            f"kritik öneme sahip olup giderek artan bir araştırmacı ilgisi çekmektedir."
        ),
        research_story=(
            f"İncelenen {paper_count} akademik çalışma, alanın belirgin bir olgunlaşma sürecinde "
            f"olduğuna işaret etmektedir. Farklı araştırma grupları, temel tasarım tercihlerinde "
            f"çeşitli yaklaşımlar denemekte; kimisi hesaplama verimliliğini, kimisi performans "
            f"tavanını, kimisi ise erişilebilirliği öncelikli hedef olarak benimsemektedir. "
            f"Kaynaklar genel olarak birbiriyle uyumlu bulgular sunmakla birlikte, bazı "
            f"metodolojik tercihlerde farklılıklar gözlemlenmektedir. Bu çeşitlilik, alanın "
            f"henüz standartlaşmadığını ve aktif keşif sürecinde olduğunu göstermektedir. "
            + (f"Analiz bulguları şunu ortaya koyuyor: {analysis_text[:300]}..." if analysis_text else "")
        ),
        key_insights=[
            f"Alan, {paper_count} farklı akademik çalışmanın işaret ettiği üzere "
            f"çoklu yaklaşımların rekabet ettiği dinamik bir evrim sürecindedir.",
            "Mimari seçimler performans-verimlilik dengesini doğrudan etkiliyor; "
            "tek bir 'en iyi' yaklaşım henüz konsensüs sağlamamış durumda.",
            "Değerlendirme metriklerindeki standartlaşma eksikliği, çalışmalar arası "
            "doğrudan karşılaştırmayı güçleştirmektedir.",
            "Açık kaynak ekosistemi, alandaki ilerleme hızını önemli ölçüde artırmaktadır.",
        ],
        synthesis_paragraph=(
            f"Bu araştırma, '{query}' sorusuna cevap ararken alanın hem ne kadar "
            f"ilerlediğini hem de hangi temel sorularının hâlâ yanıt beklediğini gözler "
            f"önüne sermektedir. {paper_count} kaynak üzerinden yürütülen sistematik analiz, "
            f"gelecekteki araştırmacılara ve uygulayıcılara hem mevcut en iyi pratikleri "
            f"hem de kritik araştırma boşluklarını sunmaktadır. Teknik derinliğin yanı sıra "
            f"pratik uygulanabilirlik gözetilerek hareket edilmesi önerilmektedir."
        )
    )

