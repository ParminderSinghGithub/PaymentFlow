"""Tests for Razorpay adapter and webhook signature verification."""

import hashlib
import hmac

import httpx
import pytest

from paymentflow.adapters.razorpay_adapter import RazorpayAdapter, verify_webhook_signature
from paymentflow.config import Settings
from paymentflow.domain.exceptions import (
    RazorpayAdapterError,
    RazorpayAPIError,
    RazorpayAuthError,
    RazorpayNotFoundError,
    RazorpayRateLimitError,
)


def generate_test_signature(body: bytes, secret: str) -> str:
    """Helper to compute valid HMAC-SHA256 signature for test payloads."""
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def test_verify_webhook_signature_valid():
    """Verify correct HMAC signature passes validation."""
    secret = "my_test_secret_123"
    body = b'{"event":"payment.failed","id":"evt_123"}'
    sig = generate_test_signature(body, secret)

    assert verify_webhook_signature(body, sig, secret) is True


def test_verify_webhook_signature_invalid():
    """Verify invalid or tampered HMAC signature fails validation."""
    secret = "my_test_secret_123"
    body = b'{"event":"payment.failed","id":"evt_123"}'
    wrong_sig = "a" * 64

    assert verify_webhook_signature(body, wrong_sig, secret) is False


def test_verify_webhook_signature_missing_inputs():
    """Verify missing signature or secret fails safely without raising exceptions."""
    body = b'{"event":"payment.failed"}'
    assert verify_webhook_signature(body, None, "secret") is False
    assert verify_webhook_signature(body, "sig", None) is False
    assert verify_webhook_signature(body, "", "secret") is False
    assert verify_webhook_signature(body, "sig", "") is False


@pytest.mark.asyncio
async def test_razorpay_adapter_get_payment_success():
    """Verify get_payment parses successful Razorpay API response."""
    mock_payment = {
        "id": "pay_test123",
        "entity": "payment",
        "amount": 50000,
        "currency": "INR",
        "status": "failed",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/payments/pay_test123"
        assert request.headers.get("authorization") is not None
        return httpx.Response(200, json=mock_payment)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        adapter = RazorpayAdapter(
            settings=Settings(razorpay_key_id="key1", razorpay_key_secret="sec1"),
            http_client=client,
        )
        payment = await adapter.get_payment("pay_test123")
        assert payment["id"] == "pay_test123"
        assert payment["amount"] == 50000


@pytest.mark.asyncio
async def test_razorpay_adapter_get_order_success():
    """Verify get_order parses successful Razorpay API response."""
    mock_order = {
        "id": "order_test123",
        "entity": "order",
        "amount": 50000,
        "status": "created",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/orders/order_test123"
        return httpx.Response(200, json=mock_order)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        adapter = RazorpayAdapter(
            settings=Settings(razorpay_key_id="key1", razorpay_key_secret="sec1"),
            http_client=client,
        )
        order = await adapter.get_order("order_test123")
        assert order["id"] == "order_test123"


@pytest.mark.asyncio
async def test_razorpay_adapter_auth_error_401():
    """Verify 401 response raises RazorpayAuthError."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"description": "Invalid key or secret"}})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        adapter = RazorpayAdapter(
            settings=Settings(razorpay_key_id="bad", razorpay_key_secret="bad"),
            http_client=client,
        )
        with pytest.raises(RazorpayAuthError):
            await adapter.get_payment("pay_123")


@pytest.mark.asyncio
async def test_razorpay_adapter_not_found_404():
    """Verify 404 response raises RazorpayNotFoundError."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": {"description": "Payment not found"}})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        adapter = RazorpayAdapter(http_client=client)
        with pytest.raises(RazorpayNotFoundError):
            await adapter.get_payment("pay_nonexistent")


@pytest.mark.asyncio
async def test_razorpay_adapter_rate_limit_429():
    """Verify 429 response raises RazorpayRateLimitError."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": {"description": "Too many requests"}})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        adapter = RazorpayAdapter(http_client=client)
        with pytest.raises(RazorpayRateLimitError):
            await adapter.get_payment("pay_123")


@pytest.mark.asyncio
async def test_razorpay_adapter_server_error_500():
    """Verify 500 response raises RazorpayAPIError."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="Internal Server Error")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        adapter = RazorpayAdapter(http_client=client)
        with pytest.raises(RazorpayAPIError) as exc_info:
            await adapter.get_payment("pay_123")
        assert exc_info.value.status_code == 500


@pytest.mark.asyncio
async def test_razorpay_adapter_timeout():
    """Verify network timeout raises RazorpayAdapterError."""
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("Connection timed out")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        adapter = RazorpayAdapter(http_client=client)
        with pytest.raises(RazorpayAdapterError):
            await adapter.get_payment("pay_123")


@pytest.mark.asyncio
async def test_razorpay_adapter_create_payment_link_success():
    """Verify create_payment_link parses successful response."""
    mock_link = {
        "id": "plink_test999",
        "short_url": "https://rzp.io/i/test999",
        "amount": 250000,
        "currency": "INR",
        "status": "created",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/payment_links"
        assert request.method == "POST"
        return httpx.Response(200, json=mock_link)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        adapter = RazorpayAdapter(
            settings=Settings(razorpay_key_id="k", razorpay_key_secret="s"),
            http_client=client,
        )
        res = await adapter.create_payment_link(
            amount=250000,
            currency="INR",
            reference_id="case_123",
        )
        assert res["id"] == "plink_test999"
        assert res["short_url"] == "https://rzp.io/i/test999"


@pytest.mark.asyncio
async def test_razorpay_adapter_get_payment_link_success():
    """Verify get_payment_link parses successful response."""
    mock_link = {
        "id": "plink_test999",
        "status": "created",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/payment_links/plink_test999"
        assert request.method == "GET"
        return httpx.Response(200, json=mock_link)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        adapter = RazorpayAdapter(
            settings=Settings(razorpay_key_id="k", razorpay_key_secret="s"),
            http_client=client,
        )
        res = await adapter.get_payment_link("plink_test999")
        assert res["id"] == "plink_test999"

