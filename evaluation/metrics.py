"""
==============================================================================
Dosya: researchmind/evaluation/metrics.py
Görevi: Araştırma Kalitesi Değerlendirme Metrikleri Hesaplayıcısı
==============================================================================
Bu modül, ResearchMind'ın ürettiği araştırmaları nesnel metriklerle
değerlendiren fonksiyonları içerir.

Hesaplanan Metrikler:
  1. research_coverage_score   — Alt soruların ne kadarının yanıtlandığı
  2. citation_accuracy_score   — Ağırlıklı iddia doğrulama doğruluğu
  3. source_quality_score      — Kaynakların ortalama ilgililik skoru
  4. factual_consistency_score — VERIFIED iddia oranı
  5. retrieval_recall          — Hedeflenen vs bulunan kaynak oranı
  6. research_completion_rate  — Raporun tamamlanma oranı
  7. overall_score             — Ağırlıklı genel puan

Kullanım Alanı:
  - GET /api/research/{id}/metrics endpoint'i
  - Faz-4 Evaluation: Baseline RAG vs ResearchMind benchmark karşılaştırması
==============================================================================
"""

import logging
from typing import Any, Dict, List

from api.schemas import EvaluationMetrics
from core.state import (
    AcademicPaperSource,
    ClaimVerification,
    WebSource,
    SubQuestion,
)

from config.settings import get_settings

logger = logging.getLogger("ResearchMind.Evaluation.Metrics")

# Metrik ağırlıkları (toplam = 1.0)
METRIC_WEIGHTS = {
    "research_coverage": 0.25,
    "citation_accuracy": 0.25,
    "source_quality": 0.15,
    "factual_consistency": 0.25,
    "retrieval_recall": 0.10,
}


def calculate_research_coverage(
    sub_questions: List[SubQuestion],
    papers: List[AcademicPaperSource],
    web_sources: List[WebSource],
) -> float:
    """
    Araştırma sorusunun ne kadarının cevaplandığını hesaplar.

    Yöntem:
      - Her 'completed' alt soru için bu alt soruya kaynak bulundu mu kontrol edilir.
      - Toplam tamamlanan / toplam alt soru oranı döndürülür.
    """
    if not sub_questions:
        return 0.5  # Alt soru yoksa varsayılan orta değer

    completed = [sq for sq in sub_questions if sq.status == "completed"]
    total = len(sub_questions)

    # Kaynak bulundu mu ayrıca değerlendir
    has_academic = len(papers) > 0
    has_web = len(web_sources) > 0
    source_bonus = 0.1 if has_academic else 0.0
    source_bonus += 0.05 if has_web else 0.0

    base_score = len(completed) / total if total > 0 else 0.0
    return min(1.0, base_score + source_bonus)


def calculate_citation_accuracy(verifications: List[ClaimVerification]) -> float:
    """
    İddiaların kaynaklarla örtüşme doğruluğunu hesaplar.

    Yöntem:
      - VERIFIED: 1.0 puan × confidence_score
      - PARTIALLY_VERIFIED: 0.8 puan × confidence_score (belirli koşulda teyit)
      - NEEDS_VERIFICATION: 0.5 puan × confidence_score
      - INSUFFICIENT_EVIDENCE: 0.4 puan × confidence_score
      - CONTRADICTED: 0.0 puan
    """
    if not verifications:
        return 0.0

    total_weighted = 0.0
    for v in verifications:
        if v.verification_status == "VERIFIED":
            total_weighted += 1.0 * v.confidence_score
        elif v.verification_status == "PARTIALLY_VERIFIED":
            total_weighted += 0.8 * v.confidence_score
        elif v.verification_status == "NEEDS_VERIFICATION":
            total_weighted += 0.5 * v.confidence_score
        elif v.verification_status == "INSUFFICIENT_EVIDENCE":
            total_weighted += 0.4 * v.confidence_score
        # CONTRADICTED = 0

    return min(1.0, total_weighted / len(verifications))


def calculate_source_quality(
    papers: List[AcademicPaperSource],
    web_sources: List[WebSource],
) -> float:
    """
    Kaynakların ortalama ilgililik (relevance) skorunu hesaplar.
    Akademik kaynaklar web kaynaklarına göre 1.5× ağırlıklıdır.
    """
    total_score = 0.0
    total_weight = 0.0

    for p in papers:
        total_score += p.relevance_score * 1.5
        total_weight += 1.5

    for w in web_sources:
        total_score += w.relevance_score * 1.0
        total_weight += 1.0

    if total_weight == 0:
        return 0.0

    return min(1.0, total_score / total_weight)


def calculate_factual_consistency(verifications: List[ClaimVerification]) -> float:
    """
    VERIFIED ve PARTIALLY_VERIFIED iddia oranını hesaplar.
    Bu metrik halüsinasyon ve yanlış atıf riskini gösterir.
    """
    if not verifications:
        return 0.0

    verified_count = sum(
        1.0 if v.verification_status == "VERIFIED"
        else 0.8 if v.verification_status == "PARTIALLY_VERIFIED"
        else 0.0
        for v in verifications
    )
    return min(1.0, verified_count / len(verifications))


def calculate_retrieval_recall(
    sub_questions: List[SubQuestion],
    papers: List[AcademicPaperSource],
    web_sources: List[WebSource],
    settings_max_papers: int = 3,
    settings_max_web: int = 4,
) -> float:
    """
    Teorik maksimum kaynak sayısına karşı gerçekte bulunan oranı hesaplar.

    Teorik Maksimum = (akademik alt soru × papers_per_sq) + (web alt soru × web_per_sq)
    """
    academic_sqs = [sq for sq in sub_questions if sq.target_type in ("academic", "both")]
    web_sqs = [sq for sq in sub_questions if sq.target_type in ("web", "both")]

    max_papers = len(academic_sqs) * settings_max_papers
    max_web = len(web_sqs) * settings_max_web
    theoretical_max = max_papers + max_web

    if theoretical_max == 0:
        return 0.5

    actual = len(papers) + len(web_sources)
    return min(1.0, actual / theoretical_max)


def calculate_completion_rate(state: Dict[str, Any]) -> float:
    """
    Araştırmanın tamamlanma oranını hesaplar.
    Rapor üretilmişse 1.0, üretilmemişse ara adımlara göre hesaplanır.
    """
    has_report = bool(state.get("final_report"))
    if has_report:
        return 1.0

    # Ara adımların tamamlanma kontrolü
    score = 0.0
    if state.get("sub_questions"):
        score += 0.2
    if state.get("academic_sources"):
        score += 0.2
    if state.get("analysis_summary"):
        score += 0.2
    if state.get("claim_verifications"):
        score += 0.2
    if state.get("research_narrative"):
        score += 0.1

    return score


def calculate_research_metrics(session_id: str, state: Dict[str, Any]) -> EvaluationMetrics:
    """
    ResearchState'ten tüm kalite metriklerini hesaplar ve
    EvaluationMetrics nesnesi olarak döndürür.

    Args:
        session_id: Araştırma oturumu kimliği
        state: Tamamlanmış LangGraph ResearchState sözlüğü

    Returns:
        Hesaplanmış EvaluationMetrics nesnesi
    """

    settings = get_settings()

    sub_questions: List[SubQuestion] = state.get("sub_questions", [])
    papers: List[AcademicPaperSource] = state.get("academic_sources", [])
    web_sources: List[WebSource] = state.get("web_sources", [])
    verifications: List[ClaimVerification] = state.get("claim_verifications", [])
    iteration_count: int = state.get("iteration_count", 0)

    # Bireysel metrikleri hesapla
    coverage = calculate_research_coverage(sub_questions, papers, web_sources)
    citation_acc = calculate_citation_accuracy(verifications)
    source_qual = calculate_source_quality(papers, web_sources)
    factual_con = calculate_factual_consistency(verifications)
    recall = calculate_retrieval_recall(
        sub_questions, papers, web_sources,
        settings_max_papers=settings.MAX_PAPERS_PER_SUBQUESTION,
        settings_max_web=settings.MAX_WEB_SOURCES_PER_SUBQUESTION,
    )
    completion = calculate_completion_rate(state)

    # Ağırlıklı genel skor
    overall = (
        coverage * METRIC_WEIGHTS["research_coverage"] +
        citation_acc * METRIC_WEIGHTS["citation_accuracy"] +
        source_qual * METRIC_WEIGHTS["source_quality"] +
        factual_con * METRIC_WEIGHTS["factual_consistency"] +
        recall * METRIC_WEIGHTS["retrieval_recall"]
    )

    logger.info(
        f"[Metrics] Oturum {session_id[:8]} | "
        f"Coverage={coverage:.2f}, CitAcc={citation_acc:.2f}, "
        f"SrcQuality={source_qual:.2f}, FactCons={factual_con:.2f}, "
        f"Recall={recall:.2f}, Overall={overall:.2f}"
    )

    return EvaluationMetrics(
        session_id=session_id,
        research_coverage_score=round(coverage, 4),
        citation_accuracy_score=round(citation_acc, 4),
        source_quality_score=round(source_qual, 4),
        factual_consistency_score=round(factual_con, 4),
        retrieval_recall=round(recall, 4),
        research_completion_rate=round(completion, 4),
        total_sources=len(papers) + len(web_sources),
        total_claims_verified=sum(1 for v in verifications if v.verification_status == "VERIFIED"),
        iteration_count=iteration_count,
        overall_score=round(overall, 4),
    )

