"""Tests for database connectivity and session lifecycle."""

import pytest
from sqlalchemy import text

from paymentflow.config import get_settings
from paymentflow.db.session import close_db, get_db_session, get_engine, ping_db


@pytest.mark.asyncio
async def test_ping_db_success():
    """Verify ping_db returns True when connected to the database."""
    get_settings.cache_clear()
    await close_db()
    is_connected = await ping_db()
    assert is_connected is True


@pytest.mark.asyncio
async def test_db_session_lifecycle():
    """Verify get_db_session yields an active async session capable of executing queries."""
    async for session in get_db_session():
        result = await session.execute(text("SELECT 1"))
        assert result.scalar() == 1


@pytest.mark.asyncio
async def test_ping_db_handles_failure_cleanly(monkeypatch):
    """Verify ping_db handles unreachable host without raising uncaught exceptions."""
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://invalid_user:invalid_pass@127.0.0.1:59999/nonexistent",
    )
    get_settings.cache_clear()
    await close_db()

    is_connected = await ping_db()
    assert is_connected is False

    get_settings.cache_clear()
    await close_db()


@pytest.mark.asyncio
async def test_engine_lifecycle():
    """Verify engine creation and clean disposal."""
    engine = get_engine()
    assert engine is not None
    await close_db()
