"""Database connection and session lifecycle management."""

import logging
from typing import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from paymentflow.config import get_settings

logger = logging.getLogger(__name__)

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Retrieve or create the global async database engine."""
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.database_url,
            echo=(settings.log_level.upper() == "DEBUG"),
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
        )
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """Retrieve or create the global async session factory."""
    global _sessionmaker
    if _sessionmaker is None:
        engine = get_engine()
        _sessionmaker = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
    return _sessionmaker


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding an async database session."""
    session_factory = get_sessionmaker()
    async with session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def ping_db() -> bool:
    """Execute a simple SELECT 1 to verify database connectivity."""
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            return result.scalar() == 1
    except Exception as exc:
        logger.warning(f"Database ping failed: {exc}")
        return False


async def init_db() -> None:
    """Initialize database engine and ensure table schemas at application startup."""
    engine = get_engine()
    import paymentflow.db.models  # noqa: F401
    from paymentflow.db.base import Base

    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await conn.execute(
                text(
                    "ALTER TABLE recovery_cases ADD COLUMN IF NOT EXISTS "
                    "scheduled_at TIMESTAMP WITH TIME ZONE;"
                )
            )
    except Exception as exc:
        logger.warning(f"Database schema init warning: {exc}")

    logger.info("Database engine initialized.")


async def close_db() -> None:
    """Dispose database engine at application shutdown."""
    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _sessionmaker = None
        logger.info("Database engine closed.")
