"""Pytest fixtures and configuration."""

import os
from typing import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from paymentflow.config import Settings, get_settings
from paymentflow.db.session import close_db, get_engine
from paymentflow.main import create_app


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    """Test configuration settings."""
    return Settings(
        environment="testing",
        log_level="DEBUG",
        database_url=os.getenv(
            "DATABASE_URL",
            "postgresql+asyncpg://paymentflow_user:paymentflow_password@localhost:5432/paymentflow_db",
        ),
        sync_database_url=os.getenv(
            "SYNC_DATABASE_URL",
            "postgresql://paymentflow_user:paymentflow_password@localhost:5432/paymentflow_db",
        ),
    )


@pytest.fixture(autouse=True)
async def cleanup_db_tables():
    """Ensure database tables are initialized, truncated, and connections disposed cleanly."""
    try:
        engine = get_engine()
        import paymentflow.db.models  # noqa: F401
        from paymentflow.db.base import Base

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await conn.execute(
                text(
                    "ALTER TABLE recovery_cases ADD COLUMN IF NOT EXISTS "
                    "scheduled_at TIMESTAMP WITH TIME ZONE;"
                )
            )
            await conn.execute(
                text(
                    "TRUNCATE TABLE audit_events, recovery_cases, webhook_events "
                    "RESTART IDENTITY CASCADE;"
                )
            )
    except Exception:
        pass

    yield

    await close_db()


@pytest.fixture
async def client(test_settings: Settings) -> AsyncGenerator[AsyncClient, None]:
    """Async test client fixture."""
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: test_settings

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


