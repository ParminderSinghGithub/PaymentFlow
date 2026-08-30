"""Integration tests for Razorpay webhook ingestion and idempotency."""

import hashlib
import hmac
import json

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from paymentflow.config import Settings
from paymentflow.db.models import AuditEventModel, RecoveryCaseModel, WebhookEventModel
from paymentflow.db.session import get_sessionmaker


def make_signed_headers(body: bytes, secret: str) -> dict[str, str]:
    """Helper to generate headers with correct Razorpay signature."""
    sig = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return {
        "Content-Type": "application/json",
        "X-Razorpay-Signature": sig,
    }


def sample_payment_failed_payload(
    event_id: str = "evt_failed_001",
    payment_id: str = "pay_fail_1001",
    amount: int = 499900,
) -> dict:
    """Generate a realistic Razorpay payment.failed webhook payload."""
    return {
        "entity": "event",
        "account_id": "acc_test_merchant",
        "event": "payment.failed",
        "id": event_id,
        "contains": ["payment"],
        "payload": {
            "payment": {
                "entity": {
                    "id": payment_id,
                    "entity": "payment",
                    "amount": amount,
                    "currency": "INR",
                    "status": "failed",
                    "order_id": "order_test_2001",
                    "invoice_id": None,
                    "international": False,
                    "method": "card",
                    "amount_refunded": 0,
                    "captured": False,
                    "description": "Test checkout item",
                    "card_id": "card_test_3001",
                    "bank": None,
                    "wallet": None,
                    "vpa": None,
                    "email": "customer@example.com",
                    "contact": "+919876543210",
                    "customer_id": "cust_test_4001",
                    "notes": {"merchant_order_id": "M-1234"},
                    "error_code": "BAD_REQUEST_ERROR",
                    "error_description": "Payment was declined by the issuer bank",
                    "error_source": "bank",
                    "error_step": "payment_authorization",
                    "error_reason": "card_declined",
                    "created_at": 1725000000,
                }
            }
        },
        "created_at": 1725000000,
    }


@pytest.mark.asyncio
async def test_valid_payment_failed_webhook(client: AsyncClient, test_settings: Settings):
    """Verify valid payment.failed webhook creates recovery case and audit trail."""
    payload_dict = sample_payment_failed_payload(
        event_id="evt_valid_001",
        payment_id="pay_valid_001",
        amount=150000,
    )
    raw_body = json.dumps(payload_dict).encode("utf-8")
    headers = make_signed_headers(raw_body, test_settings.razorpay_webhook_secret)

    response = await client.post("/webhooks/razorpay", content=raw_body, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["event_id"] == "evt_valid_001"
    assert data["event_type"] == "payment.failed"
    assert data["is_duplicate"] is False
    assert data["case_id"] == "case_pay_valid_001"
    assert data["state"] == "FAILED_INGESTED"

    # Verify Database State
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        # Webhook event
        event = await session.get(WebhookEventModel, "evt_valid_001")
        assert event is not None
        assert event.status == "PROCESSED"
        assert event.signature_verified is True

        # Recovery case
        case = await session.get(RecoveryCaseModel, "case_pay_valid_001")
        assert case is not None
        assert case.failed_payment_id == "pay_valid_001"
        assert case.amount == 150000
        assert case.currency == "INR"
        assert case.state == "FAILED_INGESTED"
        assert case.failure_code == "BAD_REQUEST_ERROR"

        # Audit event
        audit_res = await session.execute(
            select(AuditEventModel).where(AuditEventModel.case_id == "case_pay_valid_001")
        )
        audits = audit_res.scalars().all()
        assert len(audits) >= 1
        assert audits[0].event_type == "WEBHOOK_INGESTED"
        assert audits[0].actor == "system"


@pytest.mark.asyncio
async def test_webhook_missing_signature_rejected(client: AsyncClient):
    """Verify webhook with missing signature header returns 400."""
    payload_dict = sample_payment_failed_payload(event_id="evt_nosig_001")
    raw_body = json.dumps(payload_dict).encode("utf-8")

    response = await client.post(
        "/webhooks/razorpay",
        content=raw_body,
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 400
    assert "Missing X-Razorpay-Signature" in response.json()["detail"]


@pytest.mark.asyncio
async def test_webhook_invalid_signature_rejected(client: AsyncClient):
    """Verify webhook with tampered/invalid signature returns 400."""
    payload_dict = sample_payment_failed_payload(event_id="evt_invalidsig_001")
    raw_body = json.dumps(payload_dict).encode("utf-8")

    response = await client.post(
        "/webhooks/razorpay",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": "invalid_signature_hash_value_12345",
        },
    )
    assert response.status_code == 400
    assert "Invalid webhook signature" in response.json()["detail"]


@pytest.mark.asyncio
async def test_webhook_malformed_json(client: AsyncClient, test_settings: Settings):
    """Verify malformed JSON request body returns 400."""
    raw_body = b"not-a-valid-json-string{{{"
    headers = make_signed_headers(raw_body, test_settings.razorpay_webhook_secret)

    response = await client.post("/webhooks/razorpay", content=raw_body, headers=headers)
    assert response.status_code == 400
    assert "Malformed JSON" in response.json()["detail"]


@pytest.mark.asyncio
async def test_webhook_missing_payment_fields(client: AsyncClient, test_settings: Settings):
    """Verify payment.failed missing required payment fields returns 400."""
    payload = {
        "event": "payment.failed",
        "id": "evt_bad_payload",
        "payload": {"payment": {"entity": {}}},  # Missing id and amount
    }
    raw_body = json.dumps(payload).encode("utf-8")
    headers = make_signed_headers(raw_body, test_settings.razorpay_webhook_secret)

    response = await client.post("/webhooks/razorpay", content=raw_body, headers=headers)
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_duplicate_webhook_idempotency(client: AsyncClient, test_settings: Settings):
    """Verify replaying the exact same webhook is idempotent and performs zero duplicate work."""
    payload_dict = sample_payment_failed_payload(
        event_id="evt_dup_test_001",
        payment_id="pay_dup_test_001",
        amount=250000,
    )
    raw_body = json.dumps(payload_dict).encode("utf-8")
    headers = make_signed_headers(raw_body, test_settings.razorpay_webhook_secret)

    # First delivery
    resp1 = await client.post("/webhooks/razorpay", content=raw_body, headers=headers)
    assert resp1.status_code == 200
    assert resp1.json()["is_duplicate"] is False

    # Second delivery (duplicate replay)
    resp2 = await client.post("/webhooks/razorpay", content=raw_body, headers=headers)
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["is_duplicate"] is True
    assert "Duplicate event ignored" in data2["message"]

    # Verify exactly ONE recovery case and ONE webhook event exists in database
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        case_count = await session.scalar(
            select(func.count()).where(RecoveryCaseModel.failed_payment_id == "pay_dup_test_001")
        )
        assert case_count == 1

        event_count = await session.scalar(
            select(func.count()).where(WebhookEventModel.event_id == "evt_dup_test_001")
        )
        assert event_count == 1


@pytest.mark.asyncio
async def test_unsupported_valid_event(client: AsyncClient, test_settings: Settings):
    """Verify unsupported valid event is stored as IGNORED and creates no case."""
    payload = {
        "event": "order.paid",
        "id": "evt_order_paid_001",
        "payload": {
            "order": {
                "entity": {"id": "order_001", "amount": 10000, "status": "paid"}
            }
        },
    }
    raw_body = json.dumps(payload).encode("utf-8")
    headers = make_signed_headers(raw_body, test_settings.razorpay_webhook_secret)

    response = await client.post("/webhooks/razorpay", content=raw_body, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "ignored" in data["message"].lower()

    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        event = await session.get(WebhookEventModel, "evt_order_paid_001")
        assert event is not None
        assert event.status == "IGNORED"

        # Ensure no recovery case was created
        case = await session.get(RecoveryCaseModel, "case_order_001")
        assert case is None
