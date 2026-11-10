"""
==============================================================================
Dosya: ResearchMind/tools/web_search.py
Görevi: Tavily AI Web Arama ve İçerik Toplama Aracı
==============================================================================
Bu araç, internet üzerindeki en güncel teknik blogları, resmi dökümantasyonları,
benchmark duyurularını ve GitHub reposu/teknik rapor sayfalarını aramak için
Tavily Search API'ını kullanır.

Arama sonuçlarını temizleyerek sistemin ortak 'WebSource' şemasına dönüştürür.
API anahtarı eksik olduğunda çökmek yerine kullanıcıyı net şekilde uyarır.
==============================================================================
"""

import logging
from typing import List, Optional
from tavily import TavilyClient
from ResearchMind.config.settings import get_settings
from ResearchMind.core.state import WebSource

logger = logging.getLogger("ResearchMind.Tools.WebSearch")


def search_web_tavily(
    query: str,
    max_results: int = 4,
    search_depth: str = "advanced"
) -> List[WebSource]:
    """
    Tavily AI Search motorunu kullanarak derin web araması yapar.

    Args:
        query: Aranacak soru veya teknik terim
        max_results: Getirilecek maksimum web kaynağı sayısı
        search_depth: 'basic' (hızlı) veya 'advanced' (derin teknik arama)

    Returns:
        List[WebSource] listesi
    """
    settings = get_settings()
    api_key = settings.TAVILY_API_KEY

    # API Anahtarı kontrolü
    if not api_key or api_key.startswith("buraya_"):
        logger.warning(
            "[UYARI] TAVILY_API_KEY tanımlanmamış veya varsayılan değerde! "
            "Web araması atlanıyor. Lütfen .env dosyasına Tavily API anahtarınızı girin."
        )
        return []

    results: List[WebSource] = []

    try:
        client = TavilyClient(api_key=api_key)
        response = client.search(
            query=query,
            search_depth=search_depth,
            max_results=max_results,
            include_answer=False,
            include_raw_content=False
        )

        raw_results = response.get("results", [])
        for item in raw_results:
            title = item.get("title", "Web Kaynağı")
            url = item.get("url", "")
            snippet = item.get("content", "")
            score = float(item.get("score", 0.85))

            source = WebSource(
                url=url,
                title=title.strip(),
                snippet=snippet.strip(),
                full_content=snippet.strip(),
                relevance_score=score
            )
            results.append(source)

        logger.info(f"Tavily web araması tamamlandı: {len(results)} kaynak bulundu.")
    except Exception as e:
        logger.error(f"Tavily web araması sırasında hata oluştu: {e}")

    return results

