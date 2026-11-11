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
from typing import List, Optional
from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage, HumanMessage
from config.settings import get_settings
from core.llm import get_planner_llm
from core.state import SubQuestion, ResearchState

logger = logging.getLogger("ResearchMind.Agents.Planner")


class PlanResponse(BaseModel):
    """
    LLM'den dönecek yapılandırılmış planlama çıktısı.
    """
    rationale: str = Field(description="Araştırma stratejisinin genel mantığı ve kapsam özeti")
    sub_questions: List[SubQuestion] = Field(
        description="Ana soruyu derinlemesine aydınlatacak 3-5 adet alt araştırma sorusu"
    )


PLANNER_SYSTEM_PROMPT = """Sen üst düzey bir Kıdemli Araştırma Mimarı ve Baş Bilim İnsanısın (Research Planner Agent).
Görevin, kullanıcının verdiği karmaşık teknik/akademik araştırma sorusunu veya problemini incelemek ve bunu çok aşamalı, kapsamlı bir araştırma planına dönüştürmektir.

Planlama Kuralları:
1. Soru derin ve kapsamlıysa, konuyu şu ana boyutlara ayır:
   - Temel Mimari Yaklaşımlar & Tasarım Felsefeleri (Architectural Innovations)
   - Eğitim Yöntemleri ve Hizalama Teknikleri (Training, Pretraining, SFT, DPO/RLHF)
   - Kullanılan Veri Kümeleri & Sentetik Veri Yaklaşımları (Datasets & Data Mixtures)
   - Değerlendirme Benchmark'ları ve Karşılaştırmalı Performanslar (Evaluation Metrics & Leaderboards)
   - Sektörel/Akademik Kısıtlar, Çözülmemiş Problemler ve Gelecek Trendleri (Limitations & Open Challenges)

2. Her alt soru için 'target_type' belirle:
   - 'academic': Teori, formülasyon, makale mimarisi, benchmark tabloları için.
   - 'web': Açık kaynak kod depoları, güncel model sürümleri, şirket blogları ve haberler için.
   - 'both': Hem akademik hem pratik doğrulama gerektiren konular için.

3. Her alt soru için 2-3 adet net, İngilizce teknik arama sorgusu (search_queries) oluştur.
   (Akademik veritabanları arXiv ve Semantic Scholar en iyi İngilizce terimlerle sonuç verir.)

4. Alt soru sayısını 3 ile 5 arasında sınırla (kalite ve odaklanma önceliklidir).
"""


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
    API erişimi olmadığında veya hata durumunda deterministik, yüksek kaliteli
    yedek araştırma planı üretir.
    """
    clean_query = query.replace('"', '').strip()
    return [
        SubQuestion(
            id="SQ-1",
            question=f"{clean_query} kapsamındaki temel model mimarileri ve yapısal yaklaşımlar nelerdir?",
            rationale="Konunun mimari temelini ve yeniliklerini kavramak için.",
            target_type="academic",
            search_queries=[
                f"{clean_query} model architecture survey",
                f"{clean_query} novel architecture 2024 2025"
            ],
            status="pending"
        ),
        SubQuestion(
            id="SQ-2",
            question=f"{clean_query} için kullanılan eğitim yöntemleri, aşamaları ve veri kümeleri nelerdir?",
            rationale="Eğitim süreçlerini ve veri hazırlık stratejilerini analiz etmek için.",
            target_type="academic",
            search_queries=[
                f"{clean_query} training methodology pretraining alignment",
                f"{clean_query} dataset benchmark evaluation"
            ],
            status="pending"
        ),
        SubQuestion(
            id="SQ-3",
            question=f"Geliştirilen modellerin performans karşılaştırmaları, avantajları ve kısıtları (limitations) nelerdir?",
            rationale="Farklı yaklaşımların birbirine üstünlüklerini ve açık problemlerini belirlemek için.",
            target_type="both",
            search_queries=[
                f"{clean_query} benchmark comparison performance",
                f"{clean_query} limitations challenges"
            ],
            status="pending"
        )
    ]

