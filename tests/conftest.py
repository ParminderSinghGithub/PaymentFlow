"""Pytest fixtures and configuration."""

import os
from typing import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

from paymentflow.config import Settings, get_settings
from paymentflow.db.session import close_db
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
async def cleanup_db_connections():
    """Ensure database connections are cleanly disposed between tests."""
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

