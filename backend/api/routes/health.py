"""
==============================================================================
Görevi: Sistem Sağlık Kontrolü Endpoint'i (Health Check)
==============================================================================
Bu modül, ResearchMind sisteminin çalışma durumunu ve bağımlı servislerin
sağlığını raporlayan /health endpoint'ini sağlar.

Kontrol Edilen Bileşenler:
  - PostgreSQL veritabanı bağlantısı
  - Gemini API anahtarı yapılandırması
  - Tavily API anahtarı yapılandırması
  - Uygulama başlatma zamanı (uptime)
==============================================================================
"""

import time
import logging
from fastapi import APIRouter
from api.schemas import HealthResponse
from config.settings import get_settings
from database.connection import check_db_health

logger = logging.getLogger("ResearchMind.API.Health")

router = APIRouter(tags=["System"])

_start_time = time.time()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Sistem Sağlık Kontrolü",
    description="Tüm bağımlı servislerin durumunu raporlar."
)
async def health_check() -> HealthResponse:
    """
    ResearchMind sisteminin genel sağlık durumunu kontrol eder.
    Kubernetes/Docker liveness probe veya monitoring için kullanılabilir.
    """
    settings = get_settings()
    uptime = time.time() - _start_time

    # Veritabanı kontrolü
    db_ok, db_msg = await check_db_health()
    db_status = "connected" if db_ok else "disconnected"

    # API anahtarı kontrolleri
    gemini_ok = bool(settings.GEMINI_API_KEY and not settings.GEMINI_API_KEY.startswith("buraya_"))
    tavily_ok = bool(settings.TAVILY_API_KEY and not settings.TAVILY_API_KEY.startswith("buraya_"))

    overall_status = "healthy" if (db_ok and gemini_ok and tavily_ok) else "degraded"

    logger.info(f"Health check: DB={db_status}, Gemini={gemini_ok}, Tavily={tavily_ok}")

    return HealthResponse(
        status=overall_status,
        version="0.4.0",
        database=db_status,
        gemini_api="configured" if gemini_ok else "not_configured",
        tavily_api="configured" if tavily_ok else "not_configured",
        uptime_seconds=round(uptime, 2),
        details={
            "database_message": db_msg,
            "max_sub_questions": settings.MAX_SUB_QUESTIONS,
            "max_iterations": settings.MAX_ITERATIONS,
            "planner_model": settings.GEMINI_MODEL_PLANNER,
            "fast_model": settings.GEMINI_MODEL_FAST,
            "embedding_model": settings.GEMINI_MODEL_EMBEDDING,
        }
    )

