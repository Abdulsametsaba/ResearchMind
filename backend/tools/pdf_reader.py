"""
==============================================================================
Dosya: researchmind/tools/pdf_reader.py
Görevi: Akademik PDF İndirme, Bölüm Ayrıştırma ve Önbellekleme Aracı
==============================================================================
Bu araç, arXiv veya diğer açık erişimli makalelerin PDF dosyalarını indirir,
PyMuPDF (fitz) ile metin katmanını okur ve hedef odaklı bölümleri
(Methodology, Architecture, Experiments, Benchmarks, Limitations) ayrıştırır.

Büyük PDF'lerin tekrar tekrar indirilmesini engellemek için yerel dosya sistemi
üzerinde (data/cache/papers/) SHA-256 / ID tabanlı önbellekleme (caching) uygular.
==============================================================================
"""

import os
import re
import logging
import hashlib
from typing import Dict, Optional
import httpx
import pymupdf  # Modern PyMuPDF API

logger = logging.getLogger("ResearchMind.Tools.PDFReader")

# Önbellek dizini
CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "cache", "papers")
os.makedirs(CACHE_DIR, exist_ok=True)


def get_cache_path(identifier: str) -> str:
    """Belirli bir makale ID veya URL'i için önbellek dosya yolunu üretir."""
    clean_id = re.sub(r'[^a-zA-Z0-9_\-]', '_', identifier)
    if len(clean_id) > 80:
        hash_suffix = hashlib.sha256(identifier.encode()).hexdigest()[:10]
        clean_id = clean_id[:70] + "_" + hash_suffix
    return os.path.join(CACHE_DIR, f"{clean_id}.txt")


def download_and_extract_pdf_text(
    pdf_url: str,
    max_pages: int = 15,
    timeout_seconds: float = 20.0
) -> Optional[str]:
    """
    Verilen URL'den PDF dosyasını indirir ve ilk max_pages sayfasındaki metni çıkarır.
    Daha önce indirildiyse disk önbelleğinden (cache) okur.

    Args:
        pdf_url: Doğrudan PDF indirme bağlantısı (örn. https://arxiv.org/pdf/2401.12345)
        max_pages: Okunacak maksimum sayfa sayısı (aşırı token yükünü engeller)
        timeout_seconds: İndirme zaman aşımı

    Returns:
        Ayrıştırılmış temiz metin veya None
    """
    if not pdf_url:
        return None

    cache_file = get_cache_path(pdf_url)

    # 1. Önbellek kontrolü
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                logger.info(f"PDF önbellekten okundu: {os.path.basename(cache_file)}")
                return f.read()
        except Exception as e:
            logger.warning(f"Önbellek dosyası okunamadı, yeniden indirilecek: {e}")

    logger.info(f"PDF indiriliyor: {pdf_url}")

    # 2. İndirme
    try:
        headers = {
            "User-Agent": "ResearchMind-Agent/1.0 (Academic Research; mailto:research@example.com)"
        }
        with httpx.Client(timeout=timeout_seconds, follow_redirects=True, headers=headers) as client:
            resp = client.get(pdf_url)
            if resp.status_code != 200:
                logger.warning(f"PDF indirilemedi. Durum kodu: {resp.status_code} ({pdf_url})")
                return None
            pdf_bytes = resp.content

        # 3. PyMuPDF ile ayrıştırma
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        total_pages = min(len(doc), max_pages)
        pages_text = []

        for page_num in range(total_pages):
            page = doc[page_num]
            text = page.get_text("text")
            if text:
                pages_text.append(f"--- [Sayfa {page_num + 1}] ---\n{text}")

        doc.close()
        full_extracted_text = "\n\n".join(pages_text)

        # 4. Önbelleğe kaydet
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                f.write(full_extracted_text)
        except Exception as e:
            logger.warning(f"Önbellek dosyasına yazılamadı: {e}")

        logger.info(f"PDF başarıyla ayrıştırıldı ({total_pages} sayfa): {pdf_url}")
        return full_extracted_text

    except Exception as e:
        logger.error(f"PDF indirme veya okuma hatası ({pdf_url}): {e}")
        return None


def extract_targeted_sections(full_text: str) -> Dict[str, str]:
    """
    Tam makale metninden LLM analizi için kritik bölümleri hedefler.
    - Model Architecture & Method
    - Experiments & Benchmark Results
    - Limitations
    """
    sections = {
        "abstract_and_intro": "",
        "method_and_architecture": "",
        "experiments_and_results": "",
        "limitations_and_conclusion": ""
    }

    if not full_text:
        return sections

    lines = full_text.split("\n")
    current_section = "abstract_and_intro"
    collected_lines = {sec: [] for sec in sections}

    # Temel bölüm başlığı tespit kalıpları
    method_pattern = re.compile(r'^(?:\d+\.?\s*)?(?:method|methodology|architecture|proposed|approach)', re.IGNORECASE)
    experiment_pattern = re.compile(r'^(?:\d+\.?\s*)?(?:experiment|evaluation|results|benchmark)', re.IGNORECASE)
    limitation_pattern = re.compile(r'^(?:\d+\.?\s*)?(?:limitation|conclusion|future work|discussion)', re.IGNORECASE)

    for line in lines:
        stripped = line.strip()
        if method_pattern.match(stripped):
            current_section = "method_and_architecture"
        elif experiment_pattern.match(stripped):
            current_section = "experiments_and_results"
        elif limitation_pattern.match(stripped):
            current_section = "limitations_and_conclusion"

        collected_lines[current_section].append(line)

    for sec in sections:
        # Bölüm başına maksimum ~3500 karakter sınırla (context window optimizasyonu)
        joined = "\n".join(collected_lines[sec])
        sections[sec] = joined[:4000]

    return sections
