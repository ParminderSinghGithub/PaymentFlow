"""Tests for FastAPI application startup and health check."""

import pytest
from httpx import AsyncClient

from paymentflow.main import create_app, lifespan


@pytest.mark.asyncio
async def test_app_instantiation():
    """Verify application factory creates a valid FastAPI app instance."""
    app = create_app()
    assert app.title == "PaymentFlow Recovery Agent"
    assert app.version == "0.1.0"


@pytest.mark.asyncio
async def test_app_lifespan():
    """Verify application startup and shutdown lifespan execution."""
    app = create_app()
    async with lifespan(app):
        assert app is not None


@pytest.mark.asyncio
async def test_health_endpoint(client: AsyncClient):
    """Verify /health endpoint returns structured health check response."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "environment" in data
    assert "database" in data
    assert data["version"] == "0.1.0"
    assert data["environment"] == "testing"


@pytest.mark.asyncio
async def test_root_endpoint(client: AsyncClient):
    """Verify root endpoint returns system metadata."""
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "PaymentFlow Recovery Agent"
    assert data["status"] == "online"

