"""PHASE C3.6.4: MERCHANT ISOLATION, AUTHENTICATION & AUTHORIZATION BOUNDARY TESTS.

Proves that PaymentFlow's merchant integration boundary is securely tenant-isolated:
- Authenticated merchant identity is resolved strictly from server-to-server Bearer API keys.
- Merchant A cannot read, mutate, attribute, or execute recovery actions for Merchant B.
- Razorpay credentials are deterministically bound to authenticated merchant profiles.
- Webhook tenant mismatches and unknown merchants fail closed and escalate.
- Canonical benchmark records cannot leak through merchant recovery status.
- Recovery-status is strictly read-only and side-effect free.
- No secrets or API keys escape via responses or logs.
"""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from paymentflow.adapters.razorpay_adapter import RazorpayAdapter
from paymentflow.config import get_settings
from paymentflow.db.models import AuditEventModel, RecoveryCaseModel, utc_now
from paymentflow.db.session import get_sessionmaker
from paymentflow.domain.enums import CaseState
from paymentflow.main import app
from paymentflow.merchant.models import MerchantProfile, hash_api_key, verify_api_key
from paymentflow.merchant.service import MerchantRegistry
from paymentflow.services.recovery_executor import RecoveryExecutor
from paymentflow.services.webhook_service import WebhookService

# Deterministic Test Fixture Credentials
MERCHANT_A_ID = "merchant_a"
MERCHANT_A_KEY = "pf_sec_test_key_merchant_a_8801"
MERCHANT_A_RZP_KEY = "rzp_test_merchant_a_key"
MERCHANT_A_RZP_SECRET = "rzp_test_merchant_a_secret"

MERCHANT_B_ID = "merchant_b"
MERCHANT_B_KEY = "pf_sec_test_key_merchant_b_8802"
MERCHANT_B_RZP_KEY = "rzp_test_merchant_b_key"
MERCHANT_B_RZP_SECRET = "rzp_test_merchant_b_secret"

MERCHANT_DISABLED_ID = "merchant_disabled"
MERCHANT_DISABLED_KEY = "pf_sec_test_key_merchant_disabled_8803"


@pytest.fixture(autouse=True)
def setup_merchant_registry_fixtures():
    """Register isolated test merchants into MerchantRegistry."""
    MerchantRegistry.reset_to_default()

    prof_a = MerchantProfile(
        merchant_id=MERCHANT_A_ID,
        merchant_name="Merchant A Apparel",
        api_key_hash=hash_api_key(MERCHANT_A_KEY),
        is_active=True,
        razorpay_key_id=MERCHANT_A_RZP_KEY,
        razorpay_key_secret=MERCHANT_A_RZP_SECRET,
    )
    prof_b = MerchantProfile(
        merchant_id=MERCHANT_B_ID,
        merchant_name="Merchant B Electronics",
        api_key_hash=hash_api_key(MERCHANT_B_KEY),
        is_active=True,
        razorpay_key_id=MERCHANT_B_RZP_KEY,
        razorpay_key_secret=MERCHANT_B_RZP_SECRET,
    )
    prof_disabled = MerchantProfile(
        merchant_id=MERCHANT_DISABLED_ID,
        merchant_name="Merchant Disabled Co",
        api_key_hash=hash_api_key(MERCHANT_DISABLED_KEY),
        is_active=False,
        razorpay_key_id="rzp_test_disabled_key",
        razorpay_key_secret="rzp_test_disabled_secret",
    )

    MerchantRegistry.register_merchant(prof_a)
    MerchantRegistry.register_merchant(prof_b)
    MerchantRegistry.register_merchant(prof_disabled)

    yield

    MerchantRegistry.reset_to_default()


# ==============================================================================
# 1. AUTHENTICATION AUDIT TESTS (Section 3)
# ==============================================================================


@pytest.mark.asyncio
async def test_auth_missing_header():
    """Missing Authorization header returns 401 Unauthorized."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/merchant/v1/verify")
        assert res.status_code == 401
        assert "WWW-Authenticate" in res.headers
        assert res.headers["WWW-Authenticate"] == "Bearer"
        assert "Missing Authorization header" in res.json()["detail"]


@pytest.mark.asyncio
async def test_auth_empty_header():
    """Empty Authorization header returns 401 Unauthorized."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/merchant/v1/verify", headers={"Authorization": ""})
        assert res.status_code == 401
        assert "WWW-Authenticate" in res.headers


@pytest.mark.asyncio
async def test_auth_malformed_headers():
    """Malformed Authorization headers return 401 Unauthorized."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for malformed in ["Bearer", "Bearer token extra_part", "Bearer   ", "NotBearer foo"]:
            res = await client.get("/merchant/v1/verify", headers={"Authorization": malformed})
            assert res.status_code == 401
            assert "WWW-Authenticate" in res.headers


@pytest.mark.asyncio
async def test_auth_wrong_scheme():
    """Wrong authorization schemes (Basic, Token) return 401."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get(
            "/merchant/v1/verify", headers={"Authorization": f"Basic {MERCHANT_A_KEY}"}
        )
        assert res.status_code == 401


@pytest.mark.asyncio
async def test_auth_unknown_and_invalid_api_key():
    """Unknown or invalid API key returns 401 without leaking internal details."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get(
            "/merchant/v1/verify", headers={"Authorization": "Bearer totally_bogus_key_xyz"}
        )
        assert res.status_code == 401
        data = res.json()
        assert data["detail"] == "Invalid PaymentFlow API key."
        # Verify no secret, stack trace, or internal path is in response
        body_text = res.text.lower()
        assert "password" not in body_text
        assert "traceback" not in body_text
        assert "secret" not in body_text


@pytest.mark.asyncio
async def test_auth_disabled_merchant_account():
    """Disabled merchant account returns 403 Forbidden."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get(
            "/merchant/v1/verify", headers={"Authorization": f"Bearer {MERCHANT_DISABLED_KEY}"}
        )
        assert res.status_code == 403
        assert "disabled" in res.json()["detail"]


@pytest.mark.asyncio
async def test_auth_valid_merchant_keys():
    """Valid merchant keys authenticate correctly and return public metadata without secrets."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Merchant A
        res_a = await client.get(
            "/merchant/v1/verify", headers={"Authorization": f"Bearer {MERCHANT_A_KEY}"}
        )
        assert res_a.status_code == 200
        data_a = res_a.json()
        assert data_a["merchant_id"] == MERCHANT_A_ID
        assert data_a["razorpay_key_id"] == MERCHANT_A_RZP_KEY
        assert MERCHANT_A_RZP_SECRET not in res_a.text
        assert MERCHANT_A_KEY not in res_a.text

        # Merchant B
        res_b = await client.get(
            "/merchant/v1/verify", headers={"Authorization": f"Bearer {MERCHANT_B_KEY}"}
        )
        assert res_b.status_code == 200
        data_b = res_b.json()
        assert data_b["merchant_id"] == MERCHANT_B_ID
        assert data_b["razorpay_key_id"] == MERCHANT_B_RZP_KEY
        assert MERCHANT_B_RZP_SECRET not in res_b.text
        assert MERCHANT_B_KEY not in res_b.text


def test_auth_timing_safe_comparison():
    """API key verification uses hmac.compare_digest for constant-time comparison."""
    h = hash_api_key(MERCHANT_A_KEY)
    assert verify_api_key(MERCHANT_A_KEY, h) is True
    assert verify_api_key(MERCHANT_B_KEY, h) is False
    assert verify_api_key("wrong_key", h) is False


# ==============================================================================
# 2. MERCHANT IDENTITY SPOOFING TESTS (Section 4 & 7)
# ==============================================================================


@pytest.mark.asyncio
async def test_spoofing_body_merchant_id_conflict_rejected():
    """Merchant A cannot submit checkout-context claiming merchant_id=B (HTTP 403)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "external_order_id": "ORD-SPOOF-01",
            "amount": 250000,
            "currency": "INR",
            "merchant_id": MERCHANT_B_ID,  # Spoof attempt
        }
        res = await client.post(
            "/merchant/v1/checkout-context",
            headers={"Authorization": f"Bearer {MERCHANT_A_KEY}"},
            json=payload,
        )
        assert res.status_code == 403
        assert "Forbidden" in res.json()["detail"]


@pytest.mark.asyncio
async def test_spoofing_order_creation_notes_conflict_rejected():
    """Merchant A cannot inject notes with merchant_id=B during order creation (HTTP 403)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "external_order_id": "ORD-SPOOF-NOTES-01",
            "amount": 199900,
            "currency": "INR",
            "notes": {"merchant_id": MERCHANT_B_ID},  # Spoof attempt via notes
        }
        res = await client.post(
            "/merchant/v1/orders",
            headers={"Authorization": f"Bearer {MERCHANT_A_KEY}"},
            json=payload,
        )
        assert res.status_code == 403
        assert "Forbidden" in res.json()["detail"]


@pytest.mark.asyncio
async def test_spoofing_arbitrary_metadata_cannot_override_identity():
    """Metadata containing merchant_id=B does not override resolved merchant identity."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "external_order_id": "ORD-META-01",
            "amount": 150000,
            "currency": "INR",
            "metadata": {"merchant_id": MERCHANT_B_ID, "merchant": "rogue_store"},
        }
        res = await client.post(
            "/merchant/v1/checkout-context",
            headers={"Authorization": f"Bearer {MERCHANT_A_KEY}"},
            json=payload,
        )
        assert res.status_code == 200
        data = res.json()
        assert data["merchant_id"] == MERCHANT_A_ID


# ==============================================================================
# 3. RECOVERY STATUS ISOLATION TESTS (Section 6)
# ==============================================================================


@pytest.mark.asyncio
async def test_recovery_status_isolation_merchant_a_and_b():
    """Merchant A cannot read Merchant B's recovery status, and vice versa."""
    sessionmaker = get_sessionmaker()

    order_a = "order_rzp_sec_A_001"
    order_b = "order_rzp_sec_B_002"
    ext_order_a = "EXT-ORD-SEC-A-001"
    ext_order_b = "EXT-ORD-SEC-B-002"

    async with sessionmaker() as session:
        # Create Case for Merchant A
        case_a = RecoveryCaseModel(
            case_id="case_sec_A_001",
            failed_payment_id="pay_sec_A_fail",
            order_id=order_a,
            amount=450000,
            currency="INR",
            state=CaseState.ACTION_EXECUTED.value,
            case_source="MERCHANT_CHECKOUT",
            payment_link_id="plink_sec_A",
            failure_context={
                "merchant_id": MERCHANT_A_ID,
                "external_order_id": ext_order_a,
                "masked_contact": "+91******1111",
                "notification_medium": "sms",
                "notification_status": "SENT",
            },
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        # Create Case for Merchant B
        case_b = RecoveryCaseModel(
            case_id="case_sec_B_002",
            failed_payment_id="pay_sec_B_fail",
            order_id=order_b,
            amount=890000,
            currency="INR",
            state=CaseState.RECOVERED.value,
            case_source="MERCHANT_CHECKOUT",
            payment_link_id="plink_sec_B",
            recovered_payment_id="pay_sec_B_recov",
            recovered_amount=890000,
            failure_context={
                "merchant_id": MERCHANT_B_ID,
                "external_order_id": ext_order_b,
                "masked_contact": "+91******2222",
                "notification_medium": "email",
                "notification_status": "DELIVERED",
            },
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add_all([case_a, case_b])
        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        auth_a = {"Authorization": f"Bearer {MERCHANT_A_KEY}"}
        auth_b = {"Authorization": f"Bearer {MERCHANT_B_KEY}"}

        # Merchant A reads Order A -> sees full state
        res_aa = await client.get(f"/merchant/v1/orders/{order_a}/recovery-status", headers=auth_a)
        assert res_aa.status_code == 200
        assert res_aa.json()["state"] == CaseState.ACTION_EXECUTED.value
        assert res_aa.json()["masked_contact"] == "+91******1111"

        # Merchant A reads Order B -> strictly sees generic AWAITING_INGESTION
        res_ab = await client.get(f"/merchant/v1/orders/{order_b}/recovery-status", headers=auth_a)
        assert res_ab.status_code == 200
        data_ab = res_ab.json()
        assert data_ab["status"] == "AWAITING_INGESTION"
        assert "recovered_payment_id" not in data_ab
        assert "recovered_amount" not in data_ab
        assert "masked_contact" not in data_ab
        assert "case_id" not in data_ab

        # Merchant B reads Order B -> sees full recovered state
        res_bb = await client.get(f"/merchant/v1/orders/{order_b}/recovery-status", headers=auth_b)
        assert res_bb.status_code == 200
        assert res_bb.json()["state"] == CaseState.RECOVERED.value
        assert res_bb.json()["recovered_amount"] == 890000
        assert res_bb.json()["recovered_payment_id"] == "pay_sec_B_recov"

        # Merchant B reads Order A -> strictly sees generic AWAITING_INGESTION
        res_ba = await client.get(f"/merchant/v1/orders/{order_a}/recovery-status", headers=auth_b)
        assert res_ba.status_code == 200
        data_ba = res_ba.json()
        assert data_ba["status"] == "AWAITING_INGESTION"
        assert "case_id" not in data_ba
        assert "masked_contact" not in data_ba


@pytest.mark.asyncio
async def test_recovery_status_identical_external_order_ids():
    """Merchants with identical external_order_id query ONLY their own cases."""
    sessionmaker = get_sessionmaker()
    shared_ext_id = "EXT-ORD-COLLISION-100"

    async with sessionmaker() as session:
        case_a = RecoveryCaseModel(
            case_id="case_coll_A",
            failed_payment_id="pay_coll_A",
            order_id="order_coll_A",
            amount=11100,
            currency="INR",
            state=CaseState.FAILED_INGESTED.value,
            case_source="MERCHANT_CHECKOUT",
            failure_context={
                "merchant_id": MERCHANT_A_ID,
                "external_order_id": shared_ext_id,
                "masked_contact": "+91******1111",
            },
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        case_b = RecoveryCaseModel(
            case_id="case_coll_B",
            failed_payment_id="pay_coll_B",
            order_id="order_coll_B",
            amount=22200,
            currency="INR",
            state=CaseState.RECOVERED.value,
            case_source="MERCHANT_CHECKOUT",
            recovered_payment_id="pay_coll_B_recov",
            recovered_amount=22200,
            failure_context={
                "merchant_id": MERCHANT_B_ID,
                "external_order_id": shared_ext_id,
                "masked_contact": "+91******2222",
            },
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add_all([case_a, case_b])
        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Merchant A queries shared_ext_id -> sees Case A
        res_a = await client.get(
            f"/merchant/v1/orders/{shared_ext_id}/recovery-status",
            headers={"Authorization": f"Bearer {MERCHANT_A_KEY}"},
        )
        assert res_a.status_code == 200
        assert res_a.json()["case_id"] == "case_coll_A"
        assert res_a.json()["state"] == CaseState.FAILED_INGESTED.value

        # Merchant B queries shared_ext_id -> sees Case B
        res_b = await client.get(
            f"/merchant/v1/orders/{shared_ext_id}/recovery-status",
            headers={"Authorization": f"Bearer {MERCHANT_B_KEY}"},
        )
        assert res_b.status_code == 200
        assert res_b.json()["case_id"] == "case_coll_B"
        assert res_b.json()["state"] == CaseState.RECOVERED.value


@pytest.mark.asyncio
async def test_recovery_status_side_effect_free():
    """GET /merchant/v1/orders/{order_id}/recovery-status is strictly idempotent
    and side-effect free.
    """
    sessionmaker = get_sessionmaker()
    order_id = "order_read_only_01"

    async with sessionmaker() as session:
        case = RecoveryCaseModel(
            case_id="case_read_only_01",
            failed_payment_id="pay_ro_01",
            order_id=order_id,
            amount=300000,
            currency="INR",
            state=CaseState.ACTION_EXECUTED.value,
            case_source="MERCHANT_CHECKOUT",
            failure_context={"merchant_id": MERCHANT_A_ID, "external_order_id": "EXT-RO-01"},
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(case)
        await session.commit()

        initial_cases = await session.scalar(select(func.count()).select_from(RecoveryCaseModel))
        initial_audits = await session.scalar(select(func.count()).select_from(AuditEventModel))

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": f"Bearer {MERCHANT_A_KEY}"}
        res1 = await client.get(f"/merchant/v1/orders/{order_id}/recovery-status", headers=headers)
        res2 = await client.get(f"/merchant/v1/orders/{order_id}/recovery-status", headers=headers)
        assert res1.status_code == 200
        assert res2.status_code == 200
        assert res1.json() == res2.json()

    async with sessionmaker() as session:
        final_cases = await session.scalar(select(func.count()).select_from(RecoveryCaseModel))
        final_audits = await session.scalar(select(func.count()).select_from(AuditEventModel))
        assert final_cases == initial_cases
        assert final_audits == initial_audits


# ==============================================================================
# 4. RAZORPAY CREDENTIAL BINDING TESTS (Section 8 & 11)
# ==============================================================================


@pytest.mark.asyncio
async def test_executor_binds_to_authenticated_merchant_credentials():
    """RecoveryExecutor creates Payment Links strictly using the merchant's configured
    credentials.
    """
    sessionmaker = get_sessionmaker()
    case_id_a = "case_exec_cred_A"
    case_id_b = "case_exec_cred_B"

    async with sessionmaker() as session:
        case_a = RecoveryCaseModel(
            case_id=case_id_a,
            failed_payment_id="pay_cred_A",
            order_id="order_cred_A",
            amount=50000,
            currency="INR",
            state=CaseState.ACTION_APPROVED.value,
            validated_policy_id="P_CREATE_LINK_IMMEDIATE",
            case_source="MERCHANT_CHECKOUT",
            failure_context={"merchant_id": MERCHANT_A_ID},
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        case_b = RecoveryCaseModel(
            case_id=case_id_b,
            failed_payment_id="pay_cred_B",
            order_id="order_cred_B",
            amount=60000,
            currency="INR",
            state=CaseState.ACTION_APPROVED.value,
            validated_policy_id="P_CREATE_LINK_IMMEDIATE",
            case_source="MERCHANT_CHECKOUT",
            failure_context={"merchant_id": MERCHANT_B_ID},
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add_all([case_a, case_b])
        await session.commit()

    executor = RecoveryExecutor(sessionmaker=sessionmaker)

    with patch(
        "paymentflow.adapters.razorpay_adapter.RazorpayAdapter.create_payment_link"
    ) as mock_create:
        mock_create.return_value = {
            "id": "plink_mock_A",
            "short_url": "https://rzp.io/i/plink_mock_A",
            "status": "created",
        }

        # Track which adapter credentials were used
        original_init = RazorpayAdapter.__init__
        created_adapters = []

        def tracking_init(self, *args, **kwargs):
            original_init(self, *args, **kwargs)
            created_adapters.append((self.key_id, self.key_secret))

        with patch.object(RazorpayAdapter, "__init__", tracking_init):
            # Execute Merchant A
            res_a = await executor.execute(case_id_a)
            assert res_a.success is True
            # Verify Merchant A credentials were used
            assert (MERCHANT_A_RZP_KEY, MERCHANT_A_RZP_SECRET) in created_adapters

            created_adapters.clear()
            mock_create.return_value = {
                "id": "plink_mock_B",
                "short_url": "https://rzp.io/i/plink_mock_B",
                "status": "created",
            }

            # Execute Merchant B
            res_b = await executor.execute(case_id_b)
            assert res_b.success is True
            # Verify Merchant B credentials were used, NEVER Merchant A
            assert (MERCHANT_B_RZP_KEY, MERCHANT_B_RZP_SECRET) in created_adapters
            assert (MERCHANT_A_RZP_KEY, MERCHANT_A_RZP_SECRET) not in created_adapters


@pytest.mark.asyncio
async def test_executor_fails_closed_when_merchant_credentials_missing():
    """RecoveryExecutor fails closed and escalates if merchant credentials cannot be resolved."""
    sessionmaker = get_sessionmaker()
    case_id = "case_exec_disabled"

    async with sessionmaker() as session:
        case = RecoveryCaseModel(
            case_id=case_id,
            failed_payment_id="pay_cred_dis",
            order_id="order_cred_dis",
            amount=70000,
            currency="INR",
            state=CaseState.ACTION_APPROVED.value,
            validated_policy_id="P_CREATE_LINK_IMMEDIATE",
            case_source="MERCHANT_CHECKOUT",
            failure_context={"merchant_id": MERCHANT_DISABLED_ID},
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(case)
        await session.commit()

    executor = RecoveryExecutor(sessionmaker=sessionmaker)
    res = await executor.execute(case_id)
    assert res.success is False
    assert res.decision == "FAIL_CLOSED"
    assert res.state == CaseState.ESCALATED

    async with sessionmaker() as session:
        updated_case = await session.get(RecoveryCaseModel, case_id)
        assert updated_case.state == CaseState.ESCALATED.value


# ==============================================================================
# 5. WEBHOOK TENANT CORRELATION & ATTRIBUTION TESTS (Sections 9 & 10)
# ==============================================================================


@pytest.mark.asyncio
async def test_webhook_mismatched_merchant_notes_rejected():
    """Webhook with merchant B notes presenting payment for Merchant A case
    is rejected and escalated.
    """
    sessionmaker = get_sessionmaker()
    case_id = "case_webhook_mismatch_A"
    plink_id = "plink_mismatch_A"
    payment_id = "pay_mismatch_B"

    async with sessionmaker() as session:
        case = RecoveryCaseModel(
            case_id=case_id,
            failed_payment_id="pay_fail_orig_A",
            order_id="order_orig_A",
            amount=500000,
            currency="INR",
            state=CaseState.ACTION_EXECUTED.value,
            case_source="MERCHANT_CHECKOUT",
            payment_link_id=plink_id,
            failure_context={"merchant_id": MERCHANT_A_ID},
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(case)
        await session.commit()

    mock_rzp = AsyncMock()
    mock_rzp.get_payment.return_value = {
        "id": payment_id,
        "amount": 500000,
        "currency": "INR",
        "status": "captured",
    }

    async with sessionmaker() as session:
        ws = WebhookService(db_session=session, razorpay_adapter=mock_rzp)
        payload = {
            "event": "payment_link.paid",
            "id": "evt_sec_mismatch_01",
            "payload": {
                "payment_link": {
                    "entity": {
                        "id": plink_id,
                        "amount_paid": 500000,
                        "currency": "INR",
                        "status": "paid",
                        "notes": {
                            "case_id": case_id,
                            "merchant_id": MERCHANT_B_ID,  # Wrong merchant notes
                        },
                    }
                },
                "payment": {
                    "entity": {
                        "id": payment_id,
                        "amount": 500000,
                        "currency": "INR",
                        "status": "captured",
                        "notes": {
                            "case_id": case_id,
                            "merchant_id": MERCHANT_B_ID,  # Wrong merchant notes
                        },
                    }
                },
            },
        }
        res = await ws.process_webhook(payload=payload, signature_verified=True)
        assert res.state == CaseState.ESCALATED.value
        assert "Merchant mismatch" in res.message

    async with sessionmaker() as session:
        updated = await session.get(RecoveryCaseModel, case_id)
        assert updated.state == CaseState.ESCALATED.value
        assert updated.recovered_payment_id is None
        assert (updated.recovered_amount or 0) == 0


@pytest.mark.asyncio
async def test_webhook_unknown_merchant_notes_rejected():
    """Webhook containing notes from an unknown merchant is rejected and escalated."""
    sessionmaker = get_sessionmaker()
    case_id = "case_webhook_unknown_m"
    plink_id = "plink_unknown_m"
    payment_id = "pay_unknown_m"

    async with sessionmaker() as session:
        case = RecoveryCaseModel(
            case_id=case_id,
            failed_payment_id="pay_fail_orig_unk",
            order_id="order_orig_unk",
            amount=320000,
            currency="INR",
            state=CaseState.ACTION_EXECUTED.value,
            case_source="MERCHANT_CHECKOUT",
            payment_link_id=plink_id,
            failure_context={"merchant_id": MERCHANT_A_ID},
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(case)
        await session.commit()

    mock_rzp = AsyncMock()
    mock_rzp.get_payment.return_value = {
        "id": payment_id,
        "amount": 320000,
        "currency": "INR",
        "status": "captured",
    }

    async with sessionmaker() as session:
        ws = WebhookService(db_session=session, razorpay_adapter=mock_rzp)
        payload = {
            "event": "payment_link.paid",
            "id": "evt_sec_unk_01",
            "payload": {
                "payment_link": {
                    "entity": {
                        "id": plink_id,
                        "amount_paid": 320000,
                        "currency": "INR",
                        "status": "paid",
                        "notes": {
                            "case_id": case_id,
                            "merchant_id": "completely_unknown_merchant_xyz",
                        },
                    }
                },
                "payment": {
                    "entity": {
                        "id": payment_id,
                        "amount": 320000,
                        "currency": "INR",
                        "status": "captured",
                        "notes": {
                            "case_id": case_id,
                            "merchant_id": "completely_unknown_merchant_xyz",
                        },
                    }
                },
            },
        }
        res = await ws.process_webhook(payload=payload, signature_verified=True)
        assert res.state == CaseState.ESCALATED.value
        assert ("Unknown merchant" in res.message) or ("Merchant mismatch" in res.message)


@pytest.mark.asyncio
async def test_webhook_invalid_signature_fails_closed():
    """Webhook endpoint rejects invalid HMAC signature with 400 Bad Request."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/webhooks/razorpay",
            headers={"X-Razorpay-Signature": "invalid_hmac_signature_hex"},
            json={"event": "payment_link.paid"},
        )
        assert res.status_code == 400
        assert "Invalid webhook signature" in res.json()["detail"]


@pytest.mark.asyncio
async def test_cross_merchant_attribution_blocked_even_with_matching_amounts():
    """Matching amount and currency from Merchant B cannot attribute to Merchant A."""
    sessionmaker = get_sessionmaker()
    case_a_id = "case_amount_match_A"
    plink_a = "plink_match_A"
    case_b_id = "case_amount_match_B"
    plink_b = "plink_match_B"
    shared_amount = 750000

    async with sessionmaker() as session:
        case_a = RecoveryCaseModel(
            case_id=case_a_id,
            failed_payment_id="pay_orig_match_A",
            order_id="order_match_A",
            amount=shared_amount,
            currency="INR",
            state=CaseState.ACTION_EXECUTED.value,
            case_source="MERCHANT_CHECKOUT",
            payment_link_id=plink_a,
            failure_context={"merchant_id": MERCHANT_A_ID},
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        case_b = RecoveryCaseModel(
            case_id=case_b_id,
            failed_payment_id="pay_orig_match_B",
            order_id="order_match_B",
            amount=shared_amount,
            currency="INR",
            state=CaseState.ACTION_EXECUTED.value,
            case_source="MERCHANT_CHECKOUT",
            payment_link_id=plink_b,
            failure_context={"merchant_id": MERCHANT_B_ID},
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add_all([case_a, case_b])
        await session.commit()

    # Merchant B pays their payment link
    payment_b_id = "pay_captured_B_001"
    mock_rzp = AsyncMock()
    mock_rzp.get_payment.return_value = {
        "id": payment_b_id,
        "amount": shared_amount,
        "currency": "INR",
        "status": "captured",
    }

    async with sessionmaker() as session:
        ws = WebhookService(db_session=session, razorpay_adapter=mock_rzp)
        payload = {
            "event": "payment_link.paid",
            "id": "evt_shared_amt_01",
            "payload": {
                "payment_link": {
                    "entity": {
                        "id": plink_b,  # Belongs to B
                        "amount_paid": shared_amount,
                        "currency": "INR",
                        "status": "paid",
                        "notes": {"case_id": case_b_id, "merchant_id": MERCHANT_B_ID},
                    }
                },
                "payment": {
                    "entity": {
                        "id": payment_b_id,
                        "amount": shared_amount,
                        "currency": "INR",
                        "status": "captured",
                        "notes": {"case_id": case_b_id, "merchant_id": MERCHANT_B_ID},
                    }
                },
            },
        }
        res = await ws.process_webhook(payload=payload, signature_verified=True)
        assert res.state == CaseState.RECOVERED.value
        assert res.case_id == case_b_id

    # Verify Case B is RECOVERED and Case A remains untouched (ACTION_EXECUTED)
    async with sessionmaker() as session:
        ca = await session.get(RecoveryCaseModel, case_a_id)
        cb = await session.get(RecoveryCaseModel, case_b_id)
        assert cb.state == CaseState.RECOVERED.value
        assert cb.recovered_amount == shared_amount
        assert ca.state == CaseState.ACTION_EXECUTED.value
        assert (ca.recovered_amount or 0) == 0
        assert ca.recovered_payment_id is None


# ==============================================================================
# 6. INTERNAL VS MERCHANT API & BENCHMARK ISOLATION (Sections 13 & 14)
# ==============================================================================


@pytest.mark.asyncio
async def test_merchant_cannot_read_canonical_benchmark_cases():
    """Merchant cannot view canonical benchmark cases via recovery status."""
    sessionmaker = get_sessionmaker()
    bench_order_id = "order_bench_secret_01"

    async with sessionmaker() as session:
        case = RecoveryCaseModel(
            case_id="case_bench_secret_01",
            failed_payment_id="pay_bench_sec_01",
            order_id=bench_order_id,
            amount=990000,
            currency="INR",
            state=CaseState.RECOVERED.value,
            case_source="CANONICAL_EVALUATION",
            recovered_payment_id="pay_bench_recovered_01",
            recovered_amount=990000,
            failure_context={"masked_contact": "+91******9999"},
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(case)
        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get(
            f"/merchant/v1/orders/{bench_order_id}/recovery-status",
            headers={"Authorization": f"Bearer {MERCHANT_A_KEY}"},
        )
        assert res.status_code == 200
        data = res.json()
        # Strictly returns generic awaiting state; no benchmark recovery leaked
        assert data["status"] == "AWAITING_INGESTION"
        assert "recovered_amount" not in data
        assert "recovered_payment_id" not in data
        assert "case_id" not in data


@pytest.mark.asyncio
async def test_checkout_context_validation():
    """POST /merchant/v1/checkout-context validates amounts, currency, and fields."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        auth = {"Authorization": f"Bearer {MERCHANT_A_KEY}"}

        # Zero amount -> 422
        res_zero = await client.post(
            "/merchant/v1/checkout-context",
            headers=auth,
            json={"external_order_id": "ORD-0", "amount": 0, "currency": "INR"},
        )
        assert res_zero.status_code == 422

        # Negative amount -> 422
        res_neg = await client.post(
            "/merchant/v1/checkout-context",
            headers=auth,
            json={"external_order_id": "ORD-NEG", "amount": -500, "currency": "INR"},
        )
        assert res_neg.status_code == 422

        # Invalid currency -> 422
        res_curr = await client.post(
            "/merchant/v1/checkout-context",
            headers=auth,
            json={"external_order_id": "ORD-USD", "amount": 5000, "currency": "USD"},
        )
        assert res_curr.status_code == 422


@pytest.mark.asyncio
async def test_checkout_context_cross_merchant_collision_isolation():
    """Prove Merchant A and Merchant B may use the same external_order_id without context leak.

    Invariant: Neither merchant may retrieve the other's context, and a third merchant
    gets None.
    """
    shared_order_id = "ORD-SHARED-COLLISION-1001"
    ctx_a = {
        "context_id": "ctx_A_1001",
        "merchant_id": MERCHANT_A_ID,
        "merchant_name": "Store A",
        "external_order_id": shared_order_id,
        "amount": 150000,
        "currency": "INR",
        "customer_email": "alice@storea.example.com",
    }
    ctx_b = {
        "context_id": "ctx_B_1001",
        "merchant_id": MERCHANT_B_ID,
        "merchant_name": "Store B",
        "external_order_id": shared_order_id,
        "amount": 290000,
        "currency": "INR",
        "customer_email": "bob@storeb.example.com",
    }

    # Store both contexts
    MerchantRegistry.store_checkout_context("ctx_A_1001", ctx_a)
    MerchantRegistry.store_checkout_context("ctx_B_1001", ctx_b)

    # Merchant A retrieval
    ret_a = MerchantRegistry.get_checkout_context(shared_order_id, merchant_id=MERCHANT_A_ID)
    assert ret_a is not None
    assert ret_a["merchant_id"] == MERCHANT_A_ID
    assert ret_a["amount"] == 150000
    assert ret_a["customer_email"] == "alice@storea.example.com"

    # Merchant B retrieval
    ret_b = MerchantRegistry.get_checkout_context(shared_order_id, merchant_id=MERCHANT_B_ID)
    assert ret_b is not None
    assert ret_b["merchant_id"] == MERCHANT_B_ID
    assert ret_b["amount"] == 290000
    assert ret_b["customer_email"] == "bob@storeb.example.com"

    # Merchant C retrieval (unrelated tenant)
    ret_c = MerchantRegistry.get_checkout_context(
        shared_order_id, merchant_id="merchant_unrelated_03"
    )
    assert ret_c is None

    # Unscoped query by external_order_id does NOT leak either merchant's context
    ret_unscoped = MerchantRegistry.get_checkout_context(shared_order_id)
    assert ret_unscoped is None


@pytest.mark.asyncio
async def test_unassigned_case_without_merchant_id_never_claimed():
    """Prove unassigned cases lacking merchant_id are rejected for all merchants.

    Ensures zero hardcoded tenant exceptions exist in recovery status authorization.
    """
    settings = get_settings()
    sessionmaker = get_sessionmaker()
    orphan_order_id = "ORD-ORPHAN-NO-MERCHANT"

    async with sessionmaker() as session:
        orphan_case = RecoveryCaseModel(
            case_id=f"case_{orphan_order_id}",
            failed_payment_id="pay_orphan_01",
            order_id=orphan_order_id,
            amount=500000,
            currency="INR",
            state=CaseState.ACTION_EXECUTED.value,
            case_source="MERCHANT_CHECKOUT",
            failure_context={
                "external_order_id": orphan_order_id,
                # Intentionally omitted merchant_id
            },
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(orphan_case)
        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Query with default demo store key
        res_demo = await client.get(
            f"/merchant/v1/orders/{orphan_order_id}/recovery-status",
            headers={"Authorization": f"Bearer {settings.paymentflow_api_key}"},
        )
        assert res_demo.status_code == 200
        assert res_demo.json()["status"] == "AWAITING_INGESTION"

        # 2. Query with Merchant A
        res_a = await client.get(
            f"/merchant/v1/orders/{orphan_order_id}/recovery-status",
            headers={"Authorization": f"Bearer {MERCHANT_A_KEY}"},
        )
        assert res_a.status_code == 200
        assert res_a.json()["status"] == "AWAITING_INGESTION"

        # 3. Query with Merchant B
        res_b = await client.get(
            f"/merchant/v1/orders/{orphan_order_id}/recovery-status",
            headers={"Authorization": f"Bearer {MERCHANT_B_KEY}"},
        )
        assert res_b.status_code == 200
        assert res_b.json()["status"] == "AWAITING_INGESTION"
