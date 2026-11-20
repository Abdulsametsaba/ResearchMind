"""
==============================================================================
Dosya: researchmind/orchestrator/graph.py
Görevi: LangGraph Çok Ajanlı İş Akışı ve Durum Yöneticisi (Supervisor Graph)
==============================================================================
Bu dosya, ResearchMind projesinin tüm uzman ajanlarını tek bir otonom
ve döngüsel (iterative) grafikte birleştirir.

Mimari Akış (Faz-6 ile güncellenmiş):
1. START → planner       : Kullanıcı sorusunu analiz eder, alt sorular üretir.
2. planner → memory_retriever : pgvector'da geçmiş araştırmaları sorgular.
3. memory_retriever → paper_researcher : Akademik makaleleri toplar.
4. paper_researcher → web_researcher  : Web kaynaklarını toplar.
5. web_researcher → analysis          : Karşılaştırmalı analiz yapar.
6. analysis → [Koşullu: should_iterate]:
   - Eksik bilgi + iterasyon < MAX → gap_reframer → paper_researcher döngüsü.
   - Yeterli veya MAX aşıldı       → fact_checker'a ilerler.
7. fact_checker → narrative_agent → report_generator → END.

Faz-6 — Memory Retriever:
  planner'dan gelen alt sorular için pgvector üzerinde semantic search yapılır.
  Bulunan kaynaklar state'e eklenir; Paper Researcher mükerrerları atlar.
  Böylece aynı konuda önceki araştırmalardaki makaleler yeniden indirilmez.
==============================================================================
"""

import logging
from threading import Event, Lock
from datetime import datetime, timezone
from typing import Callable, Literal
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from config.settings import get_settings
from core.state import ResearchState, SubQuestion
from agents.planner import plan_research
from agents.memory_retriever import retrieve_from_memory
from agents.paper_researcher import conduct_paper_research
from agents.web_researcher import conduct_web_research
from agents.analysis_agent import conduct_analysis
from agents.fact_checker import verify_claims
from agents.narrative_agent import generate_research_narrative
from agents.report_agent import generate_research_report

logger = logging.getLogger("ResearchMind.Orchestrator")

_cancellation_events: dict[str, Event] = {}
_closed_cancellations: set[str] = set()
_visible_agent_keys = (
    "planner",
    "paper_researcher",
    "web_researcher",
    "analysis_agent",
    "gap_reframer",
    "fact_checker",
    "report_agent",
)
_agent_progress: dict[str, dict[str, str]] = {}
_agent_events: dict[str, list[dict[str, str | int]]] = {}
_cancellation_lock = Lock()


class ResearchCancelled(Exception):
    """Raised between synchronous graph nodes after a cancellation request."""


def register_cancellation(session_id: str) -> None:
    with _cancellation_lock:
        _closed_cancellations.discard(session_id)
        _cancellation_events[session_id] = Event()
        _agent_progress[session_id] = {
            key: "waiting" for key in _visible_agent_keys
        }
        _agent_events[session_id] = []


def get_agent_progress(session_id: str) -> dict[str, str]:
    with _cancellation_lock:
        return dict(
            _agent_progress.get(
                session_id,
                {key: "waiting" for key in _visible_agent_keys},
            )
        )


def get_agent_events(session_id: str) -> list[dict[str, str | int]]:
    with _cancellation_lock:
        return [dict(event) for event in _agent_events.get(session_id, [])]


def _set_agent_progress(
    session_id: str,
    agent_key: str,
    status: str,
) -> None:
    with _cancellation_lock:
        progress = _agent_progress.get(session_id)
        if progress is None or agent_key not in progress:
            return

        if progress[agent_key] == status:
            return

        progress[agent_key] = status
        events = _agent_events.get(session_id)
        if events is not None:
            events.append({
                "sequence": len(events) + 1,
                "agent_key": agent_key,
                "status": status,
                "occurred_at": datetime.now(timezone.utc).isoformat(),
            })


def request_cancellation(session_id: str) -> bool:
    with _cancellation_lock:
        if session_id in _closed_cancellations:
            return False
        event = _cancellation_events.get(session_id)
        if event is None:
            return False
        event.set()
        return True


def close_cancellation(session_id: str) -> bool:
    with _cancellation_lock:
        _closed_cancellations.add(session_id)
        event = _cancellation_events.get(session_id)
        return event is not None and event.is_set()


def is_cancellation_requested(session_id: str) -> bool:
    with _cancellation_lock:
        event = _cancellation_events.get(session_id)
        return event is not None and event.is_set()


def clear_cancellation(session_id: str) -> None:
    with _cancellation_lock:
        _cancellation_events.pop(session_id, None)
        _closed_cancellations.discard(session_id)
        _agent_progress.pop(session_id, None)
        _agent_events.pop(session_id, None)


def _cancellable(
    node: Callable[[ResearchState], dict],
    agent_key: str | None = None,
    complete_on_exit: bool = True,
) -> Callable:
    def run_node(state: ResearchState, config: RunnableConfig) -> dict:
        session_id = config.get("configurable", {}).get("thread_id")
        if session_id and is_cancellation_requested(session_id):
            raise ResearchCancelled()

        if session_id and agent_key:
            _set_agent_progress(session_id, agent_key, "running")

        try:
            result = node(state)
        except Exception:
            if session_id and agent_key:
                _set_agent_progress(session_id, agent_key, "failed")
            raise

        if session_id and agent_key and complete_on_exit:
            _set_agent_progress(session_id, agent_key, "completed")

        if session_id and is_cancellation_requested(session_id):
            raise ResearchCancelled()
        return result

    return run_node


def gap_reframing_node(state: ResearchState) -> dict:
    """
    İteratif Döngü Düğümü: Analysis Agent tarafından tespit edilen eksik noktaları
    yeni hedeflenmiş 'SubQuestion' nesnelerine dönüştürür ve arama döngüsünü besler.
    """
    iteration = state.get("iteration_count", 0) + 1
    missing_queries = state.get("missing_information_queries", [])
    logger.info(f"[İteratif Döngü] Yeni iterasyon başlatılıyor: {iteration}. Ek sorgular: {missing_queries}")

    existing_sub_questions = state.get("sub_questions", [])
    remaining_capacity = max(
        get_settings().MAX_SUB_QUESTIONS - len(existing_sub_questions),
        0,
    )
    new_sub_questions = []
    for idx, query in enumerate(missing_queries[:remaining_capacity], 1):
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
    has_question_capacity = (
        len(state.get("sub_questions", [])) < settings.MAX_SUB_QUESTIONS
    )
    if (
        not is_sufficient
        and missing_queries
        and has_question_capacity
        and iteration_count < settings.MAX_ITERATIONS
    ):
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
    workflow.add_node(
        "planner",
        _cancellable(plan_research, "planner", complete_on_exit=False),
    )
    workflow.add_node(
        "memory_retriever",
        _cancellable(retrieve_from_memory, "planner"),
    )
    workflow.add_node(
        "paper_researcher",
        _cancellable(conduct_paper_research, "paper_researcher"),
    )
    workflow.add_node(
        "web_researcher",
        _cancellable(conduct_web_research, "web_researcher"),
    )
    workflow.add_node("analysis", _cancellable(conduct_analysis, "analysis_agent"))
    workflow.add_node(
        "gap_reframer",
        _cancellable(gap_reframing_node, "gap_reframer"),
    )
    workflow.add_node("fact_checker", _cancellable(verify_claims, "fact_checker"))
    workflow.add_node(
        "narrative_agent",
        _cancellable(
            generate_research_narrative,
            "report_agent",
            complete_on_exit=False,
        ),
    )
    workflow.add_node(
        "report_generator",
        _cancellable(generate_research_report, "report_agent"),
    )

    # Kenarları Tanımla (Edges)
    workflow.add_edge(START, "planner")
    workflow.add_edge("planner", "memory_retriever")          # Faz-6: planner → memory
    workflow.add_edge("memory_retriever", "paper_researcher") # Faz-6: memory → paper
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

    # Doğrulama → Anlatı Sentezi → Raporlama
    workflow.add_edge("fact_checker", "narrative_agent")
    workflow.add_edge("narrative_agent", "report_generator")
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

