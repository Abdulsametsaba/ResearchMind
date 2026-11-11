"""
==============================================================================
Görevi: LangGraph Çok Ajanlı İş Akışı ve Durum Yöneticisi (Supervisor Graph)
==============================================================================
Bu dosya, ResearchMind projesinin tüm uzman ajanlarını (Planner, Paper Researcher,
Web Researcher, Analysis Agent, Fact Checker, Report Agent) tek bir otonom
ve döngüsel (iterative) grafikte birleştirir.

Mimari Akış:
1. START -> planner: Kullanıcı sorusunu analiz eder ve alt sorular üretir.
2. planner -> paper_researcher: Akademik makaleleri ve PDF zekasını toplar.
3. paper_researcher -> web_researcher: Web kaynaklarını toplar ve filtreler.
4. web_researcher -> analysis: Karşılaştırmalı analiz yapar ve eksiklikleri değerlendirir.
5. analysis -> [Koşullu Kenar: should_iterate]:
   - Eksik bilgi var ve MAX_ITERATIONS aşılmadıysa: gap_reframer -> paper_researcher döngüsü.
   - Araştırma yeterliyse: fact_checker'a ilerler.
6. fact_checker -> report_generator: İddiaları doğrular ve nihai raporu derler.
7. report_generator -> END.

LangGraph MemorySaver / Postgres Checkpointer ile durum kalıcılığı sağlanır.
==============================================================================
"""

import logging
from typing import Literal
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from config.settings import get_settings
from core.state import ResearchState, SubQuestion
from agents.planner import plan_research
from agents.paper_researcher import conduct_paper_research
from agents.web_researcher import conduct_web_research
from agents.analysis_agent import conduct_analysis
from agents.fact_checker import verify_claims
from agents.report_agent import generate_research_report

logger = logging.getLogger("ResearchMind.Orchestrator")


def gap_reframing_node(state: ResearchState) -> dict:
    """
    İteratif Döngü Düğümü: Analysis Agent tarafından tespit edilen eksik noktaları
    yeni hedeflenmiş 'SubQuestion' nesnelerine dönüştürür ve arama döngüsünü besler.
    """
    iteration = state.get("iteration_count", 0) + 1
    missing_queries = state.get("missing_information_queries", [])
    logger.info(f"[İteratif Döngü] Yeni iterasyon başlatılıyor: {iteration}. Ek sorgular: {missing_queries}")

    new_sub_questions = []
    for idx, query in enumerate(missing_queries, 1):
        sq = SubQuestion(
            id=f"ITER-{iteration}-SQ-{idx}",
            question=f"Eksik Bilgi Araştırması: {query}",
            rationale="Önceki araştırma aşamasında tespit edilen bilgi boşluğunu kapatmak için.",
            target_type="both",
            search_queries=[query],
            status="pending"
        )
        new_sub_questions.append(sq)

    return {
        "iteration_count": iteration,
        "sub_questions": state.get("sub_questions", []) + new_sub_questions,
        "missing_information_queries": [],
        "audit_logs": [f"[Iterative Loop] İterasyon {iteration}: {len(new_sub_questions)} yeni odaklı alt soru grafiğe eklendi."]
    }


def should_iterate(state: ResearchState) -> Literal["iterate", "finalize"]:
    """
    Koşullu Yönlendirici: Analiz tamamlandıktan sonra ek araştırma döngüsüne
    girilip girilmeyeceğine veya raporlama aşamasına geçileceğine karar verir.
    """
    settings = get_settings()
    is_sufficient = state.get("is_research_sufficient", True)
    iteration_count = state.get("iteration_count", 0)
    missing_queries = state.get("missing_information_queries", [])

    # Eğer yeterli değilse, ek sorgu varsa ve maksimum limit aşılmadıysa tekrar araştır
    if not is_sufficient and missing_queries and (iteration_count < settings.MAX_ITERATIONS):
        logger.info(f"Yetersiz kanıt tespit edildi. İteratif döngüye geçiliyor (Mevcut: {iteration_count}, Maks: {settings.MAX_ITERATIONS})")
        return "iterate"

    logger.info("Araştırma yeterli bulundu veya maksimum iterasyona ulaşıldı. Doğrulama katmanına geçiliyor.")
    return "finalize"


def build_researchmind_graph():
    """
    ResearchMind çok ajanlı durum grafiğini inşa eder ve derler.

    Returns:
        Compiled StateGraph nesnesi
    """
    workflow = StateGraph(ResearchState)

    # Düğümleri Ekle (Nodes)
    workflow.add_node("planner", plan_research)
    workflow.add_node("paper_researcher", conduct_paper_research)
    workflow.add_node("web_researcher", conduct_web_research)
    workflow.add_node("analysis", conduct_analysis)
    workflow.add_node("gap_reframer", gap_reframing_node)
    workflow.add_node("fact_checker", verify_claims)
    workflow.add_node("report_generator", generate_research_report)

    # Kenarları Tanımla (Edges)
    workflow.add_edge(START, "planner")
    workflow.add_edge("planner", "paper_researcher")
    workflow.add_edge("paper_researcher", "web_researcher")
    workflow.add_edge("web_researcher", "analysis")

    # İteratif Koşullu Yönlendirme (Adaptive & Iterative Loop)
    workflow.add_conditional_edges(
        "analysis",
        should_iterate,
        {
            "iterate": "gap_reframer",
            "finalize": "fact_checker"
        }
    )
    workflow.add_edge("gap_reframer", "paper_researcher")

    # Doğrulama ve Raporlama
    workflow.add_edge("fact_checker", "report_generator")
    workflow.add_edge("report_generator", END)

    # Durum Hafızası (Memory Checkpointer)
    checkpointer = MemorySaver()
    compiled_graph = workflow.compile(checkpointer=checkpointer)

    return compiled_graph


# Singleton derlenmiş grafik örneği
_research_graph = None

def get_research_graph():
    """Derlenmiş LangGraph grafiğini döndürür."""
    global _research_graph
    if _research_graph is None:
        _research_graph = build_researchmind_graph()
    return _research_graph

