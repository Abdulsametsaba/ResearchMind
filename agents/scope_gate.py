"""
==============================================================================
Dosya: researchmind/agents/scope_gate.py
Görevi: Research Scope Gate — Araştırma Kapsamı Değerlendirici (Faz-7)
==============================================================================
Bu modül, kullanıcının gönderdiği isteğin ResearchMind'ın amacıyla uyumlu
olup olmadığını POST /api/research endpoint'i çağrılmadan ÖNCE değerlendirir.

TEMEL FELSEFE:
  ResearchMind konuyu değil, görev türünü kısıtlar.
  - Futbol, tıp, yapay zekâ, ekonomi, tarih → HEPSİ kabul edilebilir konu.
  - Bilgi sorusu, sohbet, basit açıklama  → KABUL EDİLEMEZ görev türü.

ÜÇ OLASI ÇIKTI:
  IN_SCOPE             → Araştırma başlatılabilir, pipeline'a devam et.
  OUT_OF_SCOPE         → İstek araştırma görevi değil; nazik reddetme mesajı dön.
  NEEDS_CLARIFICATION  → Araştırma hedefi belirsiz; netleştirici soru üret.

MİMARİ KONUM:
  POST /api/research
        ↓
  [Research Scope Gate]  ← BU MODÜL
        ↓
  IN_SCOPE → Mevcut pipeline (DB kaydı + LangGraph)
  OUT_OF_SCOPE / NEEDS_CLARIFICATION → Pipeline BAŞLAMAZ, DB YAZILMAZ

GÜVENLİK:
  - Kullanıcı girdisi LLM'e prompt injection riski taşır. Bu nedenle:
      * Query, [KULLANICI_SORUSU] etiketi içinde net şekilde izole edilir.
      * Sistem prompt'u, rolü ve çıktı formatını katı biçimde tanımlar.
      * Pydantic ile yapılandırılmış çıktı doğrulanır (serbest metin kabul edilmez).
      * Max token sınırı düşük tutulur (sadece sınıflandırma gerekli).
  - Gemini yoksa: heuristic fallback devreye girer, servis dönmez.
  - Hiçbir koşulda araştırma pipeline'ı başlamadan DB'ye yazılmaz.

HATA TOLERANSI:
  - LLM hatası → Heuristic fallback (kural tabanlı) → pipeline devam eder.
  - Pydantic parse hatası → IN_SCOPE varsayımı → pipeline devam eder.
  - Her iki fallback da loglanır.
==============================================================================
"""

import logging
import re
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field
from core.llm import get_fast_llm
from langchain_core.messages import SystemMessage, HumanMessage

logger = logging.getLogger("ResearchMind.Agents.ScopeGate")


# ─── Veri Modelleri ───────────────────────────────────────────────────────────

class ScopeDecision(str, Enum):
    """Kapsam değerlendirme sonucu."""
    IN_SCOPE            = "IN_SCOPE"
    OUT_OF_SCOPE        = "OUT_OF_SCOPE"
    NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"


class ScopeGateResult(BaseModel):
    """
    Scope Gate'in LLM'den beklediği yapılandırılmış çıktı.
    Pydantic ile doğrulanır — serbest metin asla kabul edilmez.
    """
    decision: ScopeDecision = Field(
        description=(
            "IN_SCOPE: Araştırma görevi, pipeline'a devam et. "
            "OUT_OF_SCOPE: Araştırma görevi değil, reddet. "
            "NEEDS_CLARIFICATION: Hedef belirsiz, soru sor."
        )
    )
    reasoning: str = Field(
        description="Kararın 1-2 cümlelik iç gerekçesi (kullanıcıya gösterilmez, sadece loglanır)",
        max_length=300
    )
    user_message: str = Field(
        description=(
            "Kullanıcıya gösterilecek nazik Türkçe mesaj. "
            "IN_SCOPE ise boş bırak (''). "
            "OUT_OF_SCOPE ise isteğin neden kapsam dışı olduğunu açıkla. "
            "NEEDS_CLARIFICATION ise araştırma hedefini netleştiren TEK bir soru sor."
        ),
        max_length=500
    )


# ─── Sistem Prompt'u ──────────────────────────────────────────────────────────

_SCOPE_GATE_SYSTEM_PROMPT = """Sen ResearchMind sisteminin kapı bekçisisin (Research Scope Gate).
Görevin: Kullanıcının isteğinin kapsamlı akademik/analitik araştırma gerektirip gerektirmediğini değerlendirmek.

## ResearchMind Ne Yapar?
Belirli bir konuda:
- Akademik makaleler, istatistiksel veriler ve çok sayıda web kaynağı tarayarak
- Derin analiz, karşılaştırma, kanıt doğrulama yaparak
- Kapsamlı araştırma raporu üreten bir sistemdir.

## Karar Kuralları

### IN_SCOPE (Araştırmaya Uygun):
- Birden fazla kaynaktan analiz ve sentez gerektiren sorular
- İstatistiksel karşılaştırma, trend analizi, akademik değerlendirme istekleri
- "Karşılaştır", "analiz et", "değerlendir", "araştır", "incele" gibi derinlik ifadeleyen istekler
- Konudan bağımsız: futbol, tıp, yapay zekâ, tarih, ekonomi hepsi olabilir
- Örnekler:
  * "Messi ve Ronaldo'nun kariyer performanslarını akademik ve istatistiksel kaynaklarla karşılaştır."
  * "2020-2024 yılları arasında geliştirilen büyük dil modellerini karşılaştırmalı olarak analiz et."
  * "Kuantum hesaplama'nın kriptografi üzerindeki etkilerini araştır."
  * "Türkiye ekonomisindeki enflasyonun son 5 yıldaki seyrini analiz et."

### OUT_OF_SCOPE (Araştırmaya Uygun Değil):
- Basit bilgi/tanım soruları: "X kimdir?", "Y nedir?", "Z ne anlama gelir?"
- Hesap yapma, kod yazma, çeviri, düzenleme gibi araç görevleri
- Sohbet, şaka, kişisel tavsiye istekleri
- Tek bir gerçek veya veri noktası sorguları
- Örnekler:
  * "Lionel Messi kimdir?"
  * "Python'da liste nasıl oluşturulur?"
  * "Bugün hava nasıl?"
  * "Bana bir şiir yaz."
  * "İstanbul'un nüfusu nedir?"
  * "Bu metni İngilizceye çevir."

### NEEDS_CLARIFICATION (Netleştirme Gerekli):
- Araştırma isteği var gibi görünüyor ama hedef çok belirsiz veya geniş
- Zaman dilimi, kapsam veya karşılaştırma boyutu eksik
- Örnekler:
  * "Messi'nin kariyerini anlat." → Hangi dönem? Hangi metrikler?
  * "Yapay zekâ hakkında araştır." → Hangi aspekt? Hangi uygulama alanı?
  * "İklim değişikliği araştır." → Hangi boyut? Politika mı, bilimsel bulgular mı?

## Çıktı Formatı (KESİNLİKLE UYULMALI)
Aşağıdaki JSON formatında yanıt ver, başka hiçbir şey yazma:
{
  "decision": "IN_SCOPE" | "OUT_OF_SCOPE" | "NEEDS_CLARIFICATION",
  "reasoning": "Kararın kısa iç gerekçesi (kullanıcıya gösterilmez)",
  "user_message": "Kullanıcıya gösterilecek nazik Türkçe mesaj (IN_SCOPE ise boş string)"
}"""

_SCOPE_GATE_USER_TEMPLATE = """Aşağıdaki kullanıcı isteğini değerlendir:

[KULLANICI_SORUSU]
{query}
[/KULLANICI_SORUSU]

Yalnızca belirtilen JSON formatında yanıt ver."""


# ─── Heuristic Fallback ───────────────────────────────────────────────────────

# OUT_OF_SCOPE işaretçi kelime kalıpları (Türkçe + İngilizce)
_OUT_OF_SCOPE_PATTERNS = [
    # Basit kimlik/tanım soruları
    r"^(kim|ne|nedir|kimdir|nerede|kaç|hangi|nasıl\s+yapılır)\b",
    r"^(who is|what is|where is|how to|how do)\b",
    # Çeviri istekleri
    r"\b(çevir|translate|tercüme)\b",
    # Kod yazma
    r"\b(kod\s+yaz|yaz\s+bana|write\s+(a\s+)?(code|script|function|program))\b",
    # Şiir/hikaye
    r"\b(şiir|hikaye|masal|fıkra|poem|story)\s+(yaz|anlat|oluştur)\b",
    # Hava durumu/anlık bilgi
    r"\b(hava|hava\s+durumu|weather|bugün\s+hava)\b",
    # Hesaplama
    r"^\d[\d\s\+\-\*\/\(\)]+[=\?]",
]

_RESEARCH_POSITIVE_PATTERNS = [
    r"\b(karşılaştır|analiz|araştır|incele|değerlendir|compare|analyze|research|investigate|evaluate)\b",
    r"\b(istatistik|performans|trend|etki|impact|effect|benchmark)\b",
    r"\b(akademik|bilimsel|literatür|academic|scientific|literature)\b",
    r"\b(tarihsel|dönem|süreç|historical|period|evolution)\b",
]

_CLARIFICATION_TRIGGERS = [
    r"^(anlat|açıkla|anlatır\s+mısın|explain)\b",
    r"^(hakkında|üzerine|ile\s+ilgili).{0,30}$",  # Çok kısa + "hakkında"
]


def _heuristic_classify(query: str) -> ScopeGateResult:
    """
    Gemini API mevcut olmadığında devreye giren kural tabanlı yedek sınıflandırıcı.
    Pozitif araştırma sinyalleri önceliklidir (false positive'e toleranslı).
    """
    q_lower = query.lower().strip()

    # 1. Araştırma sinyali varsa direkt IN_SCOPE (en güvenli yol)
    for pattern in _RESEARCH_POSITIVE_PATTERNS:
        if re.search(pattern, q_lower):
            logger.debug(f"[Heuristic] Pozitif araştırma sinyali bulundu: {pattern}")
            return ScopeGateResult(
                decision=ScopeDecision.IN_SCOPE,
                reasoning="Heuristic: Araştırma pozitif sinyali tespit edildi.",
                user_message=""
            )

    # 2. Belirgin kapsam dışı kalıplar
    for pattern in _OUT_OF_SCOPE_PATTERNS:
        if re.search(pattern, q_lower):
            logger.debug(f"[Heuristic] OUT_OF_SCOPE kalıbı: {pattern}")
            return ScopeGateResult(
                decision=ScopeDecision.OUT_OF_SCOPE,
                reasoning="Heuristic: Bilinen kapsam dışı kalıp eşleşti.",
                user_message=(
                    "Bu istek ResearchMind'ın kapsamı dışında görünüyor. "
                    "ResearchMind; akademik analiz, istatistiksel karşılaştırma ve derin araştırma "
                    "görevleri için tasarlanmıştır. Basit bilgi soruları, kod yazma veya çeviri "
                    "gibi istekler bu sistemle desteklenmemektedir."
                )
            )

    # 3. Netleştirme gerektiren belirsiz istekler (çok kısa veya hedefsiz)
    word_count = len(q_lower.split())
    if word_count < 6:
        for pattern in _CLARIFICATION_TRIGGERS:
            if re.search(pattern, q_lower):
                return ScopeGateResult(
                    decision=ScopeDecision.NEEDS_CLARIFICATION,
                    reasoning="Heuristic: İstek çok kısa ve araştırma hedefi belirsiz.",
                    user_message=(
                        "Araştırma isteğinizi biraz daha netleştirebilir misiniz? "
                        "Hangi dönem, hangi boyut veya hangi karşılaştırma kriterlerini "
                        "ele almamı istiyorsunuz?"
                    )
                )

    # 4. Belirsiz ama kısa değil → IN_SCOPE varsay (konservatif yaklaşım)
    return ScopeGateResult(
        decision=ScopeDecision.IN_SCOPE,
        reasoning="Heuristic: Belirgin kapsam dışı sinyal yok; IN_SCOPE varsayıldı.",
        user_message=""
    )


# ─── Ana Gate Fonksiyonu ──────────────────────────────────────────────────────

def evaluate_research_scope(
    query: str,
    guidance: Optional[str] = None,
) -> ScopeGateResult:
    """
    Kullanıcının araştırma isteğini değerlendirir ve kapsam kararı döner.

    Bu fonksiyon LangGraph pipeline'ından BAĞIMSIZ çalışır; yalnızca
    POST /api/research endpoint'inde, herhangi bir DB veya LangGraph işlemi
    başlamadan önce çağrılır.

    Öncelik sırası:
      1. Gemini LLM ile yapılandırılmış sınıflandırma (ideal yol)
      2. Pydantic parse hatası → IN_SCOPE fallback (güvenli devam)
      3. Gemini yoksa / hata varsa → Heuristic fallback (kural tabanlı)

    Args:
        query:    Kullanıcının araştırma sorusu.
        guidance: Opsiyonel yönlendirme metni (bağlam için LLM'e verilir).

    Returns:
        ScopeGateResult: Karar + gerekçe + kullanıcı mesajı.

    Raises:
        Hiçbir exception fırlatmaz. Her hata loglanır ve fallback döner.
    """
    if not query or not query.strip():
        return ScopeGateResult(
            decision=ScopeDecision.OUT_OF_SCOPE,
            reasoning="Boş query.",
            user_message="Lütfen bir araştırma sorusu girin."
        )

    # Sorguda prompt injection riski: sisteme komut gibi görünen ifadeler
    # LLM'e gönderilmeden önce izole edilir (köşeli parantez delimiter ile).
    sanitized_query = query.strip()

    try:

        llm = get_fast_llm()

        # Yapılandırılmış çıktı için Pydantic şemasını bağla
        structured_llm = llm.with_structured_output(ScopeGateResult)

        # Kullanıcı metnini sisteme enjekte edilmesini önlemek için
        # şablon içinde açıkça etiketliyoruz
        user_content = _SCOPE_GATE_USER_TEMPLATE.format(
            query=sanitized_query
        )

        # Guidance varsa ek bağlam olarak ekle (sadece bilgi amaçlı)
        if guidance:
            safe_guidance = guidance[:200]  # Uzun guidance'ı kırp
            user_content += f"\n\n[EK YÖNLENDİRME (opsiyonel bağlam)]\n{safe_guidance}"

        messages = [
            SystemMessage(content=_SCOPE_GATE_SYSTEM_PROMPT),
            HumanMessage(content=user_content),
        ]

        result: ScopeGateResult = structured_llm.invoke(messages)

        logger.info(
            f"[ScopeGate] Karar: {result.decision.value} | "
            f"Gerekçe: {result.reasoning[:80]}"
        )
        return result

    except ImportError:
        # LLM modülü yüklü değil (test ortamı vs.)
        logger.debug("[ScopeGate] LLM modülü yüklenemedi → heuristic fallback.")
        return _heuristic_classify(sanitized_query)

    except ValueError as exc:
        # get_fast_llm() → GEMINI_API_KEY eksik
        logger.debug(f"[ScopeGate] API anahtarı eksik → heuristic fallback. ({exc})")
        return _heuristic_classify(sanitized_query)

    except Exception as exc:
        # Ağ hatası (ConnectError, timeout), Pydantic parse hatası veya başka LLM hatası.
        # Sandbox/test ortamı veya geçici ağ sorunu olabilir — debug seviyesinde logla.
        exc_name = type(exc).__name__
        exc_msg  = str(exc)[:120]
        logger.debug(
            f"[ScopeGate] LLM ile sınıflandırma yapılamadı "
            f"({exc_name}: {exc_msg}) → heuristic fallback."
        )
        return _heuristic_classify(sanitized_query)
