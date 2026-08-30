"""Application configuration module."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """PaymentFlow Application Settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    environment: Literal["development", "testing", "staging", "production"] = "development"
    log_level: str = "INFO"
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://paymentflow_user:paymentflow_password@localhost:5432/paymentflow_db",
        description="Async PostgreSQL connection URL",
    )
    sync_database_url: str = Field(
        default="postgresql://paymentflow_user:paymentflow_password@localhost:5432/paymentflow_db",
        description="Sync PostgreSQL connection URL for migrations and tools",
    )

    # Razorpay Credentials Placeholders (Layer 0)
    razorpay_key_id: str = Field(
        default="rzp_test_placeholder_key",
        description="Razorpay API Key ID",
    )
    razorpay_key_secret: str = Field(
        default="placeholder_secret",
        description="Razorpay API Key Secret",
    )
    razorpay_webhook_secret: str = Field(
        default="placeholder_webhook_secret",
        description="Razorpay Webhook Secret",
    )

    # LLM Configuration (Layer 0 & Layer 5D)
    llm_api_key: str = Field(
        default="placeholder_llm_api_key",
        description="LLM API Key",
    )
    llm_model: str = Field(
        default="gemini-1.5-flash",
        description="LLM Model Name",
    )
    llm_base_url: str | None = Field(
        default=None,
        description="Optional custom base URL for LLM provider API endpoint",
    )
    llm_provider_type: Literal["gemini", "openai", "mock"] = Field(
        default="gemini",
        description="LLM Provider protocol format ('gemini', 'openai', or 'mock')",
    )
    llm_timeout_seconds: float = Field(
        default=10.0,
        description="HTTP request timeout in seconds for LLM calls",
    )


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
