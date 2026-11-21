"""
==============================================================================
Görevi: FastAPI Uygulama Fabrikası ve Merkezi Yapılandırma
==============================================================================
Bu dosya, ResearchMind REST API'ının ana FastAPI uygulama nesnesini oluşturur,
router'ları bağlar, middleware'leri ekler ve uygulama yaşam döngüsü
(lifespan) olaylarını yönetir.

Özellikler:
  - CORS middleware (farklı origin'lerden erişim için)
  - Lifespan context manager (başlangıç/kapanış olayları)
  - Otomatik OpenAPI (Swagger UI: /docs, ReDoc: /redoc)
  - Health check, Research ve Metrics endpoint'leri
  - Yapılandırılmış hata yanıtları
==============================================================================
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.routes.health import router as health_router
from api.routes.research import router as research_router
from config.settings import get_settings

logger = logging.getLogger("ResearchMind.API")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Uygulama yaşam döngüsü yöneticisi.
    Başlangıçta: DB bağlantı kontrolü, log mesajı.
    Kapanışta: DB bağlantılarını kapat.
    """
    settings = get_settings()
    logger.info(f"ResearchMind API v0.4.0 başlatılıyor...")
    logger.info(f"Planner Model: {settings.GEMINI_MODEL_PLANNER}")
    logger.info(f"Fast Model: {settings.GEMINI_MODEL_FAST}")

    # A missing database is allowed during local startup, but schema migration
    # failures must stop startup rather than leave database-backed endpoints broken.
    try:
        from database.connection import check_db_health, init_db
        db_ok, db_msg = await check_db_health()
    except Exception as e:
        logger.warning(f"DB kontrolü sırasında hata: {e}")
        db_ok = False
        db_msg = str(e)

    if db_ok:
        logger.info(f"Veritabanı: {db_msg}")
        await init_db()
        logger.info("Veritabanı tabloları doğrulandı/oluşturuldu.")
    else:
        logger.warning(f"Veritabanı bağlantısı yok: {db_msg}")

    logger.info("ResearchMind API hazır. Swagger UI: http://localhost:8000/docs")
    yield

    # Kapanış
    logger.info("ResearchMind API kapatılıyor...")
    try:
        from database.connection import close_db
        await close_db()
        logger.info("Veritabanı bağlantıları kapatıldı.")
    except Exception as e:
        logger.warning(f"DB kapatma sırasında hata: {e}")


def create_app() -> FastAPI:
    """
    FastAPI uygulama örneğini oluşturur ve yapılandırır.

    Returns:
        Yapılandırılmış FastAPI uygulaması
    """
    settings = get_settings()

    app = FastAPI(
        title="ResearchMind API",
        description=(
            "## 🔬 ResearchMind Otonom Derin Araştırma Sistemi\n\n"
            "Çok ajanlı yapay zeka mimarisini kullanan akademik araştırma API'ı.\n\n"
            "### Temel Özellikler\n"
            "- **Adaptif Araştırma Planlaması**: Soruyu otomatik alt sorulara böler\n"
            "- **Akademik Zeka**: arXiv ve Semantic Scholar entegrasyonu\n"
            "- **Web Araştırması**: Tavily AI ile derin web taraması\n"
            "- **Kanıta Dayalı Doğrulama**: Her iddia kaynaklarıyla çapraz kontrol edilir\n"
            "- **Araştırma Anlatısı**: Bulguları hikayeleştiren bağlam sentezi\n"
            "- **Kalite Metrikleri**: Coverage, Citation Accuracy, Factual Consistency\n\n"
            "### Hızlı Başlangıç\n"
            "1. `POST /api/research` ile araştırma başlatın\n"
            "2. `GET /api/research/{session_id}` ile durumu kontrol edin\n"
            "3. `GET /api/research/{session_id}/report` ile raporu alın\n"
            "4. `GET /api/research/{session_id}/metrics` ile kalite metriklerini görün\n"
        ),
        version="0.4.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.CROSS_ORIGIN],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    # Router'ları bağla
    app.include_router(health_router)
    app.include_router(research_router)

    # Genel hata yakalayıcı
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error(f"İşlenmemiş hata [{request.method} {request.url}]: {exc}")
        return JSONResponse(
            status_code=500,
            content={
                "error": "İç sunucu hatası",
                "detail": str(exc) if settings.DEBUG else "Lütfen sistem yöneticisiyle iletişime geçin.",
                "path": str(request.url),
            }
        )

    # Kök endpoint
    @app.get("/", include_in_schema=False)
    async def root():
        return {
            "name": "ResearchMind API",
            "version": "0.4.0",
            "docs": "/docs",
            "health": "/health",
            "research": "/api/research",
        }

    return app


# WSGI/ASGI uyumlu uygulama örneği
app = create_app()

