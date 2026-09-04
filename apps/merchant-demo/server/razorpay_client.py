"""Merchant-side thin Razorpay client.

Handles standard Razorpay order creation for the merchant storefront.
Completely decoupled from PaymentFlow internal modules.
"""

from typing import Any

import httpx

try:
    from .config import get_merchant_settings
except Exception:
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from config import get_merchant_settings


class MerchantRazorpayClient:
    """Merchant server-side Razorpay API client."""

    def __init__(self, key_id: str | None = None, key_secret: str | None = None):
        settings = get_merchant_settings()
        self.key_id = key_id or settings.razorpay_key_id
        self.key_secret = key_secret or settings.razorpay_key_secret
        self.base_url = "https://api.razorpay.com/v1"

    async def create_order(
        self,
        amount: int,
        currency: str = "INR",
        receipt: str | None = None,
        notes: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a standard Razorpay checkout order with merchant context attached."""
        payload: dict[str, Any] = {
            "amount": amount,
            "currency": currency,
        }
        if receipt:
            payload["receipt"] = receipt
        if notes:
            payload["notes"] = notes

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{self.base_url}/orders",
                json=payload,
                auth=(self.key_id, self.key_secret),
            )
            resp.raise_for_status()
            return resp.json()
