"""Phase C3.5: Authoritative Recovery Verification & Attribution Audit Tests.

Audit and verifies:
1. captured payment verification
2. Payment Link association
3. amount match (420000 paise == ₹4,200.00)
4. currency match (INR)
5. merchant/account match
6. HMAC verification
7. authoritative gateway fetch
8. single attribution (never ₹8,400)
9. duplicate webhook suppression
10. invalid amount rejection
11. invalid currency rejection
12. already-attributed payment rejection
13. captured-only attribution
14. failed-only event cannot produce recovery credit
15. merchant recovery-status truthfulness (zero credit until RECOVERED).
"""

import hashlib
import hmac
import json
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from paymentflow.adapters.razorpay_adapter import RazorpayAdapter
from paymentflow.config import get_settings
from paymentflow.db.models import AuditEventModel, RecoveryCaseModel, utc_now
from paymentflow.db.session import get_sessionmaker
from paymentflow.domain.enums import CaseState
from paymentflow.main import app
from paymentflow.merchant.service import MerchantRegistry
from paymentflow.services.webhook_service import WebhookService


@pytest.fixture
def mock_razorpay_adapter():
    """Mock Razorpay adapter for authoritative gateway verification."""
    adapter = RazorpayAdapter(
        key_id="rzp_test_TWkctY0MsbW4Rd",
        key_secret="PWatfW99KA7gH4our6Sfvmoe",
    )
    adapter.get_payment = AsyncMock()
    return adapter


def compute_webhook_signature(body: bytes, secret: str) -> str:
    """Compute HMAC-SHA256 signature for test webhook payload."""
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


@pytest.mark.asyncio
async def test_c3_5_01_captured_payment_verification(mock_razorpay_adapter):
    """1. Authoritative verification of captured payment transitions case to RECOVERED."""
    sessionmaker = get_sessionmaker()
    case_id = "case_c35_cap_01"
    plink_id = "plink_c35_cap_01"
    payment_id = "pay_c35_cap_01"

    async with sessionmaker() as session:
        case = RecoveryCaseModel(
            case_id=case_id,
            failed_payment_id="pay_c35_fail_01",
            amount=420000,
            currency="INR",
            state=CaseState.ACTION_EXECUTED.value,
            payment_link_id=plink_id,
            case_source="MERCHANT_CHECKOUT",
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(case)
        await session.commit()

    mock_razorpay_adapter.get_payment.return_value = {
        "id": payment_id,
        "amount": 420000,
        "currency": "INR",
        "status": "captured",
        "captured": True,
    }

    payload = {
        "event": "payment.captured",
        "id": "evt_c35_cap_01",
        "payload": {
            "payment": {
                "entity": {
                    "id": payment_id,
                    "amount": 420000,
                    "currency": "INR",
                    "status": "captured",
                    "payment_link_id": plink_id,
                    "notes": {"case_id": case_id},
                }
            }
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

    # Verify DB persistence
    async with sessionmaker() as session:
        db_case = await session.get(RecoveryCaseModel, case_id)
        assert db_case.state == CaseState.RECOVERED.value
        assert db_case.recovered_payment_id == payment_id
        assert db_case.recovered_amount == 420000


@pytest.mark.asyncio
async def test_c3_5_02_payment_link_association(mock_razorpay_adapter):
    """2. Validates association between incoming payment and case via payment_link_id."""
    sessionmaker = get_sessionmaker()
    case_id = "case_c35_assoc_02"
    plink_id = "plink_c35_assoc_02"
    payment_id = "pay_c35_assoc_02"

    async with sessionmaker() as session:
        case = RecoveryCaseModel(
            case_id=case_id,
            failed_payment_id="pay_c35_fail_02",
            amount=420000,
            currency="INR",
            state=CaseState.ACTION_EXECUTED.value,
            payment_link_id=plink_id,
            case_source="MERCHANT_CHECKOUT",
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(case)
        await session.commit()

    mock_razorpay_adapter.get_payment.return_value = {
        "id": payment_id,
        "amount": 420000,
        "currency": "INR",
        "status": "captured",
    }

    # Payload with payment_link entity
    payload = {
        "event": "payment_link.paid",
        "id": "evt_c35_assoc_02",
        "payload": {
            "payment_link": {
                "entity": {
                    "id": plink_id,
                    "amount_paid": 420000,
                    "currency": "INR",
                    "status": "paid",
                }
            },
            "payment": {
                "entity": {
                    "id": payment_id,
                    "amount": 420000,
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

    assert res.case_id == case_id
    assert res.state == CaseState.RECOVERED.value


@pytest.mark.asyncio
async def test_c3_5_03_and_04_amount_and_currency_immutability(mock_razorpay_adapter):
    """3 & 4. Amount and currency match exactly: 420000 paise INR."""
    sessionmaker = get_sessionmaker()
    case_id = "case_c35_immut_03"
    plink_id = "plink_c35_immut_03"
    payment_id = "pay_c35_immut_03"

    async with sessionmaker() as session:
        case = RecoveryCaseModel(
            case_id=case_id,
            failed_payment_id="pay_c35_fail_03",
            amount=420000,
            currency="INR",
            state=CaseState.ACTION_EXECUTED.value,
            payment_link_id=plink_id,
            case_source="MERCHANT_CHECKOUT",
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(case)
        await session.commit()

    mock_razorpay_adapter.get_payment.return_value = {
        "id": payment_id,
        "amount": 420000,
        "currency": "INR",
        "status": "captured",
    }

    payload = {
        "event": "payment.captured",
        "id": "evt_c35_immut_03",
        "payload": {
            "payment": {
                "entity": {
                    "id": payment_id,
                    "amount": 420000,
                    "currency": "INR",
                    "status": "captured",
                    "payment_link_id": plink_id,
                }
            }
        },
    }

    async with sessionmaker() as session:
        service = WebhookService(session, razorpay_adapter=mock_razorpay_adapter)
        await service.process_webhook(
            raw_body=json.dumps(payload).encode("utf-8"),
            payload=payload,
            signature_verified=True,
        )

    async with sessionmaker() as session:
        db_case = await session.get(RecoveryCaseModel, case_id)
        assert db_case.amount == 420000
        assert db_case.recovered_amount == 420000
        assert db_case.currency == "INR"


@pytest.mark.asyncio
async def test_c3_5_05_merchant_account_match_isolation(mock_razorpay_adapter):
    """5. Mismatched case identifier or non-existent case is recorded as unmatched anomaly."""
    sessionmaker = get_sessionmaker()
    payload = {
        "event": "payment.captured",
        "id": "evt_c35_foreign_05",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_foreign_05",
                    "amount": 420000,
                    "currency": "INR",
                    "status": "captured",
                    "payment_link_id": "plink_foreign_non_existent",
                    "notes": {"case_id": "case_foreign_non_existent"},
                }
            }
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
    assert res.message == "Unmatched recovery payment."
    assert res.case_id is None

    # Verify UNMATCHED_RECOVERY_PAYMENT audit record
    async with sessionmaker() as session:
        audit_res = await session.execute(
            select(AuditEventModel).where(AuditEventModel.correlation_id == "evt_c35_foreign_05")
        )
        audit = audit_res.scalar_one_or_none()
        assert audit is not None
        assert audit.event_type == "UNMATCHED_RECOVERY_PAYMENT"


@pytest.mark.asyncio
async def test_c3_5_06_hmac_signature_verification_api():
    """6. Webhook endpoint verifies HMAC-SHA256: rejects bad signatures and accepts valid ones."""
    settings = get_settings()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {"event": "payment.captured", "id": "evt_sig_test"}
        raw_body = json.dumps(payload).encode("utf-8")

        # 6a. Rejects invalid HMAC signature with 400 Bad Request
        response_bad = await client.post(
            "/webhooks/razorpay",
            content=raw_body,
            headers={
                "Content-Type": "application/json",
                "X-Razorpay-Signature": "invalid_hmac_signature_12345",
            },
        )
        assert response_bad.status_code == 400
        assert "Invalid webhook signature" in response_bad.json()["detail"]

        # 6b. Accepts valid HMAC-SHA256 signature
        valid_sig = compute_webhook_signature(raw_body, settings.razorpay_webhook_secret)
        response_good = await client.post(
            "/webhooks/razorpay",
            content=raw_body,
            headers={
                "Content-Type": "application/json",
                "X-Razorpay-Signature": valid_sig,
            },
        )
        assert response_good.status_code == 200
        assert response_good.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_c3_5_07_authoritative_gateway_fetch_failure(mock_razorpay_adapter):
    """7. Gateway verification failure moves case to VERIFICATION without attributing recovery."""
    sessionmaker = get_sessionmaker()
    case_id = "case_c35_fetch_fail_07"
    plink_id = "plink_c35_fetch_fail_07"
    payment_id = "pay_c35_fetch_fail_07"

    async with sessionmaker() as session:
        case = RecoveryCaseModel(
            case_id=case_id,
            failed_payment_id="pay_c35_fail_07",
            amount=420000,
            currency="INR",
            state=CaseState.ACTION_EXECUTED.value,
            payment_link_id=plink_id,
            case_source="MERCHANT_CHECKOUT",
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(case)
        await session.commit()

    # Simulate gateway API error
    mock_razorpay_adapter.get_payment.side_effect = RuntimeError("Razorpay upstream 503")

    payload = {
        "event": "payment.captured",
        "id": "evt_c35_fetch_fail_07",
        "payload": {
            "payment": {
                "entity": {
                    "id": payment_id,
                    "amount": 420000,
                    "currency": "INR",
                    "status": "captured",
                    "payment_link_id": plink_id,
                }
            }
        },
    }

    async with sessionmaker() as session:
        service = WebhookService(session, razorpay_adapter=mock_razorpay_adapter)
        res = await service.process_webhook(
            raw_body=json.dumps(payload).encode("utf-8"),
            payload=payload,
            signature_verified=True,
        )

    assert res.state == CaseState.VERIFICATION.value

    # Verify no recovery credit was awarded
    async with sessionmaker() as session:
        db_case = await session.get(RecoveryCaseModel, case_id)
        assert db_case.state == CaseState.VERIFICATION.value
        assert db_case.recovered_amount is None
        assert db_case.recovered_payment_id is None


@pytest.mark.asyncio
async def test_c3_5_08_and_12_single_attribution_and_no_double_crediting(mock_razorpay_adapter):
    """8 & 12. Single attribution: Replaying capture or paid webhooks NEVER yields ₹8,400."""
    sessionmaker = get_sessionmaker()
    case_id = "case_c35_single_attr_08"
    plink_id = "plink_c35_single_attr_08"
    payment_id = "pay_c35_single_attr_08"

    async with sessionmaker() as session:
        case = RecoveryCaseModel(
            case_id=case_id,
            failed_payment_id="pay_c35_fail_08",
            amount=420000,
            currency="INR",
            state=CaseState.ACTION_EXECUTED.value,
            payment_link_id=plink_id,
            case_source="MERCHANT_CHECKOUT",
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(case)
        await session.commit()

    mock_razorpay_adapter.get_payment.return_value = {
        "id": payment_id,
        "amount": 420000,
        "currency": "INR",
        "status": "captured",
    }

    # First event: payment.captured
    payload1 = {
        "event": "payment.captured",
        "id": "evt_c35_attr_first",
        "payload": {
            "payment": {
                "entity": {
                    "id": payment_id,
                    "amount": 420000,
                    "currency": "INR",
                    "status": "captured",
                    "payment_link_id": plink_id,
                }
            }
        },
    }

    async with sessionmaker() as session:
        service = WebhookService(session, razorpay_adapter=mock_razorpay_adapter)
        res1 = await service.process_webhook(
            raw_body=json.dumps(payload1).encode("utf-8"),
            payload=payload1,
            signature_verified=True,
        )
    assert res1.state == CaseState.RECOVERED.value
    assert res1.is_duplicate is False

    # Second event: payment_link.paid for same payment and case
    payload2 = {
        "event": "payment_link.paid",
        "id": "evt_c35_attr_second",
        "payload": {
            "payment_link": {"entity": {"id": plink_id}},
            "payment": {
                "entity": {
                    "id": payment_id,
                    "amount": 420000,
                    "currency": "INR",
                    "status": "captured",
                    "payment_link_id": plink_id,
                }
            },
        },
    }

    async with sessionmaker() as session:
        service = WebhookService(session, razorpay_adapter=mock_razorpay_adapter)
        res2 = await service.process_webhook(
            raw_body=json.dumps(payload2).encode("utf-8"),
            payload=payload2,
            signature_verified=True,
        )
    assert res2.is_duplicate is True
    assert res2.message == "Recovery case already attributed."

    # Verify amount is strictly 420000, NOT 840000
    async with sessionmaker() as session:
        db_case = await session.get(RecoveryCaseModel, case_id)
        assert db_case.recovered_amount == 420000
        assert db_case.recovered_payment_id == payment_id

        # Verify audit logs record duplicate suppression
        audit_res = await session.execute(
            select(AuditEventModel).where(
                AuditEventModel.case_id == case_id,
                AuditEventModel.event_type == "PAYMENT_LINK_WEBHOOK_DUPLICATE",
            )
        )
        assert audit_res.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_c3_5_09_duplicate_webhook_event_id_suppression(mock_razorpay_adapter):
    """9. Exact duplicate webhook event_id is rejected idempotently at ingress."""
    sessionmaker = get_sessionmaker()
    payload = {
        "event": "payment.captured",
        "id": "evt_c35_exact_dup_09",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_c35_exact_09",
                    "amount": 420000,
                    "currency": "INR",
                    "status": "captured",
                    "payment_link_id": "plink_non_existent",
                }
            }
        },
    }

    # First attempt
    async with sessionmaker() as session:
        service = WebhookService(session, razorpay_adapter=mock_razorpay_adapter)
        res1 = await service.process_webhook(
            raw_body=json.dumps(payload).encode("utf-8"),
            payload=payload,
            signature_verified=True,
        )
    assert res1.is_duplicate is False

    # Second attempt with exact same event_id
    async with sessionmaker() as session:
        service = WebhookService(session, razorpay_adapter=mock_razorpay_adapter)
        res2 = await service.process_webhook(
            raw_body=json.dumps(payload).encode("utf-8"),
            payload=payload,
            signature_verified=True,
        )
    assert res2.is_duplicate is True
    assert res2.message == "Duplicate event ignored."


@pytest.mark.asyncio
async def test_c3_5_10_invalid_amount_rejection(mock_razorpay_adapter):
    """10. Amount mismatch (e.g. 300000 vs 420000) rejects attribution and escalates."""
    sessionmaker = get_sessionmaker()
    case_id = "case_c35_amt_mismatch_10"
    plink_id = "plink_c35_amt_mismatch_10"
    payment_id = "pay_c35_amt_mismatch_10"

    async with sessionmaker() as session:
        case = RecoveryCaseModel(
            case_id=case_id,
            failed_payment_id="pay_c35_fail_10",
            amount=420000,
            currency="INR",
            state=CaseState.ACTION_EXECUTED.value,
            payment_link_id=plink_id,
            case_source="MERCHANT_CHECKOUT",
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(case)
        await session.commit()

    # Gateway returns mismatched amount
    mock_razorpay_adapter.get_payment.return_value = {
        "id": payment_id,
        "amount": 300000,
        "currency": "INR",
        "status": "captured",
    }

    payload = {
        "event": "payment.captured",
        "id": "evt_c35_amt_mismatch_10",
        "payload": {
            "payment": {
                "entity": {
                    "id": payment_id,
                    "amount": 300000,
                    "currency": "INR",
                    "status": "captured",
                    "payment_link_id": plink_id,
                }
            }
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
    assert "Amount/currency mismatch" in res.message

    async with sessionmaker() as session:
        db_case = await session.get(RecoveryCaseModel, case_id)
        assert db_case.state == CaseState.ESCALATED.value
        assert db_case.recovered_amount is None


@pytest.mark.asyncio
async def test_c3_5_11_invalid_currency_rejection(mock_razorpay_adapter):
    """11. Currency mismatch (e.g. USD vs INR) rejects attribution and escalates."""
    sessionmaker = get_sessionmaker()
    case_id = "case_c35_curr_mismatch_11"
    plink_id = "plink_c35_curr_mismatch_11"
    payment_id = "pay_c35_curr_mismatch_11"

    async with sessionmaker() as session:
        case = RecoveryCaseModel(
            case_id=case_id,
            failed_payment_id="pay_c35_fail_11",
            amount=420000,
            currency="INR",
            state=CaseState.ACTION_EXECUTED.value,
            payment_link_id=plink_id,
            case_source="MERCHANT_CHECKOUT",
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(case)
        await session.commit()

    mock_razorpay_adapter.get_payment.return_value = {
        "id": payment_id,
        "amount": 420000,
        "currency": "USD",  # Mismatch!
        "status": "captured",
    }

    payload = {
        "event": "payment.captured",
        "id": "evt_c35_curr_mismatch_11",
        "payload": {
            "payment": {
                "entity": {
                    "id": payment_id,
                    "amount": 420000,
                    "currency": "USD",
                    "status": "captured",
                    "payment_link_id": plink_id,
                }
            }
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

    async with sessionmaker() as session:
        db_case = await session.get(RecoveryCaseModel, case_id)
        assert db_case.state == CaseState.ESCALATED.value
        assert db_case.recovered_amount is None


@pytest.mark.asyncio
async def test_c3_5_13_captured_only_attribution_rule(mock_razorpay_adapter):
    """13. Payments in non-captured status (e.g. authorized) are strictly rejected."""
    sessionmaker = get_sessionmaker()
    case_id = "case_c35_auth_only_13"
    plink_id = "plink_c35_auth_only_13"
    payment_id = "pay_c35_auth_only_13"

    async with sessionmaker() as session:
        case = RecoveryCaseModel(
            case_id=case_id,
            failed_payment_id="pay_c35_fail_13",
            amount=420000,
            currency="INR",
            state=CaseState.ACTION_EXECUTED.value,
            payment_link_id=plink_id,
            case_source="MERCHANT_CHECKOUT",
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(case)
        await session.commit()

    mock_razorpay_adapter.get_payment.return_value = {
        "id": payment_id,
        "amount": 420000,
        "currency": "INR",
        "status": "authorized",  # NOT captured
    }

    payload = {
        "event": "payment.captured",
        "id": "evt_c35_auth_only_13",
        "payload": {
            "payment": {
                "entity": {
                    "id": payment_id,
                    "amount": 420000,
                    "currency": "INR",
                    "status": "authorized",
                    "payment_link_id": plink_id,
                }
            }
        },
    }

    async with sessionmaker() as session:
        service = WebhookService(session, razorpay_adapter=mock_razorpay_adapter)
        res = await service.process_webhook(
            raw_body=json.dumps(payload).encode("utf-8"),
            payload=payload,
            signature_verified=True,
        )

    assert "is not captured" in res.message

    async with sessionmaker() as session:
        db_case = await session.get(RecoveryCaseModel, case_id)
        assert db_case.state == CaseState.ACTION_EXECUTED.value
        assert db_case.recovered_amount is None


@pytest.mark.asyncio
async def test_c3_5_14_failed_only_event_cannot_produce_recovery_credit():
    """14. A payment.failed event creates a case in FAILED_INGESTED, zero recovery credit."""
    sessionmaker = get_sessionmaker()
    failed_pay_id = "pay_c35_fail_event_14"

    payload = {
        "event": "payment.failed",
        "id": "evt_c35_fail_event_14",
        "payload": {
            "payment": {
                "entity": {
                    "id": failed_pay_id,
                    "amount": 420000,
                    "currency": "INR",
                    "status": "failed",
                    "method": "upi",
                    "error_code": "BAD_REQUEST_ERROR",
                    "error_description": "Bank decline",
                }
            }
        },
    }

    async with sessionmaker() as session:
        service = WebhookService(session)
        res = await service.process_webhook(
            raw_body=json.dumps(payload).encode("utf-8"),
            payload=payload,
            signature_verified=True,
        )

    assert res.state == CaseState.FAILED_INGESTED.value

    async with sessionmaker() as session:
        db_case = await session.get(RecoveryCaseModel, res.case_id)
        assert db_case.state == CaseState.FAILED_INGESTED.value
        assert db_case.recovered_amount is None
        assert db_case.recovered_payment_id is None


@pytest.mark.asyncio
async def test_c3_5_15_merchant_recovery_status_truthfulness():
    """15. Merchant recovery status truthful progression: zero money until state=RECOVERED."""
    MerchantRegistry.reset_to_default()
    sessionmaker = get_sessionmaker()
    order_id = "ORD-C35-TEST-4200"
    case_id = f"case_{order_id}"

    # Step 1: Case in ACTION_EXECUTED (link sent, awaiting payment)
    async with sessionmaker() as session:
        case = RecoveryCaseModel(
            case_id=case_id,
            failed_payment_id="pay_c35_order_orig",
            order_id=order_id,
            amount=420000,
            currency="INR",
            state=CaseState.ACTION_EXECUTED.value,
            payment_link_id="plink_c35_order_01",
            case_source="MERCHANT_CHECKOUT",
            failure_context={
                "external_order_id": order_id,
                "notification_status": "SENT",
                "notification_medium": "sms",
                "masked_contact": "+91******1160",
                "delivery_verified": False,
            },
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(case)
        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Query before payment: Must show zero recovered amount
        r_pre = await client.get(
            f"/merchant/v1/orders/{order_id}/recovery-status",
            headers={"Authorization": "Bearer pf_live_test_merchant_key_2026"},
        )
        assert r_pre.status_code == 200
        d_pre = r_pre.json()
        assert d_pre["state"] == "ACTION_EXECUTED"
        assert d_pre["recovered_amount"] is None
        assert "Payment could not be completed" in d_pre["message"]

        # Step 2: Simulate authoritative recovery payment
        async with sessionmaker() as session:
            db_case = await session.get(RecoveryCaseModel, case_id)
            db_case.state = CaseState.RECOVERED.value
            db_case.recovered_amount = 420000
            db_case.recovered_payment_id = "pay_c35_order_rec"
            await session.commit()

        # Query after payment: Must show INR 4200.00 recovered
        r_post = await client.get(
            f"/merchant/v1/orders/{order_id}/recovery-status",
            headers={"Authorization": "Bearer pf_live_test_merchant_key_2026"},
        )
        assert r_post.status_code == 200
        d_post = r_post.json()
        assert d_post["state"] == "RECOVERED"
        assert d_post["recovered_amount"] == 420000
        assert d_post["recovered_payment_id"] == "pay_c35_order_rec"
        assert "Payment recovered successfully! Recovered amount: INR 4200.00." in d_post["message"]
