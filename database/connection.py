"""
==============================================================================
Dosya: researchmind/database/connection.py
Görevi: Asenkron Veritabanı Bağlantısı ve Tablo Yönetimi
==============================================================================
Bu dosya, SQLAlchemy 2.0 AsyncEngine ve async_sessionmaker kullanarak
PostgreSQL (+ pgvector) veritabanına asenkron bağlantı kurar, oturumları yönetir
ve tabloların otomatik oluşturulmasını (init_db) sağlar.

Motor (engine) tembel yükleme (lazy initialization) ile çalışır; böylece
farklı event-loop'larda veya testlerde bağlantı havuzu kilitlenmeleri önlenir.
==============================================================================
"""

import logging
from typing import AsyncGenerator, Optional, Tuple
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy import text
from config.settings import get_settings
from database.models import Base

logger = logging.getLogger("ResearchMind.Database")

# Ayarları oku
settings = get_settings()

_engine: Optional[AsyncEngine] = None
_session_maker: Optional[async_sessionmaker[AsyncSession]] = None


def get_engine() -> AsyncEngine:
    """
    SQLAlchemy Asenkron Motor örneğini döndürür (Lazy Singleton).
    """
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            settings.DATABASE_URL,
            echo=False,
            pool_pre_ping=True,
            future=True
        )
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """
    Oturum fabrikasını döndürür.
    """
    global _session_maker
    if _session_maker is None:
        _session_maker = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False
        )
    return _session_maker


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI veya arka plan ajanları için asenkron oturum (session) üreteci.
    Kullanım bittiğinde oturumu güvenle kapatır.
    """
    session_maker = get_sessionmaker()
    async with session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def close_db() -> None:
    """
    Tüm veritabanı bağlantı havuzlarını kapatır ve kaynakları serbest bırakır.
    """
    global _engine, _session_maker
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_maker = None


async def check_db_health() -> Tuple[bool, str]:
    """
    Configured PostgreSQL connection is checked directly, regardless of how
    the database is hosted.
    """
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True, "PostgreSQL bağlantısı başarılı ve çalışıyor."
    except Exception as e:
        return False, f"PostgreSQL bağlantısı başarısız: {type(e).__name__} - {e}"


async def init_db() -> None:
    """
    Veritabanı tablolarını ve varsa pgvector eklentisini oluşturur.
    Faz-6: Mevcut tablolara embedding sütunlarını ekleyen migration çalıştırır.
    """
    engine = get_engine()
    async with engine.begin() as conn:
        try:
            # Vektör eklentisini etkinleştir (pgvector)
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            logger.info("pgvector eklentisi doğrulandı/etkinleştirildi.")
        except Exception as e:
            logger.warning(f"pgvector eklentisi etkinleştirilemedi (vektör özellikleri sınırlandırılabilir): {e}")

        # Tüm modellerin tablolarını oluştur
        await conn.run_sync(Base.metadata.create_all)
        logger.info("Tüm veritabanı tabloları başarıyla oluşturuldu.")

        await conn.execute(text(
            "ALTER TABLE research_sessions "
            "ADD COLUMN IF NOT EXISTS result_summary JSON;"
        ))

        # ── Faz-6 Migration: Mevcut tablolara embedding sütunları ekle ──────────
        # CREATE TABLE IF NOT EXISTS mevcut tablolara yeni sütun eklemez;
        # ALTER TABLE + ADD COLUMN IF NOT EXISTS güvenli şekilde çalışır.
        try:
            await conn.execute(text(
                "ALTER TABLE academic_papers "
                "ADD COLUMN IF NOT EXISTS embedding vector(768);"
            ))
            await conn.execute(text(
                "ALTER TABLE web_sources "
                "ADD COLUMN IF NOT EXISTS embedding vector(768);"
            ))
            logger.info("Faz-6 migration: embedding sütunları doğrulandı/eklendi.")
        except Exception as e:
            logger.warning(f"Faz-6 migration sırasında hata (embedding sütunları): {e}")
