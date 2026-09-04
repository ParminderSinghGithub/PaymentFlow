"""Merchant-side PaymentFlow integration client.

Communicates with PaymentFlow solely over HTTP using the server-to-server API key.
Never imports PaymentFlow internal Python modules (database models, state machine, etc.).
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


class MerchantPaymentFlowClient:
    """Client for calling PaymentFlow Merchant Integration APIs over HTTP."""

    def __init__(self, api_url: str | None = None, api_key: str | None = None):
        settings = get_merchant_settings()
        self.api_url = (api_url or settings.paymentflow_api_url).rstrip("/")
        self.api_key = api_key or settings.paymentflow_api_key

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def verify_credentials(self) -> dict[str, Any]:
        """Verify that merchant API credentials are valid and active."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{self.api_url}/merchant/v1/verify",
                headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.json()

    async def register_checkout_context(
        self,
        external_order_id: str,
        amount: int,
        currency: str = "INR",
        customer_email: str | None = None,
        customer_phone: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Register checkout attempt context with PaymentFlow for recovery monitoring."""
        payload: dict[str, Any] = {
            "external_order_id": external_order_id,
            "amount": amount,
            "currency": currency,
        }
        if customer_email:
            payload["customer_email"] = customer_email
        if customer_phone:
            payload["customer_phone"] = customer_phone
        if metadata:
            payload["metadata"] = metadata

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{self.api_url}/merchant/v1/checkout-context",
                json=payload,
                headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.json()
