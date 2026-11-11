"""
==============================================================================
Görevi: Merkezi Konfigürasyon ve Ortam Değişkenleri Yönetimi
==============================================================================
Bu dosya, Pydantic Settings kullanarak .env dosyasındaki veya sistem ortamındaki
değişkenleri (API anahtarları, model isimleri, veritabanı bağlantı URI'leri)
tip güvenli (type-safe) bir şekilde okur ve uygulamanın tüm katmanlarına
doğrulanmış ayar nesnesi sağlar.
==============================================================================
"""

import os
from functools import lru_cache
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    ResearchMind merkezi konfigürasyon sınıfı.
    Ortam değişkenlerini .env dosyasından otomatik yükler.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # --- Uygulama Temel Ayarları ---
    APP_NAME: str = "ResearchMind"
    APP_ENV: str = "development"
    DEBUG: bool = True

    # --- LLM Sağlayıcısı (Google Gemini) ---
    # Not: Bu değer .env içinde tanımlanmalıdır.
    GEMINI_API_KEY: str = Field(
        default="",
        description="Google AI Studio Gemini API anahtarı"
    )
    GEMINI_MODEL_PLANNER: str = Field(
        default="gemini-2.5-pro",
        description="Planlama, sentez ve rapor yazımı için kullanılan ana model"
    )
    GEMINI_MODEL_FAST: str = Field(
        default="gemini-2.5-flash",
        description="Hızlı alt sorgu üretimi, özetleme ve fact-check için model"
    )
    GEMINI_TEMPERATURE: float = Field(
        default=0.2,
        description="Halüsinasyonu azaltmak için düşük sıcaklık değeri"
    )

    # --- Arama Araçları ---
    TAVILY_API_KEY: str = Field(
        default="",
        description="Tavily AI Search API anahtarı"
    )
    SEMANTIC_SCHOLAR_API_KEY: Optional[str] = Field(
        default=None,
        description="Opsiyonel: Semantic Scholar API anahtarı"
    )

    # --- Veritabanı ve Vektör Veritabanı (PostgreSQL + pgvector) ---
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "researchmind"
    POSTGRES_HOST: str = "127.0.0.1"
    POSTGRES_PORT: int = 5432
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/researchmind",
        description="Asyncpg uyumlu PostgreSQL ve pgvector bağlantı dizesi"
    )

    # --- Araştırma Parametreleri ---
    MAX_SUB_QUESTIONS: int = Field(
        default=5,
        description="Bir araştırmada oluşturulabilecek maksimum alt soru sayısı"
    )
    MAX_ITERATIONS: int = Field(
        default=2,
        description="Eksik bilgi tespitinde izin verilen maksimum ek arama döngüsü sayısı"
    )
    MAX_PAPERS_PER_SUBQUESTION: int = Field(
        default=3,
        description="Her bir alt soru için incelenecek maksimum akademik makale sayısı"
    )
    MAX_WEB_SOURCES_PER_SUBQUESTION: int = Field(
        default=4,
        description="Her bir alt soru için taranacak maksimum web kaynağı sayısı"
    )

    # --- İsteğe Bağlı Gözlemlenebilirlik (LangSmith) ---
    LANGCHAIN_TRACING_V2: bool = False
    LANGCHAIN_API_KEY: Optional[str] = None
    LANGCHAIN_PROJECT: str = "ResearchMind"


@lru_cache()
def get_settings() -> Settings:
    """
    Singleton konfigürasyon nesnesi döndürür.
    lru_cache sayesinde dosya sadece bir kez okunur.
    """
    return Settings()

