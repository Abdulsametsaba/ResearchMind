"""
==============================================================================
Görevi: Araştırma Planlayıcı Ajan (Research Planner Agent)
==============================================================================
Bu ajan, kullanıcının girdiği karmaşık araştırma sorusunu analiz eder ve
kapsamlı bir araştırma stratejisi kurgular.

İşlevleri:
1. Ana soruyu mantıksal ve teknik alt araştırma boyutlarına ayrıştırır
   (Mimari, Eğitim Metodolojisi, Veri Kümeleri, Benchmark Performansları, Kısıtlar vb.).
2. Her alt konu için hedefin akademik makale mi ('academic'), web kaynakları mı ('web'),
   yoksa her ikisi mi ('both') olduğunu belirler.
3. Akademik arama motorları ve web arama API'ları için optimize edilmiş,
   yüksek hedefli arama anahtar kelimeleri (search_queries) üretir.
4. LangGraph durum nesnesine (ResearchState) güncellenmiş alt soruları yazar.
==============================================================================
"""

import logging
from typing import List
from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage, HumanMessage
from config.settings import get_settings
from core.llm import get_planner_llm
from core.state import SubQuestion, ResearchState
from prompts.planner_agent import create_planner_prompt

logger = logging.getLogger("ResearchMind.Agents.Planner")


class PlanResponse(BaseModel):
    rationale: str = Field(description="Araştırma stratejisinin genel mantığı ve kapsam özeti")
    sub_questions: List[SubQuestion] = Field(
        description="Ana soruyu derinlemesine aydınlatacak 3-5 adet alt araştırma sorusu"
    )

def plan_research(state: ResearchState) -> dict:
    """
    LangGraph düğümü: Araştırma durumunu alır, planlama yapar ve sub_questions listesini döner.

    Args:
        state: Mevcut ResearchState

    Returns:
        Durum güncelleme sözlüğü: {"sub_questions": [...], "audit_logs": [...]}
    """
    query = state.get("research_query", "")
    guidance = state.get("user_guidance")
    settings = get_settings()

    PLANNER_SYSTEM_PROMPT = create_planner_prompt()

    logger.info(f"Planner Agent çalıştırılıyor. Ana Soru: '{query}'")

    # API Anahtarı tanımlı mı kontrol et
    api_key = settings.GEMINI_API_KEY
    if not api_key or api_key.startswith("buraya_"):
        logger.warning("GEMINI_API_KEY tanımlanmamış, kural tabanlı varsayılan plan devreye sokuluyor.")
        default_sub_questions = generate_heuristic_plan(query)
        return {
            "sub_questions": default_sub_questions,
            "current_subquestion_index": 0,
            "audit_logs": ["[Planner] API anahtarı olmadığı için kural tabanlı araştırma planı oluşturuldu."]
        }

    try:
        llm = get_planner_llm()
        structured_llm = llm.with_structured_output(PlanResponse)

        user_content = f"Ana Araştırma Sorusu: {query}"
        if guidance:
            user_content += f"\n\nKullanıcı Özel Direktifleri: {guidance}"

        response: PlanResponse = structured_llm.invoke([
            SystemMessage(content=PLANNER_SYSTEM_PROMPT),
            HumanMessage(content=user_content)
        ])

        sub_qs = response.sub_questions
        # ID'lerin SQ-1, SQ-2 şeklinde sıralı olduğundan emin ol
        for idx, sq in enumerate(sub_qs, 1):
            if not sq.id or sq.id == "string":
                sq.id = f"SQ-{idx}"

        logger.info(f"Planner Agent başarıyla {len(sub_qs)} alt soru üretti.")
        return {
            "sub_questions": sub_qs,
            "current_subquestion_index": 0,
            "audit_logs": [f"[Planner] {len(sub_qs)} alt araştırma konusu ve arama stratejisi belirlendi."]
        }

    except Exception as e:
        logger.error(f"Planner Agent çalışırken hata oluştu: {e}. Heuristic plana geçiliyor.")
        fallback_sub_questions = generate_heuristic_plan(query)
        return {
            "sub_questions": fallback_sub_questions,
            "current_subquestion_index": 0,
            "audit_logs": [f"[Planner] LLM çağrısında hata ({type(e).__name__}); yedek plan devreye alındı."]
        }


def generate_heuristic_plan(query: str) -> List[SubQuestion]:
    """
    API erişimi olmadığında veya hata durumunda deterministik, konuya duyarlı
    ve yüksek kaliteli yedek araştırma planı üretir.
    """
    clean_query = query.replace('"', '').strip()
    lower_q = clean_query.lower()

    # Kriptografi / Güvenlik / Post-Quantum kontrolü
    is_crypto = any(k in lower_q for k in [
        "kem", "dsa", "fips", "post-quantum", "kuantum", "rsa", "ecc",
        "kripto", "lattice", "kyber", "dilithium", "sphincs", "security"
    ])

    if is_crypto:
        return [
            SubQuestion(
                id="SQ-1",
                question=f"{clean_query} kapsamında temel standartlar, matematiksel temeller ve kriptografik ilkeller (KEM vs İmza) nelerdir?",
                rationale="FIPS 203/204 gibi standartların ve algoritmik temellerin rolünü belirlemek için.",
                target_type="academic",
                search_queries=[
                    f"{clean_query} NIST FIPS standards specifications",
                    f"{clean_query} lattice-based cryptography foundations"
                ],
                status="pending"
            ),
            SubQuestion(
                id="SQ-2",
                question=f"{clean_query} için güvenlik kategorileri (NIST Levels 1-5), anahtar/imza boyutları ve performans metrikleri nelerdir?",
                rationale="Farklı algoritmaların parametre ve güvenlik eşdeğerliklerini somut verilerle kıyaslamak için.",
                target_type="both",
                search_queries=[
                    f"{clean_query} key size ciphertext benchmark performance",
                    f"{clean_query} NIST security category comparison"
                ],
                status="pending"
            ),
            SubQuestion(
                id="SQ-3",
                question=f"{clean_query} için yan kanal (SCA) ve hata enjeksiyonu (FIA) saldırı modelleri, kısıtlar ve savunma mekanizmaları nelerdir?",
                rationale="Pratik donanım/yazılım uygulama açıklarını ve koruma yöntemlerini netleştirmek için.",
                target_type="both",
                search_queries=[
                    f"{clean_query} side-channel fault injection attack vulnerabilities",
                    f"{clean_query} practical implementation limitations"
                ],
                status="pending"
            )
        ]

    # Genel Bilimsel / Teknik Plan
    return [
        SubQuestion(
            id="SQ-1",
            question=f"{clean_query} kapsamındaki temel mimari yaklaşımlar, algoritmalar ve tasarım ilkeleri nelerdir?",
            rationale="Konunun teorik ve yapısal temellerini kavramak için.",
            target_type="academic",
            search_queries=[
                f"{clean_query} architecture mechanism survey",
                f"{clean_query} fundamental algorithms specifications"
            ],
            status="pending"
        ),
        SubQuestion(
            id="SQ-2",
            question=f"{clean_query} için uygulanan metodolojiler, deneysel protokoller ve değerlendirme kriterleri nelerdir?",
            rationale="Süreç tasarımını ve deneysel yöntemleri analiz etmek için.",
            target_type="academic",
            search_queries=[
                f"{clean_query} methodology experimental protocols",
                f"{clean_query} benchmark evaluation metrics"
            ],
            status="pending"
        ),
        SubQuestion(
            id="SQ-3",
            question=f"{clean_query} alanındaki yaklaşımların nicel performans karşılaştırmaları, avantajları ve kısıtları (limitations) nelerdir?",
            rationale="Farklı çözümlerin üstünlüklerini, darboğazlarını ve açık araştırma sorularını belirlemek için.",
            target_type="both",
            search_queries=[
                f"{clean_query} quantitative comparison performance",
                f"{clean_query} limitations open challenges"
            ],
            status="pending"
        )
    ]

