from config.settings import Settings
from langchain_google_genai import GoogleGenerativeAIEmbeddings
import logging
from typing import Optional, List

logger = logging.getLogger('ResearchMind.Tools.Embeddings')

EMBEDDING_DIM=768
MAX_TEXT_CHARS=8000

def generate_embedding(
    text: str,
) -> Optional[List[float]]:
    """
    Verilen metni 768 boyutlu anlamsal vektöre dönüştürür.

    Gemini text-embedding-004 modeli kullanılır. API anahtarı yoksa veya
    metin boşsa None döner; çağıran kod bunu sessizce atlayabilir.

    Args:
        text: Vektörleştirilecek metin (makale özeti, snippet vb.)

    Returns:
        768 elemanlı float listesi veya None
    """
    settings = Settings()
    api_key = settings.GEMINI_API_KEY

    if not api_key or api_key.startswith("buraya_"):
        logger.debug("Gemini API anahtarı yapılandırılmamış — embedding atlandı.")
        return None

    if not text or not text.strip():
        return None

    trimmed=text.strip()[:MAX_TEXT_CHARS]

    try:
        model_name = settings.GEMINI_MODEL_EMBEDDING or "models/text-embedding-004"
        model = GoogleGenerativeAIEmbeddings(
            model=model_name,
            google_api_key=api_key,
        )
        embedding: List[float] = model.embed_query(trimmed,output_dimensionality=EMBEDDING_DIM)
        logger.debug(
            f"Embedding üretildi: {len(embedding)} boyut | "
            f"giriş: {len(trimmed)} karakter"
        )
        return embedding

    except Exception as exc:
        logger.warning(f"Embedding üretim hatası: {exc}")
        return None

def build_paper_text(title: str, abstract: str) -> str:
    """
    Makale için embedding giriş metnini oluşturur.
    Başlık + özet birleştirmesi en iyi anlamsal temsili sağlar.
    """
    return f"{title}. {abstract}"


def build_web_source_text(title: str, snippet: str) -> str:
    """
    Web kaynağı için embedding giriş metnini oluşturur.
    """
    return f"{title}. {snippet}"


def build_query_text(query: str) -> str:
    """
    Araştırma sorgusu için embedding giriş metnini oluşturur.
    """
    return query.strip() 

