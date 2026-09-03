"""Phase C3.1: Merchant integration contract and authentication boundary tests.

Verifies:
1. Server-to-server Bearer API key authentication.
2. 401 on missing, invalid, or malformed credentials.
3. 403 on disabled merchant account.
4. Merchant identity derived strictly from credentials, not arbitrary body fields.
5. 403 when request body attempts to impersonate another merchant.
6. Validation errors (422) on malformed amount, unsupported currency, or missing fields.
7. Zero leakage of Razorpay Key Secret or PaymentFlow API keys in responses.
8. Multi-merchant credential and configuration isolation.
9. Successful registration of checkout context crossing the HTTP boundary.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from paymentflow.config import get_settings
from paymentflow.main import app
from paymentflow.merchant.models import MerchantProfile, hash_api_key
from paymentflow.merchant.service import MerchantRegistry


@pytest.fixture(autouse=True)
def reset_merchant_registry():
    """Ensure registry is in clean default prototype state for every test."""
    MerchantRegistry.reset_to_default()
    yield
    MerchantRegistry.reset_to_default()


@pytest.mark.asyncio
async def test_verify_endpoint_missing_auth_header():
    """Missing Authorization header must return HTTP 401."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/merchant/v1/verify")
        assert res.status_code == 401
        assert "Bearer" in res.headers.get("www-authenticate", "")
        data = res.json()
        assert "detail" in data
        assert "Missing Authorization header" in data["detail"]


@pytest.mark.asyncio
async def test_verify_endpoint_malformed_auth_scheme():
    """Malformed Authorization header (e.g. Basic instead of Bearer) must return HTTP 401."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get(
            "/merchant/v1/verify",
            headers={"Authorization": "Basic dXNlcjpwYXNz"},
        )
        assert res.status_code == 401
        data = res.json()
        assert "Malformed Authorization header" in data["detail"]


@pytest.mark.asyncio
async def test_verify_endpoint_invalid_api_key():
    """Invalid PaymentFlow API key must return HTTP 401."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get(
            "/merchant/v1/verify",
            headers={"Authorization": "Bearer pf_invalid_test_key_xyz"},
        )
        assert res.status_code == 401
        data = res.json()
        assert "Invalid PaymentFlow API key" in data["detail"]


@pytest.mark.asyncio
async def test_verify_endpoint_disabled_merchant():
    """Disabled merchant account must return HTTP 403."""
    disabled_key = "pf_disabled_merchant_key_2026"
    disabled_merchant = MerchantProfile(
        merchant_id="merchant_disabled_co",
        merchant_name="Disabled Merchant Co",
        api_key_hash=hash_api_key(disabled_key),
        is_active=False,
        razorpay_key_id="rzp_test_disabled_key",
        razorpay_key_secret="secret_disabled_key",
    )
    MerchantRegistry.register_merchant(disabled_merchant)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get(
            "/merchant/v1/verify",
            headers={"Authorization": f"Bearer {disabled_key}"},
        )
        assert res.status_code == 403
        data = res.json()
        assert "disabled" in data["detail"].lower()


@pytest.mark.asyncio
async def test_verify_endpoint_valid_merchant_credentials():
    """Valid merchant credential resolves authenticated context with zero secret leakage."""
    settings = get_settings()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get(
            "/merchant/v1/verify",
            headers={"Authorization": f"Bearer {settings.paymentflow_api_key}"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "authenticated"
        assert data["merchant_id"] == "merchant_demo_store"
        assert data["merchant_name"] == "Acme Fashion Store (Buildathon Demo)"
        assert data["razorpay_key_id"] == settings.razorpay_key_id
        assert data["is_active"] is True

        # STRICT GUARANTEE: Never leak Razorpay Key Secret or PaymentFlow API Key
        raw_response = res.text
        assert settings.razorpay_key_secret not in raw_response
        assert settings.paymentflow_api_key not in raw_response


@pytest.mark.asyncio
async def test_checkout_context_missing_auth():
    """Missing auth on POST /merchant/v1/checkout-context returns HTTP 401."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/merchant/v1/checkout-context",
            json={
                "external_order_id": "order_test_123",
                "amount": 250000,
                "currency": "INR",
            },
        )
        assert res.status_code == 401


@pytest.mark.asyncio
async def test_checkout_context_valid_registration():
    """Valid checkout context request across HTTP boundary succeeds with stable public contract."""
    settings = get_settings()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "external_order_id": "order_M123456",
            "external_payment_id": "pay_attempt_failed_01",
            "amount": 349900,
            "currency": "INR",
            "customer_email": "shopper@example.com",
            "customer_phone": "+919876543210",
            "merchant_reference": "cart_session_8891",
            "error_code": "BAD_REQUEST_ERROR",
            "error_description": "Payment was declined by issuing bank",
            "metadata": {"sku": "SUMMER-JACKET-BLK", "channel": "mobile_app"},
        }
        res = await client.post(
            "/merchant/v1/checkout-context",
            headers={"Authorization": f"Bearer {settings.paymentflow_api_key}"},
            json=payload,
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "accepted"
        assert data["context_id"].startswith("mctx_")
        assert data["merchant_id"] == "merchant_demo_store"
        assert data["external_order_id"] == "order_M123456"
        assert data["external_payment_id"] == "pay_attempt_failed_01"
        assert data["amount"] == 349900
        assert data["currency"] == "INR"
        assert data["customer_email"] == "shopper@example.com"
        assert data["customer_phone"] == "+919876543210"
        assert "registered_at" in data

        # Public contract verification: internal DB/benchmark fields must NOT be present
        for forbidden_key in [
            "eval_run_id",
            "case_source",
            "ai_policy_id",
            "validated_policy_id",
            "evaluation_outcome",
            "simulated",
            "audit_trail",
        ]:
            assert forbidden_key not in data

        # Secret leakage verification
        assert settings.razorpay_key_secret not in res.text
        assert settings.paymentflow_api_key not in res.text


@pytest.mark.asyncio
async def test_checkout_context_impersonation_prevented():
    """Merchant cannot impersonate another merchant via request-body merchant_id."""
    settings = get_settings()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "external_order_id": "order_M777",
            "amount": 100000,
            "currency": "INR",
            "merchant_id": "merchant_victim_store",  # Attempt to spoof identity
        }
        res = await client.post(
            "/merchant/v1/checkout-context",
            headers={"Authorization": f"Bearer {settings.paymentflow_api_key}"},
            json=payload,
        )
        assert res.status_code == 403
        data = res.json()
        assert "Forbidden" in data["detail"]
        assert "does not match authenticated credentials" in data["detail"]


@pytest.mark.asyncio
async def test_checkout_context_matching_body_merchant_id_accepted():
    """If body merchant_id matches authenticated merchant, request is accepted."""
    settings = get_settings()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "external_order_id": "order_M888",
            "amount": 150000,
            "currency": "INR",
            "merchant_id": "merchant_demo_store",  # Matches authenticated identity
        }
        res = await client.post(
            "/merchant/v1/checkout-context",
            headers={"Authorization": f"Bearer {settings.paymentflow_api_key}"},
            json=payload,
        )
        assert res.status_code == 200
        assert res.json()["merchant_id"] == "merchant_demo_store"


@pytest.mark.asyncio
async def test_checkout_context_validation_errors():
    """Malformed amount, unsupported currency, or missing required fields return 422."""
    settings = get_settings()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        auth_header = {"Authorization": f"Bearer {settings.paymentflow_api_key}"}

        # 1. Missing external_order_id
        res1 = await client.post(
            "/merchant/v1/checkout-context",
            headers=auth_header,
            json={"amount": 10000, "currency": "INR"},
        )
        assert res1.status_code == 422

        # 2. Non-positive amount (amount <= 0)
        res2 = await client.post(
            "/merchant/v1/checkout-context",
            headers=auth_header,
            json={"external_order_id": "ord_1", "amount": 0, "currency": "INR"},
        )
        assert res2.status_code == 422

        # 3. Negative amount
        res3 = await client.post(
            "/merchant/v1/checkout-context",
            headers=auth_header,
            json={"external_order_id": "ord_2", "amount": -5000, "currency": "INR"},
        )
        assert res3.status_code == 422

        # 4. Unsupported currency (e.g. USD)
        res4 = await client.post(
            "/merchant/v1/checkout-context",
            headers=auth_header,
            json={"external_order_id": "ord_3", "amount": 5000, "currency": "USD"},
        )
        assert res4.status_code == 422
        assert "Unsupported currency" in res4.text


@pytest.mark.asyncio
async def test_multi_merchant_configuration_isolation():
    """Merchant A's key resolves only Merchant A's credentials; Merchant B resolves only B's."""
    # Register Merchant B
    key_b = "pf_secret_key_merchant_beta_99"
    merchant_b = MerchantProfile(
        merchant_id="merchant_beta_store",
        merchant_name="Beta Electronics",
        api_key_hash=hash_api_key(key_b),
        is_active=True,
        razorpay_key_id="rzp_test_BETA_KEY_ID",
        razorpay_key_secret="secret_BETA_KEY_SECRET",
    )
    MerchantRegistry.register_merchant(merchant_b)

    settings = get_settings()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Request with Merchant A credentials (default demo store)
        res_a = await client.get(
            "/merchant/v1/verify",
            headers={"Authorization": f"Bearer {settings.paymentflow_api_key}"},
        )
        assert res_a.status_code == 200
        data_a = res_a.json()
        assert data_a["merchant_id"] == "merchant_demo_store"
        assert data_a["razorpay_key_id"] == settings.razorpay_key_id

        # Request with Merchant B credentials
        res_b = await client.get(
            "/merchant/v1/verify",
            headers={"Authorization": f"Bearer {key_b}"},
        )
        assert res_b.status_code == 200
        data_b = res_b.json()
        assert data_b["merchant_id"] == "merchant_beta_store"
        assert data_b["razorpay_key_id"] == "rzp_test_BETA_KEY_ID"

        # Verify internal resolution isolation
        creds_a = MerchantRegistry.resolve_razorpay_credentials("merchant_demo_store")
        creds_b = MerchantRegistry.resolve_razorpay_credentials("merchant_beta_store")
        assert creds_a is not None
        assert creds_b is not None
        assert creds_a[0] == settings.razorpay_key_id
        assert creds_b[0] == "rzp_test_BETA_KEY_ID"
        assert creds_a != creds_b
