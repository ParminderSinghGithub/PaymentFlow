"""Phase C3.2: Real merchant checkout failure ingress tests.

Verifies:
1. Merchant order creation API (POST /merchant/v1/orders).
2. Minimal merchant checkout HTML page (GET /merchant/checkout).
3. Webhook ingestion of real-format payment.failed event with merchant context correlation.
4. Zero recovery execution, zero recovery payment links, zero credit (recovered_amount is None/0).
5. State transition strictly at FAILED_INGESTED.
6. Webhook-level database idempotency on duplicate event delivery.
7. Airtight evidence boundary: Merchant checkout cases are tagged case_source='MERCHANT_CHECKOUT'
   and never pollute canonical evaluation benchmark runs.
"""

import json
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from paymentflow.config import get_settings
from paymentflow.db.models import AuditEventModel, RecoveryCaseModel
from paymentflow.db.session import get_db_session
from paymentflow.domain.enums import CaseState
from paymentflow.main import app
from paymentflow.merchant.service import MerchantRegistry
from paymentflow.services.webhook_service import WebhookService


@pytest.fixture(autouse=True)
def reset_merchant_registry():
    """Ensure registry is in clean default state."""
    MerchantRegistry.reset_to_default()
    yield
    MerchantRegistry.reset_to_default()


@pytest.mark.asyncio
async def test_create_merchant_order_unauthorized():
    """POST /merchant/v1/orders without Bearer auth must return 401."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/merchant/v1/orders",
            json={
                "amount": 345000,
                "currency": "INR",
                "external_order_id": "ORD-C32-TEST-01",
            },
        )
        assert res.status_code == 401


@pytest.mark.asyncio
async def test_create_merchant_order_success():
    """POST /merchant/v1/orders creates Razorpay order and registers checkout context."""
    settings = get_settings()
    auth_header = {"Authorization": f"Bearer {settings.paymentflow_api_key}"}

    mock_rzp_order = {
        "id": "order_test_rzp_c32_123",
        "entity": "order",
        "amount": 345000,
        "amount_paid": 0,
        "amount_due": 345000,
        "currency": "INR",
        "receipt": "ORD-C32-FAIL-3450",
        "status": "created",
        "notes": {
            "merchant_id": "merchant_prototype_default",
            "external_order_id": "ORD-C32-FAIL-3450",
        },
    }

    with patch(
        "paymentflow.adapters.razorpay_adapter.RazorpayAdapter.create_order",
        new_callable=AsyncMock,
        return_value=mock_rzp_order,
    ) as mock_create:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.post(
                "/merchant/v1/orders",
                headers=auth_header,
                json={
                    "amount": 345000,
                    "currency": "INR",
                    "external_order_id": "ORD-C32-FAIL-3450",
                    "customer_name": "Priya Sharma",
                    "customer_email": "priya.sharma@example.com",
                    "customer_phone": "9876543210",
                },
            )

            assert res.status_code == 201
            data = res.json()
            assert data["status"] == "created"
            assert data["razorpay_order_id"] == "order_test_rzp_c32_123"
            assert data["external_order_id"] == "ORD-C32-FAIL-3450"
            assert data["amount"] == 345000
            assert data["currency"] == "INR"
            assert data["razorpay_key_id"] == settings.razorpay_key_id
            assert "context_id" in data
            assert "/merchant/checkout?context_id=" in data["checkout_url"]

            # Verify context is stored in MerchantRegistry
            ctx = MerchantRegistry.get_checkout_context(data["context_id"])
            assert ctx is not None
            assert ctx["merchant_id"] == "merchant_demo_store"
            assert ctx["external_order_id"] == "ORD-C32-FAIL-3450"
            assert ctx["razorpay_order_id"] == "order_test_rzp_c32_123"

            mock_create.assert_awaited_once()


@pytest.mark.asyncio
async def test_merchant_checkout_page_renders_html_with_key_and_no_secrets():
    """GET /merchant/checkout returns HTML with Checkout.js and zero secret leakage."""
    settings = get_settings()

    # Pre-store a context
    context_id = "mctx_test_checkout_c32"
    MerchantRegistry.store_checkout_context(
        context_id,
        {
            "context_id": context_id,
            "merchant_id": "merchant_prototype_default",
            "merchant_name": "Test Merchant Storefront",
            "external_order_id": "ORD-C32-FAIL-3450",
            "razorpay_order_id": "order_test_rzp_c32_123",
            "amount": 345000,
            "currency": "INR",
            "customer_name": "Priya Sharma",
            "customer_email": "priya.sharma@example.com",
            "customer_phone": "9876543210",
            "razorpay_key_id": settings.razorpay_key_id,
        },
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get(f"/merchant/checkout?context_id={context_id}")
        assert res.status_code == 200
        html = res.text

        # Verify Checkout.js inclusion and UI elements
        assert "https://checkout.razorpay.com/v1/checkout.js" in html
        assert "failure@razorpay" in html
        assert "ORD-C32-FAIL-3450" in html
        assert "₹3,450.00" in html
        assert settings.razorpay_key_id in html

        # Verify strict zero secret leakage
        assert settings.razorpay_key_secret not in html
        assert settings.paymentflow_api_key not in html
        assert settings.razorpay_webhook_secret not in html


@pytest.mark.asyncio
async def test_merchant_payment_failed_webhook_ingestion_and_correlation():
    """Webhook ingestion of payment.failed correlates merchant context and creates case."""
    context_id = "mctx_c32_webhook_test"
    order_id = "order_rzp_fail_c32_789"
    payment_id = "pay_rzp_fail_c32_456"

    MerchantRegistry.store_checkout_context(
        context_id,
        {
            "context_id": context_id,
            "merchant_id": "merchant_prototype_default",
            "merchant_name": "PaymentFlow Prototype Storefront",
            "external_order_id": "ORD-C32-FAIL-3450",
            "razorpay_order_id": order_id,
            "amount": 345000,
            "currency": "INR",
        },
    )

    webhook_payload = {
        "entity": "event",
        "account_id": "acc_test_merchant_123",
        "event": "payment.failed",
        "contains": ["payment"],
        "payload": {
            "payment": {
                "entity": {
                    "id": payment_id,
                    "entity": "payment",
                    "amount": 345000,
                    "currency": "INR",
                    "status": "failed",
                    "order_id": order_id,
                    "method": "upi",
                    "captured": False,
                    "description": "Order ORD-C32-FAIL-3450",
                    "email": "priya.sharma@example.com",
                    "contact": "+919876543210",
                    "error_code": "BAD_REQUEST_ERROR",
                    "error_description": "Payment was declined by customer bank",
                    "error_source": "bank",
                    "error_step": "payment_authorization",
                    "error_reason": "payment_failed",
                    "notes": {
                        "merchant_id": "merchant_prototype_default",
                        "external_order_id": "ORD-C32-FAIL-3450",
                    },
                }
            }
        },
        "created_at": 1725430000,
    }

    raw_body = json.dumps(webhook_payload).encode()

    async for session in get_db_session():
        service = WebhookService(db_session=session)
        result = await service.process_webhook(
            raw_body=raw_body,
            payload=webhook_payload,
            signature_verified=True,
        )

        assert result.status == "ok"
        assert result.event_type == "payment.failed"
        assert not result.is_duplicate
        assert result.case_id == f"case_{payment_id}"
        assert result.state == CaseState.FAILED_INGESTED.value

        # Inspect persisted RecoveryCaseModel
        q_case = select(RecoveryCaseModel).where(RecoveryCaseModel.case_id == result.case_id)
        res_case = await session.execute(q_case)
        case = res_case.scalar_one_or_none()

        assert case is not None
        assert case.failed_payment_id == payment_id
        assert case.order_id == order_id
        assert case.amount == 345000
        assert case.currency == "INR"
        assert case.payment_method == "upi"
        assert case.failure_code == "BAD_REQUEST_ERROR"
        assert case.state == CaseState.FAILED_INGESTED.value
        assert case.case_source == "MERCHANT_CHECKOUT"
        assert case.recovered_amount is None or case.recovered_amount == 0
        assert case.payment_link_id is None

        # Verify failure_context correlation
        fc = case.failure_context
        assert fc["merchant_id"] == "merchant_prototype_default"
        assert fc["external_order_id"] == "ORD-C32-FAIL-3450"
        assert fc["case_source"] == "MERCHANT_CHECKOUT"

        # Verify AuditEvent
        q_audit = select(AuditEventModel).where(AuditEventModel.case_id == case.case_id)
        res_audit = await session.execute(q_audit)
        audit = res_audit.scalar_one_or_none()

        assert audit is not None
        assert audit.event_type == "WEBHOOK_INGESTED"
        assert audit.action == "INGEST_FAILED_PAYMENT"
        assert audit.details["merchant_id"] == "merchant_prototype_default"
        assert audit.details["external_order_id"] == "ORD-C32-FAIL-3450"
        assert audit.details["case_source"] == "MERCHANT_CHECKOUT"

        # Verify Idempotency on duplicate delivery
        dup_result = await service.process_webhook(
            raw_body=raw_body,
            payload=webhook_payload,
            signature_verified=True,
        )
        assert dup_result.status == "ok"
        assert dup_result.is_duplicate is True
        break
