"""
==============================================================================
Dosya: researchmind/tools/academic_search.py
Görevi: Akademik Makale Tarama ve Meta Veri Çıkarma Aracı
==============================================================================
Bu araç, akademik derin araştırmanın temelini oluşturur.
arXiv API ve Semantic Scholar REST API'larını kullanarak:
- Verilen arama sorgularına göre en alakalı akademik makaleleri listeler.
- Başlık, yazarlar, yayın yılı, özet (abstract), arXiv ID ve PDF indirme bağlantısını
  ayrıştırır.
- Çıktıyı sistemin ortak veri şeması olan 'AcademicPaperSource' nesnelerine dönüştürür.
API anahtarı olmasa dahi arXiv API üzerinden ücretsiz ve sınırsız sorgulama yapılabilir.
==============================================================================
"""

import logging
from typing import List, Optional
import arxiv
import httpx
from ResearchMind.config.settings import get_settings
from ResearchMind.core.state import AcademicPaperSource

logger = logging.getLogger("ResearchMind.Tools.AcademicSearch")


def search_arxiv(
    query: str,
    max_results: int = 4,
    sort_by: arxiv.SortCriterion = arxiv.SortCriterion.Relevance
) -> List[AcademicPaperSource]:
    """
    arXiv API üzerinden verilen sorguya ilişkin en alakalı akademik makaleleri arar.

    Args:
        query: Arama terimi (örn. 'vision language models architecture benchmark')
        max_results: Getirilecek maksimum makale sayısı
        sort_by: Sıralama kriteri (Relevance veya SubmittedDate)

    Returns:
        List[AcademicPaperSource] listesi
    """
    settings = get_settings()
    results: List[AcademicPaperSource] = []

    logger.info(f"arXiv araması başlatılıyor: '{query}' (limit: {max_results})")

    try:
        # arXiv İstemcisi yapılandırması (sayfa boyutu ve gecikme ayarlı)
        client = arxiv.Client(
            page_size=max_results,
            delay_seconds=1.5,
            num_retries=3
        )

        search = arxiv.Search(
            query=query,
            max_results=max_results,
            sort_by=sort_by
        )

        for paper in client.results(search):
            paper_id = paper.entry_id.split("/")[-1] # örn. 2401.12345v1 -> 2401.12345v1
            year = str(paper.published.year) if paper.published else None
            author_names = [author.name for author in paper.authors]

            source = AcademicPaperSource(
                id=f"arxiv:{paper_id}",
                title=paper.title.strip().replace("\n", " "),
                authors=author_names,
                published_year=year,
                url=paper.entry_id,
                pdf_url=paper.pdf_url,
                abstract=paper.summary.strip().replace("\n", " "),
                extracted_intel=None,
                relevance_score=0.9  # arXiv relevance varsayılan skoru
            )
            results.append(source)

        logger.info(f"arXiv araması tamamlandı. {len(results)} makale bulundu.")
    except Exception as e:
        logger.error(f"arXiv araması sırasında hata oluştu: {e}")

    return results


def search_semantic_scholar(
    query: str,
    max_results: int = 3
) -> List[AcademicPaperSource]:
    """
    Semantic Scholar Graph API üzerinden akademik makale araması yapar.
    Varsa SEMANTIC_SCHOLAR_API_KEY kullanılır, yoksa genel kota üzerinden sorgu atılır.

    Args:
        query: Arama sorgusu
        max_results: Maksimum sonuç sayısı

    Returns:
        List[AcademicPaperSource]
    """
    settings = get_settings()
    results: List[AcademicPaperSource] = []
    endpoint = "https://api.semanticscholar.org/graph/v1/paper/search"

    headers = {}
    if settings.SEMANTIC_SCHOLAR_API_KEY:
        headers["x-api-key"] = settings.SEMANTIC_SCHOLAR_API_KEY

    params = {
        "query": query,
        "limit": max_results,
        "fields": "title,authors,year,abstract,openAccessPdf,url"
    }

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(endpoint, params=params, headers=headers)
            if response.status_code == 200:
                data = response.json()
                for item in data.get("data", []):
                    title = item.get("title", "İsimsiz Makale")
                    abstract = item.get("abstract") or "Özet metin bulunamadı."
                    year = str(item.get("year")) if item.get("year") else None
                    authors = [a.get("name") for a in item.get("authors", []) if a.get("name")]
                    pdf_info = item.get("openAccessPdf") or {}
                    pdf_url = pdf_info.get("url")
                    paper_id = item.get("paperId", "unknown")

                    source = AcademicPaperSource(
                        id=f"s2:{paper_id[:12]}",
                        title=title.strip(),
                        authors=authors,
                        published_year=year,
                        url=item.get("url") or f"https://www.semanticscholar.org/paper/{paper_id}",
                        pdf_url=pdf_url,
                        abstract=abstract.strip(),
                        extracted_intel=None,
                        relevance_score=0.88
                    )
                    results.append(source)
            else:
                logger.warning(f"Semantic Scholar API yanıt kodu: {response.status_code}")
    except Exception as e:
        logger.warning(f"Semantic Scholar API erişiminde hata (arXiv yedek olarak yeterlidir): {e}")

    return results


def search_academic_papers(
    query: str,
    max_results: int = 4
) -> List[AcademicPaperSource]:
    """
    Birleşik akademik arama fonksiyonu.
    Öncelikle arXiv'den arar, yeterli sonuç gelmezse Semantic Scholar ile zenginleştirir.
    Mükerrer makaleleri başlık benzerliğine göre eler.
    """
    papers = search_arxiv(query, max_results=max_results)

    # Eğer arXiv'den yeterli sonuç alınamadıysa Semantic Scholar'a başvur
    if len(papers) < max_results:
        remaining = max_results - len(papers)
        s2_papers = search_semantic_scholar(query, max_results=remaining)
        
        # Mükerrerleri engelle
        existing_titles = {p.title.lower().strip() for p in papers}
        for s2_p in s2_papers:
            if s2_p.title.lower().strip() not in existing_titles:
                papers.append(s2_p)
                existing_titles.add(s2_p.title.lower().strip())

    return papers[:max_results]

