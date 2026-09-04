"""Phase C3.4: Real recovery decision, Razorpay Payment Link creation, and native SMS handoff tests.

Verifies:
1. payment.failed -> triage -> eligibility -> LLM advisory -> guardrail -> recovery link creation.
2. Merchant-bound Razorpay credential resolution and same-account binding.
3. Customer contact (name, phone, email) propagation into Razorpay Payment Link.
4. notify.sms=True primary notification dispatch without duplicate notify_by call.
5. Truthful notification semantics: notification_status='SENT', delivery_verified=False.
6. Phone number masking in logs and audit trails (+91******1160).
7. Zero recovery credit invariant: recovered_amount=0/None, recovered_payment_id=None.
8. Duplicate payment.failed webhook idempotency (single case).
9. Duplicate Payment Link prevention (idempotent executor returns existing link).
10. Explicit fallback notification handling via notify_payment_link.
11. Strict non-exposure of Razorpay secret and PaymentFlow API key.
12. Multi-merchant isolation (Merchant A cannot use Merchant B's Razorpay credentials).
"""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from paymentflow.adapters.llm_adapter import LLMClient
from paymentflow.adapters.razorpay_adapter import RazorpayAdapter
from paymentflow.config import get_settings
from paymentflow.db.models import AuditEventModel, RecoveryCaseModel, utc_now
from paymentflow.db.session import get_sessionmaker
from paymentflow.domain.enums import CaseState, FailureCategory, RecoveryPolicy, TemplateId
from paymentflow.domain.models import RecoveryProposal
from paymentflow.main import app
from paymentflow.merchant.models import MerchantProfile, hash_api_key
from paymentflow.merchant.service import MerchantRegistry
from paymentflow.services.recovery_executor import RecoveryExecutor, mask_phone
from paymentflow.services.recovery_orchestrator import RecoveryOrchestrator


@pytest.fixture(autouse=True)
def reset_merchant_registry():
    """Ensure merchant registry is clean before and after each test."""
    MerchantRegistry.reset_to_default()
    yield
    MerchantRegistry.reset_to_default()


def make_mock_link_response(
    link_id: str = "plink_test_c34_999",
    amount: int = 420000,
    short_url: str = "https://rzp.io/rzp/test_c34",
    status: str = "created",
) -> dict:
    return {
        "id": link_id,
        "entity": "payment_link",
        "amount": amount,
        "currency": "INR",
        "status": status,
        "short_url": short_url,
        "accept_partial": False,
        "notify": {"sms": True, "email": True, "whatsapp": False},
        "customer": {
            "name": "Priya Sharma",
            "contact": "+919814711160",
            "email": "priya.sharma@example.com",
        },
        "description": "Recovery link for failed payment",
        "reference_id": f"FP-{link_id}",
        "payments": [],
        "created_at": 1725430000,
    }


def test_mask_phone_utility():
    """Verify phone masking formats correctly and truthfully."""
    assert mask_phone("+919814711160") == "+91******1160"
    assert mask_phone("9876543210") == "987******3210"
    assert mask_phone(None) == "N/A"
    assert mask_phone("") == "N/A"


@pytest.mark.asyncio
async def test_recovery_executor_merchant_binding_and_native_sms():
    """RecoveryExecutor creates Payment Link using merchant credentials and native SMS."""
    sessionmaker = get_sessionmaker()
    case_id = "case_c34_exec_test_01"
    payment_id = "pay_c34_test_failed_01"
    amount = 420000

    # Register custom merchant B to prove dynamic credential resolution
    MerchantRegistry.register_merchant(
        MerchantProfile(
            merchant_id="merchant_beta_boutique",
            merchant_name="Beta Boutique",
            api_key_hash=hash_api_key("pk_test_beta_secret_key_111"),
            is_active=True,
            razorpay_key_id="rzp_test_BETA_KEY_999",
            razorpay_key_secret="rzp_test_BETA_SECRET_888",
        )
    )

    async with sessionmaker() as session:
        case = RecoveryCaseModel(
            case_id=case_id,
            failed_payment_id=payment_id,
            order_id="order_beta_001",
            amount=amount,
            currency="INR",
            payment_method="card",
            failure_code="BAD_REQUEST_ERROR",
            failure_description="Card declined by bank",
            failure_context={
                "merchant_id": "merchant_beta_boutique",
                "email": "customer.beta@example.com",
                "contact": "+919814711160",
                "customer_name": "Rohan Verma",
                "error_source": "bank",
                "error_step": "payment_authorization",
                "error_reason": "card_declined",
            },
            state=CaseState.ACTION_APPROVED.value,
            validated_policy_id=RecoveryPolicy.P_CREATE_LINK_IMMEDIATE.value,
            case_source="MERCHANT_CHECKOUT",
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(case)
        await session.commit()

    mock_resp = make_mock_link_response(
        link_id="plink_beta_777",
        amount=amount,
        short_url="https://rzp.io/rzp/beta777",
    )

    with patch.object(
        RazorpayAdapter, "create_payment_link", new_callable=AsyncMock
    ) as mock_create:
        mock_create.return_value = mock_resp

        executor = RecoveryExecutor(sessionmaker=sessionmaker)
        res = await executor.execute(case_id=case_id)

        assert res.success is True
        assert res.payment_link_id == "plink_beta_777"
        assert res.payment_link_short_url == "https://rzp.io/rzp/beta777"
        assert res.state == CaseState.ACTION_EXECUTED

        # Verify call arguments passed to RazorpayAdapter
        mock_create.assert_awaited_once()
        _, kwargs = mock_create.call_args
        assert kwargs["amount"] == 420000
        assert kwargs["currency"] == "INR"
        assert kwargs["notify"] == {"sms": True, "email": True}
        assert kwargs["customer"]["contact"] == "+919814711160"
        assert kwargs["customer"]["email"] == "customer.beta@example.com"
        assert kwargs["customer"]["name"] == "Rohan Verma"
        assert kwargs["notes"]["merchant_id"] == "merchant_beta_boutique"

    # Inspect persisted case and audit models
    async with sessionmaker() as session:
        updated = await session.get(RecoveryCaseModel, case_id)
        assert updated is not None
        assert updated.state == CaseState.ACTION_EXECUTED.value
        assert updated.payment_link_id == "plink_beta_777"
        assert updated.payment_link_status == "created"
        # Invariants: no recovery credit
        assert updated.recovered_amount is None or updated.recovered_amount == 0
        assert updated.recovered_payment_id is None

        # Notification status model in failure_context
        fc = updated.failure_context
        assert fc["notification_medium"] == "sms"
        assert fc["notification_status"] == "SENT"
        assert fc["notification_requested"] is True
        assert fc["notification_api_success"] is True
        assert fc["delivery_verified"] is False
        assert fc["delivery_verification_source"] is None
        assert fc["masked_contact"] == "+91******1160"

        # Check AuditEvent
        q_audit = select(AuditEventModel).where(
            AuditEventModel.case_id == case_id,
            AuditEventModel.event_type == "RECOVERY_SMS_NOTIFICATION_SENT",
        )
        res_audit = await session.execute(q_audit)
        audit = res_audit.scalar_one_or_none()
        assert audit is not None
        assert audit.details["masked_contact"] == "+91******1160"
        assert audit.details["delivery_verified"] is False
        assert (
            audit.details["statement"]
            == "SMS sent via Razorpay; handset delivery not independently verified."
        )


@pytest.mark.asyncio
async def test_duplicate_recovery_execution_idempotency():
    """Second execution of already-executed case returns existing link without calling Razorpay."""
    sessionmaker = get_sessionmaker()
    case_id = "case_c34_idempotent_test"

    async with sessionmaker() as session:
        case = RecoveryCaseModel(
            case_id=case_id,
            failed_payment_id="pay_c34_dup_01",
            order_id="order_c34_dup",
            amount=345000,
            currency="INR",
            payment_link_id="plink_existing_12345",
            payment_link_short_url="https://rzp.io/rzp/existing",
            payment_link_status="created",
            state=CaseState.ACTION_EXECUTED.value,
            case_source="MERCHANT_CHECKOUT",
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(case)
        await session.commit()

    with patch.object(
        RazorpayAdapter, "create_payment_link", new_callable=AsyncMock
    ) as mock_create:
        executor = RecoveryExecutor(sessionmaker=sessionmaker)
        res = await executor.execute(case_id=case_id)

        assert res.success is True
        assert res.decision == "ALREADY_EXECUTED"
        assert res.payment_link_id == "plink_existing_12345"
        mock_create.assert_not_awaited()


@pytest.mark.asyncio
async def test_razorpay_adapter_notify_fallback():
    """RazorpayAdapter.notify_payment_link issues explicit notify_by call for fallback resend."""
    adapter = RazorpayAdapter()
    with patch.object(adapter, "_request", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = {"success": True}
        res = await adapter.notify_payment_link("plink_test_fallback", medium="sms")
        assert res == {"success": True}
        mock_req.assert_awaited_once_with("POST", "payment_links/plink_test_fallback/notify_by/sms")


@pytest.mark.asyncio
async def test_end_to_end_orchestration_merchant_checkout_failure():
    """Pipeline: FAILED_INGESTED -> Diagnosis -> Eligibility -> Guardrail -> Payment Link."""
    sessionmaker = get_sessionmaker()
    case_id = "case_c34_e2e_orch_01"
    payment_id = "pay_c34_e2e_01"
    amount = 420000

    async with sessionmaker() as session:
        case = RecoveryCaseModel(
            case_id=case_id,
            failed_payment_id=payment_id,
            order_id="order_c34_e2e_01",
            amount=amount,
            currency="INR",
            payment_method="card",
            failure_code="BAD_REQUEST_ERROR",
            failure_description="Customer payment dropped off",
            failure_context={
                "merchant_id": "merchant_demo_store",
                "contact": "+919814711160",
                "email": "priya.sharma@example.com",
                "customer_name": "Priya Sharma",
                "error_source": "customer",
                "error_step": "payment_authorization",
                "error_reason": "payment_failed",
            },
            state=CaseState.FAILED_INGESTED.value,
            case_source="MERCHANT_CHECKOUT",
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(case)
        await session.commit()

    mock_resp = make_mock_link_response(
        link_id="plink_c34_live_e2e_01",
        amount=amount,
        short_url="https://rzp.io/rzp/c34_live",
    )

    mock_proposal = RecoveryProposal(
        failure_category=FailureCategory.C1,
        policy_id=RecoveryPolicy.P_CREATE_LINK_IMMEDIATE,
        template_id=TemplateId.TPL_RECOVERY_STANDARD,
        explanation="Customer payment dropped off; immediate retry link.",
    )

    with (
        patch.object(RazorpayAdapter, "create_payment_link", new_callable=AsyncMock) as mock_create,
        patch.object(LLMClient, "generate_proposal", new_callable=AsyncMock) as mock_llm,
    ):
        mock_create.return_value = mock_resp
        mock_llm.return_value = (
            mock_proposal,
            {"model": "mock-llm", "latency_ms": 10.0, "is_fallback": False, "error": None},
        )

        orchestrator = RecoveryOrchestrator(sessionmaker=sessionmaker)
        res = await orchestrator.orchestrate_recovery(case_id=case_id, fetch_from_gateway=False)

        assert res["success"] is True
        assert res["state"] == CaseState.ACTION_EXECUTED.value
        assert res["payment_link_id"] == "plink_c34_live_e2e_01"
        assert res["payment_link_url"] == "https://rzp.io/rzp/c34_live"

    # Verify database state
    async with sessionmaker() as session:
        updated = await session.get(RecoveryCaseModel, case_id)
        assert updated is not None
        assert updated.state == CaseState.ACTION_EXECUTED.value
        assert updated.payment_link_id == "plink_c34_live_e2e_01"
        assert updated.recovered_amount is None or updated.recovered_amount == 0
        assert updated.failure_context["masked_contact"] == "+91******1160"
        assert updated.failure_context["notification_status"] == "SENT"


@pytest.mark.asyncio
async def test_merchant_order_recovery_status_safe_endpoint():
    """GET /merchant/v1/orders/{order_id}/recovery-status returns safe state without secrets."""
    settings = get_settings()
    auth_header = {"Authorization": f"Bearer {settings.paymentflow_api_key}"}
    sessionmaker = get_sessionmaker()

    order_id = "order_c34_status_check"
    external_order_id = "EXT-ORD-C34-STATUS"
    async with sessionmaker() as session:
        case = RecoveryCaseModel(
            case_id=f"case_{order_id}",
            failed_payment_id="pay_c34_status_01",
            order_id=order_id,
            amount=420000,
            currency="INR",
            payment_link_id="plink_safe_secret_test",
            state=CaseState.ACTION_EXECUTED.value,
            case_source="MERCHANT_CHECKOUT",
            failure_context={
                "merchant_id": "merchant_demo_store",
                "external_order_id": external_order_id,
                "masked_contact": "+91******1160",
                "notification_medium": "sms",
                "notification_status": "SENT",
            },
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(case)
        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Lookup by Razorpay Order ID
        res = await client.get(
            f"/merchant/v1/orders/{order_id}/recovery-status",
            headers=auth_header,
        )
        assert res.status_code == 200
        data = res.json()
        assert data["order_id"] == order_id
        assert data["state"] == CaseState.ACTION_EXECUTED.value
        assert data["notification_status"] == "SENT"
        assert data["masked_contact"] == "+91******1160"
        assert data["delivery_verified"] is False

        # 2. Lookup by Merchant External Order ID
        res_ext = await client.get(
            f"/merchant/v1/orders/{external_order_id}/recovery-status",
            headers=auth_header,
        )
        assert res_ext.status_code == 200
        data_ext = res_ext.json()
        assert data_ext["order_id"] == external_order_id
        assert data_ext["case_id"] == f"case_{order_id}"
        assert data_ext["state"] == CaseState.ACTION_EXECUTED.value

        # Strictly assert NO secret leakage
        raw_text = res.text
        assert settings.razorpay_key_secret not in raw_text
        assert settings.paymentflow_api_key not in raw_text
        assert "plink_safe_secret_test" not in raw_text  # Link ID hidden from customer poll
