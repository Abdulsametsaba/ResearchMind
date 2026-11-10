"""
==============================================================================
Dosya: ResearchMind/core/llm.py
Görevi: Google Gemini LLM İstemci Fabrikası ve Model Yönetimi
==============================================================================
Bu dosya, sistemdeki farklı roller (Planner, Researcher, Fact-Checker, Report)
için uygun Gemini model örneklerini (`ChatGoogleGenerativeAI`) üretir.
- Planner ve Report Agent gibi derin akıl yürütme gerektiren roller için
  Pro model (örn. gemini-2.5-pro)
- Arama sorgusu üretimi, hızlı filtreleme ve fact-check için yüksek hızlı
  Flash model (örn. gemini-2.5-flash)
yapılandırılarak maliyet ve hız optimizasyonu sağlanır.
==============================================================================
"""

import os
from typing import Optional
from langchain_google_genai import ChatGoogleGenerativeAI
from ResearchMind.config.settings import get_settings


def get_gemini_client(
    model_name: Optional[str] = None,
    temperature: Optional[float] = None,
    max_retries: int = 3
) -> ChatGoogleGenerativeAI:
    """
    Belirtilen model adı ve parametrelerle yapılandırılmış bir ChatGoogleGenerativeAI
    örneği döndürür.

    Args:
        model_name: Kullanılacak modelin adı. Belirtilmezse varsayılan planner model kullanılır.
        temperature: Üretim yaratıcılığı (0.0 = deterministik, 1.0 = yaratıcı).
        max_retries: Ağ veya kota hatalarında otomatik yeniden deneme sayısı.

    Returns:
        ChatGoogleGenerativeAI nesnesi
    """
    settings = get_settings()
    api_key = settings.GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY")

    if not api_key:
        raise ValueError(
            "[HATA] GEMINI_API_KEY tanımlanmamış!\n"
            "Lütfen .env dosyasında 'GEMINI_API_KEY=...' değişkenini tanımlayın "
            "veya ortam değişkeni olarak ekleyin."
        )

    selected_model = model_name or settings.GEMINI_MODEL_PLANNER
    selected_temp = temperature if temperature is not None else settings.GEMINI_TEMPERATURE

    return ChatGoogleGenerativeAI(
        model=selected_model,
        google_api_key=api_key,
        temperature=selected_temp,
        max_retries=max_retries
    )


def get_planner_llm() -> ChatGoogleGenerativeAI:
    """
    Stratejik planlama, derin analiz ve nihai rapor üretimi için
    yüksek akıl yürütme kapasiteli modeli döndürür.
    """
    settings = get_settings()
    return get_gemini_client(
        model_name=settings.GEMINI_MODEL_PLANNER,
        temperature=0.2
    )


def get_fast_llm() -> ChatGoogleGenerativeAI:
    """
    Alt sorgu üretimi, web metni özetleme, iddia ayrıştırma ve
    doğrulama için yüksek hızlı ve düşük maliyetli modeli döndürür.
    """
    settings = get_settings()
    return get_gemini_client(
        model_name=settings.GEMINI_MODEL_FAST,
        temperature=0.1
    )

