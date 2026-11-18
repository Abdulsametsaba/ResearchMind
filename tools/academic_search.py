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
import re
from typing import List, Set
import arxiv
import httpx
from config.settings import get_settings
from core.state import AcademicPaperSource

logger = logging.getLogger("ResearchMind.Tools.AcademicSearch")


def _tokenize_text(text: str) -> Set[str]:
    """Metni küçük harfli kelime token'larına ayırır ve bağlaçları eler."""
    stop_words = {
        "a", "an", "the", "and", "or", "in", "on", "at", "to", "for", "of", "with",
        "by", "from", "as", "is", "are", "was", "were", "be", "been", "that", "this",
        "it", "which", "ve", "ile", "bir", "bu", "için", "olan", "olarak", "de", "da"
    }
    words = re.findall(r'[a-zA-Z0-9\-_]{2,}', text.lower())
    return {w for w in words if w not in stop_words}


def compute_relevance_score(query: str, title: str, abstract: str) -> float:
    """
    Sorgu terimleri ile makale başlığı ve özeti arasındaki anlamsal/sözcüksel
    örtüşmeye göre dinamik bir alaka (relevance) skoru hesaplar (0.15 - 0.98).
    
    - Başlık eşleşmeleri 2.5x kat ağırlıklıdır.
    - Büyük harfli / teknik kısaltmalar (örn. FIPS, KEM, DSA, RSA, LLM) korunur.
    - Tam sorgu öbeği geçiyorsa ek prim verilir.
    """
    if not query:
        return 0.50

    q_tokens = _tokenize_text(query)
    if not q_tokens:
        return 0.50

    title_tokens = _tokenize_text(title)
    abstract_tokens = _tokenize_text(abstract)

    # Başlık ve özet kesişimleri
    title_matches = q_tokens.intersection(title_tokens)
    abstract_matches = q_tokens.intersection(abstract_tokens)

    # Örtüşme oranları
    title_ratio = len(title_matches) / len(q_tokens)
    abstract_ratio = len(abstract_matches) / len(q_tokens)

    # Ağırlıklı birleşik skor: Başlık çok daha kritiktir
    raw_score = (title_ratio * 0.65) + (abstract_ratio * 0.35)

    # Tam sorgu öbeği veya anahtar terim başlıkta geçiyorsa prim
    clean_q = query.lower().strip()
    if clean_q in title.lower():
        raw_score += 0.20
    elif clean_q in abstract.lower():
        raw_score += 0.10

    # Taban skor 0.15, tavan 0.98 olacak şekilde sınırla ve yuvarla
    final_score = max(0.15, min(0.98, raw_score))
    return round(final_score, 2)


def search_arxiv(
    query: str,
    max_results: int = 4,
    sort_by: arxiv.SortCriterion = arxiv.SortCriterion.Relevance,
    min_relevance_threshold: float = 0.25
) -> List[AcademicPaperSource]:
    """
    arXiv API üzerinden verilen sorguya ilişkin en alakalı akademik makaleleri arar.
    Dinamik alaka skoru hesaplar ve belirlenen eşik değerinin altındaki ilgisiz makaleleri eler.

    Args:
        query: Arama terimi (örn. 'post-quantum cryptography ML-KEM FIPS 203')
        max_results: Getirilecek maksimum makale sayısı
        sort_by: Sıralama kriteri (Relevance veya SubmittedDate)
        min_relevance_threshold: Bu skorun altındaki makaleler elenir (varsayılan: 0.25)

    Returns:
        List[AcademicPaperSource] listesi
    """
    settings = get_settings()
    results: List[AcademicPaperSource] = []

    logger.info(f"arXiv araması başlatılıyor: '{query}' (limit: {max_results})")

    try:
        # arXiv İstemcisi yapılandırması (sayfa boyutu ve gecikme ayarlı)
        client = arxiv.Client(
            page_size=max(max_results * 2, 6),  # Filtreleme için biraz daha fazla çek
            delay_seconds=1.5,
            num_retries=3
        )

        search = arxiv.Search(
            query=query,
            max_results=max(max_results * 2, 6),
            sort_by=sort_by
        )

        for paper in client.results(search):
            paper_id = paper.entry_id.split("/")[-1]  # örn. 2401.12345v1
            year = str(paper.published.year) if paper.published else None
            author_names = [author.name for author in paper.authors]
            title_clean = paper.title.strip().replace("\n", " ")
            abstract_clean = paper.summary.strip().replace("\n", " ")

            # Dinamik alaka skoru hesaplama
            rel_score = compute_relevance_score(query, title_clean, abstract_clean)

            # Belirlenen eşik değerinin altındaki alakasız makaleleri ele
            if rel_score < min_relevance_threshold:
                logger.debug(f"arXiv makalesi elendi (düşük alaka: {rel_score}): {title_clean[:50]}")
                continue

            source = AcademicPaperSource(
                id=f"arxiv:{paper_id}",
                title=title_clean,
                authors=author_names,
                published_year=year,
                url=paper.entry_id,
                pdf_url=paper.pdf_url,
                abstract=abstract_clean,
                extracted_intel=None,
                relevance_score=rel_score
            )
            results.append(source)
            if len(results) >= max_results:
                break

        logger.info(f"arXiv araması tamamlandı. {len(results)} makale seçildi.")
    except Exception as e:
        logger.error(f"arXiv araması sırasında hata oluştu: {e}")

    return results


def search_semantic_scholar(
    query: str,
    max_results: int = 3,
    min_relevance_threshold: float = 0.25
) -> List[AcademicPaperSource]:
    """
    Semantic Scholar Graph API üzerinden akademik makale araması yapar.
    Varsa SEMANTIC_SCHOLAR_API_KEY kullanılır, yoksa genel kota üzerinden sorgu atılır.
    Dinamik alaka skoru hesaplar.
    """
    settings = get_settings()
    results: List[AcademicPaperSource] = []
    endpoint = "https://api.semanticscholar.org/graph/v1/paper/search"

    headers = {}
    if settings.SEMANTIC_SCHOLAR_API_KEY:
        headers["x-api-key"] = settings.SEMANTIC_SCHOLAR_API_KEY

    params = {
        "query": query,
        "limit": max(max_results * 2, 5),
        "fields": "title,authors,year,abstract,openAccessPdf,url"
    }

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(endpoint, params=params, headers=headers)
            if response.status_code == 200:
                data = response.json()
                for item in data.get("data", []):
                    title = item.get("title", "İsimsiz Makale").strip()
                    abstract = (item.get("abstract") or "Özet metin bulunamadı.").strip()
                    year = str(item.get("year")) if item.get("year") else None
                    authors = [a.get("name") for a in item.get("authors", []) if a.get("name")]
                    pdf_info = item.get("openAccessPdf") or {}
                    pdf_url = pdf_info.get("url")
                    paper_id = item.get("paperId", "unknown")

                    rel_score = compute_relevance_score(query, title, abstract)
                    if rel_score < min_relevance_threshold:
                        continue

                    source = AcademicPaperSource(
                        id=f"s2:{paper_id[:12]}",
                        title=title,
                        authors=authors,
                        published_year=year,
                        url=item.get("url") or f"https://www.semanticscholar.org/paper/{paper_id}",
                        pdf_url=pdf_url,
                        abstract=abstract,
                        extracted_intel=None,
                        relevance_score=rel_score
                    )
                    results.append(source)
                    if len(results) >= max_results:
                        break
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
    Mükerrer makaleleri başlık benzerliğine göre eler ve alaka skoruna göre sıralar.
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

    # En yüksek alaka skoruna göre sırala
    papers.sort(key=lambda x: x.relevance_score, reverse=True)
    return papers[:max_results]

