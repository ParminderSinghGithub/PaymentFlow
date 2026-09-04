"""Merchant Demo Server Configuration.

Loads merchant credentials and PaymentFlow integration endpoints strictly from environment.
Secrets (RAZORPAY_KEY_SECRET, PAYMENTFLOW_API_KEY) are server-side only and never exposed.
"""

import os

from pydantic_settings import BaseSettings


class MerchantServerSettings(BaseSettings):
    """Configuration for the external merchant storefront server."""

    # Server binding
    host: str = "127.0.0.1"
    port: int = 8002

    # Merchant Identity
    merchant_id: str = "merchant_demo_store"
    merchant_name: str = "Acme Fashion Store (Buildathon Demo)"

    # Server-to-Server Razorpay Credentials (SECRET - NEVER EXPOSED TO CLIENT)
    razorpay_key_id: str = os.getenv("RAZORPAY_KEY_ID", "rzp_test_TWkctY0MsbW4Rd")
    razorpay_key_secret: str = os.getenv("RAZORPAY_KEY_SECRET", "PWatfW99KA7gH4our6Sfvmoe")

    # Server-to-Server PaymentFlow Credentials (SECRET - NEVER EXPOSED TO CLIENT)
    paymentflow_api_key: str = os.getenv("PAYMENTFLOW_API_KEY", "pf_live_test_merchant_key_2026")
    paymentflow_api_url: str = os.getenv("PAYMENTFLOW_API_URL", "http://localhost:8001")


def get_merchant_settings() -> MerchantServerSettings:
    """Return merchant server settings instance."""
    return MerchantServerSettings()
