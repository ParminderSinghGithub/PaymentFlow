"""Comprehensive tests for Layer 4B: Payment Link outcome verification and revenue attribution."""

import json
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from paymentflow.adapters.razorpay_adapter import RazorpayAdapter
from paymentflow.db.models import AuditEventModel, RecoveryCaseModel, utc_now
from paymentflow.db.session import get_sessionmaker
from paymentflow.domain.enums import CaseState, FailureCategory, RecoveryPolicy
from paymentflow.services.webhook_service import WebhookService


@pytest.fixture
def mock_razorpay_adapter():
    """Mock Razorpay adapter for payment verification."""
    adapter = RazorpayAdapter()
    adapter.get_payment = AsyncMock()
    return adapter


@pytest.mark.asyncio
async def test_layer4b_payment_link_paid_happy_path(mock_razorpay_adapter):
    """Test valid payment_link.paid webhook attributes exact recovered revenue."""
    sessionmaker = get_sessionmaker()
    case_id = "case_l4b_happy_01"
    plink_id = "plink_l4b_happy_01"
    payment_id = "pay_l4b_recovered_01"

    async with sessionmaker() as session:
        case = RecoveryCaseModel(
            case_id=case_id,
            failed_payment_id="pay_l4b_orig_01",
            amount=349900,
            currency="INR",
            state=CaseState.ACTION_EXECUTED.value,
            failure_category=FailureCategory.C1.value,
            validated_policy_id=RecoveryPolicy.P_CREATE_LINK_IMMEDIATE.value,
            payment_link_id=plink_id,
            payment_link_short_url=f"https://rzp.io/i/{plink_id}",
            payment_link_status="created",
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(case)
        await session.commit()

    mock_razorpay_adapter.get_payment.return_value = {
        "id": payment_id,
        "amount": 349900,
        "currency": "INR",
        "status": "captured",
    }

    payload = {
        "event": "payment_link.paid",
        "id": "evt_l4b_happy_01",
        "payload": {
            "payment_link": {
                "entity": {
                    "id": plink_id,
                    "amount_paid": 349900,
                    "currency": "INR",
                    "status": "paid",
                    "notes": {"case_id": case_id, "failed_payment_id": "pay_l4b_orig_01"},
                }
            },
            "payment": {
                "entity": {
                    "id": payment_id,
                    "amount": 349900,
                    "currency": "INR",
                    "status": "captured",
                    "payment_link_id": plink_id,
                }
            },
        },
    }

    async with sessionmaker() as session:
        service = WebhookService(session, razorpay_adapter=mock_razorpay_adapter)
        res = await service.process_webhook(
            raw_body=json.dumps(payload).encode("utf-8"),
            payload=payload,
            signature_verified=True,
        )

    assert res.status == "ok"
    assert res.case_id == case_id
    assert res.state == CaseState.RECOVERED.value
    assert res.is_duplicate is False

    # Verify database persistence of recovered revenue
    async with sessionmaker() as session:
        db_case = await session.get(RecoveryCaseModel, case_id)
        assert db_case.state == CaseState.RECOVERED.value
        assert db_case.recovered_payment_id == payment_id
        assert db_case.recovered_amount == 349900
        assert db_case.payment_link_status == "paid"

        # Verify audit records
        audit_res = await session.execute(
            select(AuditEventModel).where(AuditEventModel.case_id == case_id)
        )
        audits = audit_res.scalars().all()
        event_types = [a.event_type for a in audits]
        assert "PAYMENT_VERIFICATION_REQUESTED" in event_types
        assert "PAYMENT_VERIFIED" in event_types
        assert "RECOVERY_ATTRIBUTED" in event_types

        attr_event = next(a for a in audits if a.event_type == "RECOVERY_ATTRIBUTED")
        assert attr_event.decision == "ATTRIBUTED"
        assert attr_event.details["recovered_amount_paise"] == 349900


@pytest.mark.asyncio
async def test_layer4b_webhook_replay_single_attribution(mock_razorpay_adapter):
    """Test webhook replay causes zero incremental revenue attribution."""
    sessionmaker = get_sessionmaker()
    case_id = "case_l4b_replay_01"
    plink_id = "plink_l4b_replay_01"
    payment_id = "pay_l4b_replay_01"
    event_id = "evt_l4b_replay_unique_01"

    async with sessionmaker() as session:
        case = RecoveryCaseModel(
            case_id=case_id,
            failed_payment_id="pay_l4b_replay_orig_01",
            amount=199900,
            currency="INR",
            state=CaseState.ACTION_EXECUTED.value,
            payment_link_id=plink_id,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(case)
        await session.commit()

    mock_razorpay_adapter.get_payment.return_value = {
        "id": payment_id,
        "amount": 199900,
        "currency": "INR",
        "status": "captured",
    }

    payload = {
        "event": "payment_link.paid",
        "id": event_id,
        "payload": {
            "payment_link": {"entity": {"id": plink_id}},
            "payment": {
                "entity": {
                    "id": payment_id,
                    "amount": 199900,
                    "currency": "INR",
                    "status": "captured",
                }
            },
        },
    }
    raw_body = json.dumps(payload).encode("utf-8")

    # First delivery
    async with sessionmaker() as session:
        service = WebhookService(session, razorpay_adapter=mock_razorpay_adapter)
        res1 = await service.process_webhook(
            raw_body=raw_body, payload=payload, signature_verified=True
        )
        assert res1.is_duplicate is False
        assert res1.state == CaseState.RECOVERED.value

    # Replayed delivery (same event ID)
    async with sessionmaker() as session:
        service = WebhookService(session, razorpay_adapter=mock_razorpay_adapter)
        res2 = await service.process_webhook(
            raw_body=raw_body, payload=payload, signature_verified=True
        )
        assert res2.is_duplicate is True
        assert res2.status == "ok"

    # Verify single attribution in DB
    async with sessionmaker() as session:
        db_case = await session.get(RecoveryCaseModel, case_id)
        assert db_case.recovered_amount == 199900


@pytest.mark.asyncio
async def test_layer4b_second_payment_on_recovered_case_suppressed(mock_razorpay_adapter):
    """Test that a second distinct payment on an already recovered case does not double-count."""
    sessionmaker = get_sessionmaker()
    case_id = "case_l4b_double_pay_01"
    plink_id = "plink_l4b_double_01"

    async with sessionmaker() as session:
        case = RecoveryCaseModel(
            case_id=case_id,
            failed_payment_id="pay_l4b_double_orig_01",
            amount=500000,
            currency="INR",
            state=CaseState.RECOVERED.value,
            recovered_payment_id="pay_l4b_first_01",
            recovered_amount=500000,
            payment_link_id=plink_id,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(case)
        await session.commit()

    payload = {
        "event": "payment_link.paid",
        "id": "evt_l4b_second_pay_01",
        "payload": {
            "payment_link": {"entity": {"id": plink_id}},
            "payment": {
                "entity": {
                    "id": "pay_l4b_second_02",
                    "amount": 500000,
                    "currency": "INR",
                    "status": "captured",
                }
            },
        },
    }

    async with sessionmaker() as session:
        service = WebhookService(session, razorpay_adapter=mock_razorpay_adapter)
        res = await service.process_webhook(
            raw_body=json.dumps(payload).encode("utf-8"),
            payload=payload,
            signature_verified=True,
        )

    assert res.is_duplicate is True
    assert res.case_id == case_id

    # Verify amount remained unchanged (500000 paise, not 1000000 paise)
    async with sessionmaker() as session:
        db_case = await session.get(RecoveryCaseModel, case_id)
        assert db_case.recovered_amount == 500000
        assert db_case.recovered_payment_id == "pay_l4b_first_01"


@pytest.mark.asyncio
async def test_layer4b_amount_mismatch_rejected(mock_razorpay_adapter):
    """Test amount mismatch between recovered payment and case is rejected and escalated."""
    sessionmaker = get_sessionmaker()
    case_id = "case_l4b_mismatch_01"
    plink_id = "plink_l4b_mismatch_01"
    payment_id = "pay_l4b_mismatch_01"

    async with sessionmaker() as session:
        case = RecoveryCaseModel(
            case_id=case_id,
            failed_payment_id="pay_l4b_mismatch_orig_01",
            amount=499900,  # Original expected: ₹4999.00
            currency="INR",
            state=CaseState.ACTION_EXECUTED.value,
            payment_link_id=plink_id,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(case)
        await session.commit()

    mock_razorpay_adapter.get_payment.return_value = {
        "id": payment_id,
        "amount": 100000,  # Mismatched paid: ₹1000.00
        "currency": "INR",
        "status": "captured",
    }

    payload = {
        "event": "payment_link.paid",
        "id": "evt_l4b_mismatch_01",
        "payload": {
            "payment_link": {"entity": {"id": plink_id}},
            "payment": {
                "entity": {
                    "id": payment_id,
                    "amount": 100000,
                    "currency": "INR",
                    "status": "captured",
                }
            },
        },
    }

    async with sessionmaker() as session:
        service = WebhookService(session, razorpay_adapter=mock_razorpay_adapter)
        res = await service.process_webhook(
            raw_body=json.dumps(payload).encode("utf-8"),
            payload=payload,
            signature_verified=True,
        )

    assert res.state == CaseState.ESCALATED.value

    # Verify no revenue attributed and case moved to ESCALATED
    async with sessionmaker() as session:
        db_case = await session.get(RecoveryCaseModel, case_id)
        assert db_case.recovered_amount is None
        assert db_case.recovered_payment_id is None
        assert db_case.state == CaseState.ESCALATED.value

        audit_res = await session.execute(
            select(AuditEventModel).where(AuditEventModel.case_id == case_id)
        )
        audits = audit_res.scalars().all()
        event_types = [a.event_type for a in audits]
        assert "RECOVERY_AMOUNT_MISMATCH" in event_types
        assert "RECOVERY_ATTRIBUTION_REJECTED" in event_types


@pytest.mark.asyncio
async def test_layer4b_unmatched_payment_link(mock_razorpay_adapter):
    """Test webhook with unknown Payment Link records anomaly and performs zero attribution."""
    sessionmaker = get_sessionmaker()

    payload = {
        "event": "payment_link.paid",
        "id": "evt_l4b_unknown_link_01",
        "payload": {
            "payment_link": {"entity": {"id": "plink_unknown_9999"}},
            "payment": {
                "entity": {
                    "id": "pay_unknown_9999",
                    "amount": 100000,
                    "currency": "INR",
                    "status": "captured",
                }
            },
        },
    }

    async with sessionmaker() as session:
        service = WebhookService(session, razorpay_adapter=mock_razorpay_adapter)
        res = await service.process_webhook(
            raw_body=json.dumps(payload).encode("utf-8"),
            payload=payload,
            signature_verified=True,
        )

    assert res.status == "ok"
    assert res.case_id is None

    # Verify anomaly audit record
    async with sessionmaker() as session:
        audit_res = await session.execute(
            select(AuditEventModel).where(
                AuditEventModel.event_type == "UNMATCHED_RECOVERY_PAYMENT"
            )
        )
        audits = audit_res.scalars().all()
        assert len(audits) >= 1
        assert any(a.details.get("payment_link_id") == "plink_unknown_9999" for a in audits)


@pytest.mark.asyncio
async def test_layer4b_payment_not_captured_rejected(mock_razorpay_adapter):
    """Test payment in 'failed' status is rejected for attribution."""
    sessionmaker = get_sessionmaker()
    case_id = "case_l4b_not_cap_01"
    plink_id = "plink_l4b_not_cap_01"

    async with sessionmaker() as session:
        case = RecoveryCaseModel(
            case_id=case_id,
            failed_payment_id="pay_l4b_not_cap_orig_01",
            amount=200000,
            currency="INR",
            state=CaseState.ACTION_EXECUTED.value,
            payment_link_id=plink_id,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(case)
        await session.commit()

    mock_razorpay_adapter.get_payment.return_value = {
        "id": "pay_failed_attempt_01",
        "amount": 200000,
        "currency": "INR",
        "status": "failed",
    }

    payload = {
        "event": "payment_link.paid",
        "id": "evt_l4b_not_cap_01",
        "payload": {
            "payment_link": {"entity": {"id": plink_id}},
            "payment": {
                "entity": {
                    "id": "pay_failed_attempt_01",
                    "amount": 200000,
                    "currency": "INR",
                    "status": "failed",
                }
            },
        },
    }

    async with sessionmaker() as session:
        service = WebhookService(session, razorpay_adapter=mock_razorpay_adapter)
        res = await service.process_webhook(
            raw_body=json.dumps(payload).encode("utf-8"),
            payload=payload,
            signature_verified=True,
        )

    assert res.status == "ok"
    assert res.state == CaseState.ACTION_EXECUTED.value

    # Verify no revenue attributed
    async with sessionmaker() as session:
        db_case = await session.get(RecoveryCaseModel, case_id)
        assert db_case.recovered_amount is None
        assert db_case.state == CaseState.ACTION_EXECUTED.value
