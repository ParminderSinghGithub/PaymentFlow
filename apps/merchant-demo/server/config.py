"""Merchant Demo Server Configuration.

Loads merchant credentials and PaymentFlow integration endpoints strictly from environment.
Secrets (RAZORPAY_KEY_SECRET, PAYMENTFLOW_API_KEY) are server-side only and never exposed.
"""

import os

from pydantic_settings import BaseSettings


class MerchantServerSettings(BaseSettings):
    """Configuration for the external merchant storefront server."""

    # Server binding (supports Railway PORT and container environments)
    host: str = os.getenv("HOST", os.getenv("MERCHANT_HOST", "0.0.0.0"))
    port: int = int(os.getenv("PORT", os.getenv("MERCHANT_PORT", "8002")))

    # Merchant Identity
    merchant_id: str = "merchant_demo_store"
    merchant_name: str = "Merchant Store Demo"

    # Server-to-Server Razorpay Credentials (SECRET - NEVER EXPOSED TO CLIENT)
    razorpay_key_id: str = os.getenv("RAZORPAY_KEY_ID", "rzp_test_placeholder_key")
    razorpay_key_secret: str = os.getenv("RAZORPAY_KEY_SECRET", "placeholder_secret")

    # Server-to-Server PaymentFlow Credentials (SECRET - NEVER EXPOSED TO CLIENT)
    paymentflow_api_key: str = os.getenv("PAYMENTFLOW_API_KEY", "pf_live_test_merchant_key_2026")
    paymentflow_api_url: str = os.getenv("PAYMENTFLOW_API_URL", "http://localhost:8001")


def get_merchant_settings() -> MerchantServerSettings:
    """Return merchant server settings instance."""
    return MerchantServerSettings()
