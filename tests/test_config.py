"""Tests for application configuration."""

import pytest
from pydantic import ValidationError

from paymentflow.config import Settings


def test_default_config_loading():
    """Verify settings load default values properly."""
    settings = Settings()
    assert settings.environment in ["development", "testing", "staging", "production"]
    assert settings.app_port == 8000
    assert "postgresql" in settings.database_url
    assert settings.razorpay_key_id is not None
    assert settings.llm_model == "gemini-1.5-flash"


def test_custom_environment_override(monkeypatch):
    """Verify settings can be overridden by environment variables."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("APP_PORT", "9000")
    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://custom:pwd@dbhost:5432/custom_db")

    settings = Settings()
    assert settings.environment == "production"
    assert settings.app_port == 9000
    assert settings.log_level == "WARNING"
    assert settings.database_url == "postgresql+asyncpg://custom:pwd@dbhost:5432/custom_db"


def test_invalid_environment_validation(monkeypatch):
    """Verify invalid environment literals are rejected by Pydantic."""
    monkeypatch.setenv("ENVIRONMENT", "invalid_env_name")
    with pytest.raises(ValidationError):
        Settings()
