"""Unit tests for WebhookService business logic, branch coverage, and error handling."""

import pytest

from paymentflow.db.session import get_sessionmaker
from paymentflow.domain.exceptions import WebhookPayloadError
from paymentflow.services.webhook_service import WebhookService


@pytest.mark.asyncio
async def test_webhook_service_payload_validations():
    """Verify WebhookService rejects non-dict or invalid payloads."""
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        service = WebhookService(session)

        # Non-dict payload
        with pytest.raises(WebhookPayloadError):
            await service.process_webhook(b"[]", [], signature_verified=True)

        # Missing event field
        with pytest.raises(WebhookPayloadError):
            await service.process_webhook(b"{}", {"id": "evt_1"}, signature_verified=True)


@pytest.mark.asyncio
async def test_webhook_service_payment_failed_validation_branches():
    """Verify _handle_payment_failed validates payment entity fields."""
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        service = WebhookService(session)

        # Missing payment entity
        with pytest.raises(WebhookPayloadError):
            await service.process_webhook(
                b"{}",
                {"event": "payment.failed", "id": "evt_e1", "payload": {}},
                signature_verified=True,
            )

        # Missing payment id
        with pytest.raises(WebhookPayloadError):
            await service.process_webhook(
                b"{}",
                {
                    "event": "payment.failed",
                    "id": "evt_e2",
                    "payload": {"payment": {"entity": {"amount": 500}}},
                },
                signature_verified=True,
            )

        # Missing payment amount
        with pytest.raises(WebhookPayloadError):
            await service.process_webhook(
                b"{}",
                {
                    "event": "payment.failed",
                    "id": "evt_e3",
                    "payload": {"payment": {"entity": {"id": "pay_e3"}}},
                },
                signature_verified=True,
            )


@pytest.mark.asyncio
async def test_webhook_service_extract_event_id_fallbacks():
    """Verify event ID extraction fallbacks."""
    # 1. From event_id field
    assert (
        WebhookService.extract_event_id({"event_id": "evt_custom_1"}, b"")
        == "evt_custom_1"
    )

    # 2. From payment id and created_at
    payload = {
        "event": "payment.failed",
        "created_at": 170000,
        "payload": {"payment": {"entity": {"id": "pay_abc"}}},
    }
    extracted = WebhookService.extract_event_id(payload, b"")
    assert extracted == "evt_pay_abc_payment.failed_170000"

    # 3. From raw body hash
    extracted_hash = WebhookService.extract_event_id({"event": "other"}, b"some_raw_bytes")
    assert extracted_hash.startswith("evt_hash_")


@pytest.mark.asyncio
async def test_webhook_service_existing_case_for_payment():
    """Verify that when a case already exists for a payment, subsequent event links it."""
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        service = WebhookService(session)

        payload1 = {
            "event": "payment.failed",
            "id": "evt_case_test_01",
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_case_repeat_01",
                        "amount": 10000,
                        "currency": "INR",
                    }
                }
            },
        }
        res1 = await service.process_webhook(b"", payload1, signature_verified=True)
        assert res1.case_id == "case_pay_case_repeat_01"

        # Another webhook with different event_id for the same payment
        payload2 = {
            "event": "payment.failed",
            "id": "evt_case_test_02",
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_case_repeat_01",
                        "amount": 10000,
                        "currency": "INR",
                    }
                }
            },
        }
        res2 = await service.process_webhook(b"", payload2, signature_verified=True)
        assert res2.case_id == "case_pay_case_repeat_01"
        assert "already exists" in res2.message
