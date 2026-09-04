"""Razorpay API integration adapter and webhook signature verification."""

import hashlib
import hmac
import logging
from typing import Any

import httpx

from paymentflow.config import Settings, get_settings
from paymentflow.domain.exceptions import (
    RazorpayAdapterError,
    RazorpayAPIError,
    RazorpayAuthError,
    RazorpayNotFoundError,
    RazorpayRateLimitError,
)

logger = logging.getLogger(__name__)


def verify_webhook_signature(raw_body: bytes, signature: str | None, secret: str | None) -> bool:
    """Verify Razorpay webhook signature using HMAC-SHA256 against the raw request body."""
    if not signature or not secret:
        logger.warning("Missing signature or webhook secret during verification.")
        return False

    try:
        expected_signature = hmac.new(
            key=secret.encode("utf-8"),
            msg=raw_body,
            digestmod=hashlib.sha256,
        ).hexdigest()

        is_valid = hmac.compare_digest(expected_signature, signature)
        if not is_valid:
            logger.warning("Webhook signature mismatch.")
        return is_valid
    except Exception as exc:
        logger.error(f"Error during webhook signature calculation: {exc}")
        return False


class RazorpayAdapter:
    """Async HTTP adapter for Razorpay REST APIs."""

    def __init__(
        self,
        settings: Settings | None = None,
        key_id: str | None = None,
        key_secret: str | None = None,
        base_url: str = "https://api.razorpay.com/v1",
        timeout: float = 10.0,
        http_client: httpx.AsyncClient | None = None,
    ):
        self.settings = settings or get_settings()
        self.key_id = key_id or self.settings.razorpay_key_id
        self.key_secret = key_secret or self.settings.razorpay_key_secret
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._external_client = http_client

    def _get_auth(self) -> tuple[str, str]:
        """Return HTTP Basic Auth tuple."""
        return (self.key_id, self.key_secret)

    async def _request(self, method: str, endpoint: str, **kwargs: Any) -> dict[str, Any]:
        """Execute authenticated HTTP request with error handling and normalization."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        auth = self._get_auth()

        client = self._external_client or httpx.AsyncClient(timeout=self.timeout)
        should_close = self._external_client is None

        try:
            response = await client.request(method, url, auth=auth, **kwargs)

            if response.status_code == 401:
                logger.error("Razorpay authentication failed (401). Check API keys.")
                raise RazorpayAuthError("Authentication with Razorpay API failed.")
            if response.status_code == 404:
                logger.warning(f"Razorpay resource not found at {endpoint} (404).")
                raise RazorpayNotFoundError(f"Razorpay resource not found: {endpoint}")
            if response.status_code == 429:
                logger.warning("Razorpay rate limit exceeded (429).")
                raise RazorpayRateLimitError("Razorpay API rate limit exceeded.")
            if response.status_code >= 400:
                error_msg = response.text
                try:
                    err_json = response.json()
                    error_msg = err_json.get("error", {}).get("description", response.text)
                except Exception:
                    pass
                logger.error(f"Razorpay API error ({response.status_code}): {error_msg}")
                raise RazorpayAPIError(response.status_code, error_msg)

            return response.json()
        except httpx.TimeoutException as exc:
            logger.error(f"Razorpay API request timed out: {exc}")
            raise RazorpayAdapterError(f"Razorpay API request timed out: {exc}") from exc
        except httpx.RequestError as exc:
            logger.error(f"Razorpay network communication failed: {exc}")
            raise RazorpayAdapterError(f"Razorpay network communication failed: {exc}") from exc
        finally:
            if should_close:
                await client.aclose()

    async def get_payment(self, payment_id: str) -> dict[str, Any]:
        """Fetch payment details by payment ID."""
        if not payment_id:
            raise ValueError("payment_id must not be empty.")
        logger.info(f"Fetching payment details for: {payment_id}")
        return await self._request("GET", f"payments/{payment_id}")

    async def get_order(self, order_id: str) -> dict[str, Any]:
        """Fetch order details by order ID."""
        if not order_id:
            raise ValueError("order_id must not be empty.")
        logger.info(f"Fetching order details for: {order_id}")
        return await self._request("GET", f"orders/{order_id}")

    async def create_order(
        self,
        amount: int,
        currency: str = "INR",
        receipt: str | None = None,
        notes: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create standard Razorpay Order."""
        if amount <= 0:
            raise ValueError("amount must be a positive integer in paise.")
        if currency != "INR":
            raise ValueError("Only INR currency is supported.")

        payload: dict[str, Any] = {
            "amount": amount,
            "currency": currency,
        }
        if receipt:
            payload["receipt"] = receipt
        if notes:
            payload["notes"] = notes

        logger.info(f"Creating Razorpay Order: amount={amount}, receipt={receipt}")
        return await self._request("POST", "orders", json=payload)

    async def create_payment_link(
        self,
        amount: int,
        currency: str = "INR",
        description: str | None = None,
        customer: dict[str, Any] | None = None,
        reference_id: str | None = None,
        notes: dict[str, Any] | None = None,
        expire_by: int | None = None,
        notify: dict[str, bool] | None = None,
    ) -> dict[str, Any]:
        """Create a standard Razorpay Payment Link."""
        if amount <= 0:
            raise ValueError("amount must be a positive integer in paise.")
        if currency != "INR":
            raise ValueError("Only INR currency is supported.")

        notify_config = notify if notify is not None else {"sms": False, "email": False}

        payload: dict[str, Any] = {
            "amount": amount,
            "currency": currency,
            "description": description or "Payment Recovery Link",
            "reminder_enable": False,
            "notify": notify_config,
        }
        if reference_id:
            payload["reference_id"] = reference_id
        if customer:
            payload["customer"] = customer
        if notes:
            payload["notes"] = notes
        if expire_by:
            payload["expire_by"] = expire_by

        logger.info(
            f"Creating Razorpay Payment Link: amount={amount}, reference_id={reference_id}, "
            f"notify={notify_config}"
        )
        return await self._request("POST", "payment_links", json=payload)

    async def notify_payment_link(
        self, payment_link_id: str, medium: str = "sms"
    ) -> dict[str, Any]:
        """Send explicit notification for a payment link via Razorpay notify_by endpoint.

        Used only as fallback or resend mechanism when primary creation notify did not dispatch.
        """
        if not payment_link_id:
            raise ValueError("payment_link_id must not be empty.")
        if medium not in ("sms", "email"):
            raise ValueError("medium must be 'sms' or 'email'.")
        logger.info(f"Triggering Razorpay fallback notification for {payment_link_id} via {medium}")
        return await self._request("POST", f"payment_links/{payment_link_id}/notify_by/{medium}")

    async def get_payment_link(self, payment_link_id: str) -> dict[str, Any]:
        """Fetch payment link details by ID."""
        if not payment_link_id:
            raise ValueError("payment_link_id must not be empty.")
        logger.info(f"Fetching payment link details for: {payment_link_id}")
        return await self._request("GET", f"payment_links/{payment_link_id}")
