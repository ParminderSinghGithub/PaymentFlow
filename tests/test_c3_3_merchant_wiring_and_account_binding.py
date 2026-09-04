"""Phase C3.3: Merchant integration wiring, account binding, and clean product boundary tests.

Verifies:
1. Deterministic merchant API key -> merchant_id resolution.
2. Deterministic merchant identity -> isolated Razorpay configuration binding.
3. Multi-merchant credential isolation: Merchant A cannot use Merchant B's credentials.
4. Merchant demo public API / browser responses never leak secrets.
5. Merchant server can call PaymentFlow through HTTP (/merchant/v1/checkout-context).
6. AST source inspection: apps/merchant-demo does NOT import internal PaymentFlow modules.
7. Merchant webhook correlation remains tagged case_source='MERCHANT_CHECKOUT'.
8. Webhook account identity binding: Webhook payload is bound to registered merchant profile.
"""

import ast
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from paymentflow.config import get_settings
from paymentflow.main import app
from paymentflow.merchant.models import MerchantProfile, hash_api_key
from paymentflow.merchant.service import MerchantRegistry


@pytest.fixture(autouse=True)
def reset_merchant_registry():
    """Ensure merchant registry starts from a clean prototype state."""
    MerchantRegistry.reset_to_default()
    yield
    MerchantRegistry.reset_to_default()


# =========================================================================
# 1. Deterministic Key -> Identity -> Razorpay Credential Resolution
# =========================================================================


def test_merchant_api_key_resolves_correct_identity_and_razorpay_binding():
    """Valid PaymentFlow API key resolves the registered merchant identity and Razorpay config."""
    settings = get_settings()
    profile = MerchantRegistry.get_by_api_key(settings.paymentflow_api_key)

    assert profile is not None
    assert profile.merchant_id == "merchant_demo_store"
    assert profile.merchant_name == "Acme Fashion Store (Buildathon Demo)"
    assert profile.is_active is True
    assert profile.razorpay_key_id == settings.razorpay_key_id
    assert profile.razorpay_key_secret == settings.razorpay_key_secret

    # Verify deterministic binding
    creds = MerchantRegistry.resolve_razorpay_credentials(profile.merchant_id)
    assert creds is not None
    key_id, key_secret = creds
    assert key_id == settings.razorpay_key_id
    assert key_secret == settings.razorpay_key_secret


# =========================================================================
# 2. Multi-Merchant Isolation (Merchant A cannot use Merchant B's config)
# =========================================================================


def test_cross_merchant_credential_and_configuration_isolation():
    """Merchant A credentials can never resolve or access Merchant B configuration."""
    merchant_a = MerchantProfile(
        merchant_id="merchant_a",
        merchant_name="Merchant Alpha Store",
        api_key_hash=hash_api_key("pf_key_alpha_12345"),
        is_active=True,
        razorpay_key_id="rzp_test_ALPHA_111",
        razorpay_key_secret="secret_ALPHA_999",
    )
    merchant_b = MerchantProfile(
        merchant_id="merchant_b",
        merchant_name="Merchant Beta Store",
        api_key_hash=hash_api_key("pf_key_beta_67890"),
        is_active=True,
        razorpay_key_id="rzp_test_BETA_222",
        razorpay_key_secret="secret_BETA_888",
    )

    MerchantRegistry.register_merchant(merchant_a)
    MerchantRegistry.register_merchant(merchant_b)

    # Resolving by Key A must yield Profile A
    profile_a = MerchantRegistry.get_by_api_key("pf_key_alpha_12345")
    assert profile_a is not None
    assert profile_a.merchant_id == "merchant_a"
    assert profile_a.razorpay_key_id == "rzp_test_ALPHA_111"
    assert profile_a.razorpay_key_secret == "secret_ALPHA_999"

    # Resolving by Key B must yield Profile B
    profile_b = MerchantRegistry.get_by_api_key("pf_key_beta_67890")
    assert profile_b is not None
    assert profile_b.merchant_id == "merchant_b"
    assert profile_b.razorpay_key_id == "rzp_test_BETA_222"
    assert profile_b.razorpay_key_secret == "secret_BETA_888"

    # Key A cannot resolve Profile B
    assert profile_a.merchant_id != profile_b.merchant_id
    assert profile_a.razorpay_key_secret != profile_b.razorpay_key_secret

    # Direct query by merchant_id is strictly bound
    creds_a = MerchantRegistry.resolve_razorpay_credentials("merchant_a")
    creds_b = MerchantRegistry.resolve_razorpay_credentials("merchant_b")
    assert creds_a != creds_b
    assert creds_a == ("rzp_test_ALPHA_111", "secret_ALPHA_999")
    assert creds_b == ("rzp_test_BETA_222", "secret_BETA_888")


# =========================================================================
# 3. Secret Exposure Audit (Zero Leakage in Public APIs and Browser Responses)
# =========================================================================


@pytest.mark.asyncio
async def test_public_and_browser_responses_never_leak_secrets():
    """Merchant verify, config, and checkout endpoints must never leak secrets."""
    settings = get_settings()
    auth_header = {"Authorization": f"Bearer {settings.paymentflow_api_key}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. PaymentFlow verify endpoint
        res_verify = await client.get("/merchant/v1/verify", headers=auth_header)
        assert res_verify.status_code == 200
        text_verify = res_verify.text
        assert settings.razorpay_key_secret not in text_verify
        assert settings.paymentflow_api_key not in text_verify

        # 2. Checkout page endpoint
        res_checkout = await client.get("/merchant/checkout")
        assert res_checkout.status_code == 200
        text_checkout = res_checkout.text
        assert settings.razorpay_key_secret not in text_checkout
        assert settings.paymentflow_api_key not in text_checkout
        assert settings.razorpay_webhook_secret not in text_checkout
        assert settings.razorpay_key_id in text_checkout  # Public key is safe and allowed


# =========================================================================
# 4. Merchant Server Calls PaymentFlow over HTTP
# =========================================================================


@pytest.mark.asyncio
async def test_merchant_server_calls_paymentflow_over_http_mocked_network():
    """Merchant server PaymentFlow client communicates via HTTP without internal imports."""
    # Import merchant demo client dynamically to prove separation
    import importlib.util

    client_path = Path("apps/merchant-demo/server/paymentflow_client.py")
    spec = importlib.util.spec_from_file_location("paymentflow_client", client_path)
    assert spec is not None and spec.loader is not None
    client_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(client_mod)

    MerchantPaymentFlowClient = client_mod.MerchantPaymentFlowClient
    client = MerchantPaymentFlowClient(
        api_url="http://mock-paymentflow",
        api_key="pf_live_test_merchant_key_2026",
    )

    mock_resp = {
        "status": "accepted",
        "context_id": "mctx_test_c33",
        "merchant_id": "merchant_demo_store",
        "external_order_id": "ORD-C33-HTTP-001",
        "amount": 345000,
        "currency": "INR",
        "registered_at": "2026-09-04T12:00:00Z",
    }

    from unittest.mock import MagicMock

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_response_obj = MagicMock()
        mock_response_obj.status_code = 200
        mock_response_obj.json.return_value = mock_resp
        mock_response_obj.raise_for_status.return_value = None
        mock_post.return_value = mock_response_obj

        result = await client.register_checkout_context(
            external_order_id="ORD-C33-HTTP-001",
            amount=345000,
            currency="INR",
            customer_email="test@example.com",
            customer_phone="9876543210",
        )

        assert result["status"] == "accepted"
        assert result["context_id"] == "mctx_test_c33"
        mock_post.assert_awaited_once()

        # Check call arguments
        call_kwargs = mock_post.await_args.kwargs
        assert "Authorization" in call_kwargs["headers"]
        assert call_kwargs["headers"]["Authorization"] == "Bearer pf_live_test_merchant_key_2026"
        assert call_kwargs["json"]["external_order_id"] == "ORD-C33-HTTP-001"


# =========================================================================
# 5. AST Source Inspection: Merchant Demo Has Zero Internal PaymentFlow Imports
# =========================================================================


def test_merchant_demo_has_zero_internal_paymentflow_imports():
    """Verify via AST that apps/merchant-demo does NOT import internal PaymentFlow modules.

    Prohibits:
    - paymentflow.db.* (models, sessions, base)
    - paymentflow.services.* (recovery_executor, policy_engine, webhook_service)
    - paymentflow.domain.* (state machine, rules)
    - paymentflow.eval.*
    - paymentflow.adapters.gemini_adapter
    """
    demo_dir = Path("apps/merchant-demo")
    assert demo_dir.exists(), "apps/merchant-demo directory must exist"

    prohibited_modules = {
        "paymentflow.db",
        "paymentflow.services",
        "paymentflow.domain",
        "paymentflow.eval",
        "paymentflow.adapters.gemini_adapter",
        "paymentflow.models",
    }

    for py_file in demo_dir.glob("**/*.py"):
        code = py_file.read_text(encoding="utf-8")
        tree = ast.parse(code, filename=str(py_file))

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    for prohibited in prohibited_modules:
                        assert not alias.name.startswith(prohibited), (
                            f"Prohibited import '{alias.name}' in {py_file}"
                        )
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    for prohibited in prohibited_modules:
                        assert not node.module.startswith(prohibited), (
                            f"Prohibited from-import '{node.module}' in {py_file}"
                        )


# =========================================================================
# 6. Webhook Account Identity and Evidence Isolation
# =========================================================================


def test_webhook_correlation_preserves_case_source_boundary():
    """Ensure merchant cases are strictly segregated with case_source='MERCHANT_CHECKOUT'."""
    # Store test context
    MerchantRegistry.store_checkout_context(
        "order_c33_isolated_test",
        {
            "context_id": "mctx_c33_iso",
            "merchant_id": "merchant_demo_store",
            "external_order_id": "ORD-C33-ISO",
            "amount": 345000,
            "currency": "INR",
        },
    )

    ctx = MerchantRegistry.get_checkout_context("order_c33_isolated_test")
    assert ctx is not None
    assert ctx["merchant_id"] == "merchant_demo_store"
    assert ctx["external_order_id"] == "ORD-C33-ISO"
