"""
==============================================================================
Görevi: ResearchMind Ana Çalıştırma ve Komut Satırı Arayüzü (CLI Entrypoint)
==============================================================================
Bu dosya, ResearchMind otonom araştırma sistemini komut satırından tetikler.
Kullanıcıdan araştırma sorusunu alır, LangGraph ajan grafiğini çalıştırır,
adımları canlı olarak konsolda raporlar ve üretilen nihai raporu hem ekranda
gösterir hem de 'data/reports/' dizinine Markdown olarak kaydeder.
==============================================================================
"""

import sys
import os
import uuid
import datetime
from typing import Optional
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

# Proje kök dizinini ekle
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config.settings import get_settings
from core.state import ResearchState
from orchestrator.graph import get_research_graph

console = Console()


def run_research(query: str, guidance: Optional[str] = None) -> ResearchState:
    """
    Belirtilen araştırma sorusu için ResearchMind çok ajanlı iş akışını yürütür.

    Args:
        query: Kullanıcının araştırma problemi / sorusu
        guidance: Opsiyonel ek kullanıcı yönlendirmeleri

    Returns:
        Tamamlanmış ResearchState nesnesi
    """
    settings = get_settings()
    graph = get_research_graph()

    session_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": session_id}}

    initial_state: ResearchState = {
        "research_query": query,
        "user_guidance": guidance,
        "sub_questions": [],
        "current_subquestion_index": 0,
        "academic_sources": [],
        "web_sources": [],
        "analysis_summary": "",
        "comparative_data": {},
        "claim_verifications": [],
        "iteration_count": 0,
        "missing_information_queries": [],
        "is_research_sufficient": False,
        "final_report": None,
        "audit_logs": [f"[Session] Araştırma oturumu başlatıldı ({session_id[:8]})."]
    }

    console.print(Panel(
        f"[bold cyan]Araştırma Sorusu:[/bold cyan] {query}\n"
        f"[bold green]Model:[/bold green] {settings.GEMINI_MODEL_PLANNER} | "
        f"[bold green]Oturum:[/bold green] {session_id[:8]}",
        title="🔬 ResearchMind Otonom Derin Araştırma",
        border_style="cyan"
    ))

    # Grafiği çalıştır
    with console.status("[bold yellow]Ajanlar çalışıyor (Planner -> Researchers -> Analysis -> Fact Checker -> Report)...[/bold yellow]"):
        final_state = graph.invoke(initial_state, config=config)

    # Raporu Ekrana Bas
    report = final_state.get("final_report")
    if report:
        console.print("\n")
        console.print(Panel(f"[bold green]{report.title}[/bold green]", border_style="green"))

        console.print("\n[bold yellow]📌 Yönetici Özeti:[/bold yellow]")
        console.print(report.executive_summary)

        if report.comparative_analysis_markdown:
            console.print("\n[bold yellow]📊 Karşılaştırmalı Analiz Tablosu:[/bold yellow]")
            console.print(Markdown(report.comparative_analysis_markdown))

        if report.verification_matrix_markdown:
            console.print("\n[bold yellow]🛡️ Kanıt Doğrulama Matrisi (Fact-Checking):[/bold yellow]")
            console.print(Markdown(report.verification_matrix_markdown))

        # Raporu diske kaydet
        reports_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "reports")
        os.makedirs(reports_dir, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        report_filename = f"report_{timestamp}.md"
        report_path = os.path.join(reports_dir, report_filename)

        with open(report_path, "w", encoding="utf-8") as f:
            f.write(f"# {report.title}\n\n")
            f.write(f"**Araştırma Sorusu:** {query}\n\n")
            f.write(f"**Tarih:** {datetime.datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n")
            f.write(f"## Yönetici Özeti\n{report.executive_summary}\n\n")

            for sec in report.sections:
                f.write(f"## {sec['heading']}\n{sec['content']}\n\n")

            if report.comparative_analysis_markdown:
                f.write(f"## Karşılaştırmalı Analiz\n{report.comparative_analysis_markdown}\n\n")

            if report.verification_matrix_markdown:
                f.write(f"## Kanıta Dayalı Doğrulama Matrisi\n{report.verification_matrix_markdown}\n\n")

            f.write(f"## Kısıtlar ve Gelecek Trendleri\n{report.limitations_and_future_directions}\n\n")

            f.write("## Kaynakça\n")
            for b in report.bibliography:
                f.write(f"- {b['citation']}\n")

        console.print(f"\n[bold green]✓ Rapor başarıyla diske kaydedildi:[/bold green] {report_path}")

    return final_state


if __name__ == "__main__":
    default_query = (
        "2023-2026 yılları arasında geliştirilen Vision-Language modellerini araştır. "
        "Mimari yaklaşımlarını, eğitim yöntemlerini, performanslarını ve birbirlerine göre avantajlarını karşılaştır."
    )
    user_query = sys.argv[1] if len(sys.argv) > 1 else default_query
    run_research(user_query)

