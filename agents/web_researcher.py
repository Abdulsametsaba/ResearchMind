"""
==============================================================================
Dosya: researchmind/agents/web_researcher.py
Görevi: Web Araştırmacı Ajanı (Web Researcher Agent)
==============================================================================
Bu ajan, araştırma planındaki pratik, güncel ve web odaklı alt soruları işler:
1. Tavily AI Search kullanarak teknik blogları, model duyurularını ve
   resmi dökümantasyonları araştırır.
2. Web kaynaklarından gelen gürültüyü (reklamlar, alakasız metinler) filtreler.
3. Her kaynak için temizlenmiş teknik özet ve anlamsal alaka skoru hesaplar.
4. Elde edilen 'WebSource' kayıtlarını LangGraph durumuna aktarır.
==============================================================================
"""

import logging
from typing import List
from researchmind.config.settings import get_settings
from researchmind.core.state import SubQuestion, WebSource, ResearchState
from researchmind.tools.web_search import search_web_tavily

logger = logging.getLogger("ResearchMind.Agents.WebResearcher")


def conduct_web_research(state: ResearchState) -> dict:
    """
    LangGraph düğümü: Alt sorulardan web niteliğinde olanları alır,
    Tavily ile arama yapar ve elde edilen kaynakları state'e ekler.
    """
    sub_questions: List[SubQuestion] = state.get("sub_questions", [])
    settings = get_settings()

    web_sub_qs = [
        sq for sq in sub_questions
        if sq.target_type in ("web", "both")
    ]

    if not web_sub_qs:
        logger.info("Web araştırması yapılacak alt soru bulunamadı.")
        return {"audit_logs": ["[Web Researcher] Taranacak web alt sorusu bulunmadı."]}

    new_web_sources: List[WebSource] = []
    seen_urls = {w.url for w in state.get("web_sources", [])}
    audit_messages = []

    for sq in web_sub_qs:
        logger.info(f"Web alt sorusu işleniyor: [{sq.id}] {sq.question}")
        queries = sq.search_queries or [sq.question]

        for query in queries[:2]:
            found_sources = search_web_tavily(
                query=query,
                max_results=settings.MAX_WEB_SOURCES_PER_SUBQUESTION,
                search_depth="advanced"
            )

            for src in found_sources:
                if src.url not in seen_urls:
                    seen_urls.add(src.url)
                    new_web_sources.append(src)
                    audit_messages.append(f"[Web Researcher] Kaynak eklendi: '{src.title[:50]}...'")

    if not new_web_sources:
        audit_messages.append("[Web Researcher] Tavily API anahtarı girilene kadar web taraması beklemede veya sonuç bulunamadı.")

    return {
        "web_sources": new_web_sources,
        "audit_logs": audit_messages
    }

