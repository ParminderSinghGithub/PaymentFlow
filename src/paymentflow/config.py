"""Application configuration module."""

from functools import lru_cache
from typing import Any, Literal

from pydantic import AliasChoices, Field, field_validator, model_validator
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
    app_port: int = Field(
        default=8000,
        validation_alias=AliasChoices("PORT", "APP_PORT"),
        description="Application port (supports Railway PORT or APP_PORT)",
    )
    public_base_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("PUBLIC_BASE_URL", "PAYMENTFLOW_PUBLIC_BASE_URL"),
        description="Public base URL (e.g. Railway public domain or zrok tunnel URL)",
    )

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://paymentflow_user:paymentflow_password@localhost:5432/paymentflow_db",
        validation_alias=AliasChoices("DATABASE_URL", "APP_DATABASE_URL"),
        description="Async PostgreSQL connection URL",
    )
    sync_database_url: str = Field(
        default="postgresql://paymentflow_user:paymentflow_password@localhost:5432/paymentflow_db",
        validation_alias=AliasChoices("SYNC_DATABASE_URL", "APP_SYNC_DATABASE_URL"),
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
        validation_alias=AliasChoices("GEMINI_API_KEY", "LLM_API_KEY"),
        description="LLM API Key (Google Gemini)",
    )
    llm_model: str = Field(
        default="gemini-2.5-flash",
        validation_alias=AliasChoices("GEMINI_MODEL", "LLM_MODEL"),
        description="LLM Model identifier",
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

    # CORS Configuration for Frontend Service
    cors_origins: list[str] | str = Field(
        default=["*"],
        description="Allowed CORS origins for external frontend service",
    )

    # Merchant Server-to-Server Integration (Layer 6: Merchant Integration Boundary)
    paymentflow_api_key: str = Field(
        default="pf_live_test_merchant_key_2026",
        description="PaymentFlow Server-to-Server API Key for Merchant Integration",
    )
    paymentflow_api_url: str = Field(
        default="http://localhost:8000",
        description="Base URL for PaymentFlow API service",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("[") and v.endswith("]"):
                import json

                try:
                    parsed = json.loads(v)
                    if isinstance(parsed, list):
                        return [str(origin).strip() for origin in parsed if str(origin).strip()]
                except Exception:
                    pass
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        if isinstance(v, list):
            return [str(origin).strip() for origin in v if str(origin).strip()]
        return ["*"]

    @model_validator(mode="after")
    def reconcile_database_urls(self) -> "Settings":
        from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

        # Ensure async database_url uses postgresql+asyncpg:// dialect
        # and asyncpg-compatible SSL query parameters
        if self.database_url:
            db_url = self.database_url
            if db_url.startswith("postgres://"):
                db_url = "postgresql+asyncpg://" + db_url[len("postgres://") :]
            elif db_url.startswith("postgresql://") and not db_url.startswith(
                "postgresql+asyncpg://"
            ):
                db_url = "postgresql+asyncpg://" + db_url[len("postgresql://") :]

            parsed = urlsplit(db_url)
            if parsed.query:
                qs = parse_qs(parsed.query)
                # asyncpg expects 'ssl' parameter rather than libpq 'sslmode'
                if "sslmode" in qs:
                    ssl_val = qs.pop("sslmode")
                    if "ssl" not in qs:
                        qs["ssl"] = ssl_val
                # asyncpg does not support channel_binding
                qs.pop("channel_binding", None)
                db_url = urlunsplit(
                    (
                        parsed.scheme,
                        parsed.netloc,
                        parsed.path,
                        urlencode(qs, doseq=True),
                        parsed.fragment,
                    )
                )
            self.database_url = db_url

        # Ensure sync_database_url is derived or has postgresql:// dialect for psycopg2
        default_sync = (
            "postgresql://paymentflow_user:paymentflow_password@localhost:5432/paymentflow_db"
        )
        if self.sync_database_url == default_sync and not self.database_url.endswith(
            "localhost:5432/paymentflow_db"
        ):
            sync_url = self.database_url
            if sync_url.startswith("postgresql+asyncpg://"):
                sync_url = "postgresql://" + sync_url[len("postgresql+asyncpg://") :]
            parsed = urlsplit(sync_url)
            if parsed.query:
                qs = parse_qs(parsed.query)
                if "ssl" in qs and "sslmode" not in qs:
                    qs["sslmode"] = qs.pop("ssl")
                qs.pop("channel_binding", None)
                sync_url = urlunsplit(
                    (
                        parsed.scheme,
                        parsed.netloc,
                        parsed.path,
                        urlencode(qs, doseq=True),
                        parsed.fragment,
                    )
                )
            self.sync_database_url = sync_url
        elif self.sync_database_url:
            sync_url = self.sync_database_url
            if sync_url.startswith("postgres://"):
                sync_url = "postgresql://" + sync_url[len("postgres://") :]
            elif sync_url.startswith("postgresql+asyncpg://"):
                sync_url = "postgresql://" + sync_url[len("postgresql+asyncpg://") :]
            parsed = urlsplit(sync_url)
            if parsed.query:
                qs = parse_qs(parsed.query)
                if "ssl" in qs and "sslmode" not in qs:
                    qs["sslmode"] = qs.pop("ssl")
                qs.pop("channel_binding", None)
                sync_url = urlunsplit(
                    (
                        parsed.scheme,
                        parsed.netloc,
                        parsed.path,
                        urlencode(qs, doseq=True),
                        parsed.fragment,
                    )
                )
            self.sync_database_url = sync_url

        return self


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
