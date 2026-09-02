"""End-to-end integration tests for Layer 2 pipeline."""

import hashlib
import hmac
import json

import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from paymentflow.adapters.razorpay_adapter import RazorpayAdapter
from paymentflow.config import Settings
from paymentflow.db.models import AuditEventModel, RecoveryCaseModel, utc_now
from paymentflow.db.session import get_sessionmaker
from paymentflow.domain.enums import CaseState, EligibilityStatus, FailureCategory
from paymentflow.services.recovery_service import RecoveryTriageService


def make_signed_headers(body: bytes, secret: str) -> dict[str, str]:
    sig = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return {"Content-Type": "application/json", "X-Razorpay-Signature": sig}


@pytest.fixture
def mock_gateway_client() -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if "pay_e2e_001" in path:
            return httpx.Response(
                200,
                json={
                    "id": "pay_e2e_001",
                    "entity": "payment",
                    "amount": 199900,
                    "currency": "INR",
                    "status": "failed",
                    "order_id": "order_e2e_001",
                    "customer_id": "cust_e2e_001",
                    "method": "card",
                    "error_code": "BAD_REQUEST_ERROR",
                    "error_description": "Card authentication failed",
                    "error_source": "customer",
                    "error_step": "payment_authentication",
                    "error_reason": "card_declined",
                },
            )
        if "order_e2e_001" in path:
            return httpx.Response(
                200,
                json={"id": "order_e2e_001", "amount": 199900, "status": "attempted"},
            )
        return httpx.Response(404, json={"error": {"description": "Not found"}})

    transport = httpx.MockTransport(handler)
    return httpx.AsyncClient(transport=transport)


@pytest.mark.asyncio
async def test_layer2_end_to_end_eligible_pipeline(
    client: AsyncClient,
    test_settings: Settings,
    mock_gateway_client: httpx.AsyncClient,
):
    """Full Layer 2 pipeline: Webhook Ingest -> Enrichment -> Classification -> Eligibility."""
    # 1. Ingest payment.failed webhook
    payload = {
        "entity": "event",
        "event": "payment.failed",
        "id": "evt_e2e_001",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_e2e_001",
                    "amount": 199900,
                    "currency": "INR",
                    "status": "failed",
                    "method": "card",
                    "error_code": "BAD_REQUEST_ERROR",
                    "error_description": "Card authentication failed",
                }
            }
        },
    }
    raw_body = json.dumps(payload).encode("utf-8")
    headers = make_signed_headers(raw_body, test_settings.razorpay_webhook_secret)

    res = await client.post("/webhooks/razorpay", content=raw_body, headers=headers)
    assert res.status_code == 200
    case_id = res.json()["case_id"]
    assert case_id == "case_pay_e2e_001"

    # 2. Run Layer 2 Triage Pipeline
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        adapter = RazorpayAdapter(settings=test_settings, http_client=mock_gateway_client)
        service = RecoveryTriageService(session, razorpay_adapter=adapter)

        case, decision = await service.process_triage_pipeline(case_id)

        # 3. Assert Case In-Memory State
        assert case.state == CaseState.ELIGIBILITY_CHECKED.value
        assert case.failure_category == FailureCategory.C1.value
        assert case.eligibility_status == EligibilityStatus.ELIGIBLE.value
        assert decision.eligible is True
        assert decision.evaluated_amount == 199900

    # 4. Verify Database Persistence Reload
    async with sessionmaker() as session:
        reloaded = await session.get(RecoveryCaseModel, case_id)
        assert reloaded is not None
        assert reloaded.state == CaseState.ELIGIBILITY_CHECKED.value
        assert reloaded.failure_category == "C1"
        assert "CUSTOMER_ACTION" in reloaded.classification_evidence["matched_rule"]
        assert reloaded.eligibility_status == "ELIGIBLE"
        assert reloaded.eligibility_reason == "ELIGIBLE"

        # 5. Verify Chronological Audit Trail
        audit_res = await session.execute(
            select(AuditEventModel)
            .where(AuditEventModel.case_id == case_id)
            .order_by(AuditEventModel.id)
        )
        audits = audit_res.scalars().all()
        event_types = [a.event_type for a in audits]

        assert "WEBHOOK_INGESTED" in event_types
        assert "CONTEXT_ENRICHED" in event_types
        assert "FAILURE_CLASSIFIED" in event_types
        assert "ELIGIBILITY_EVALUATED" in event_types


@pytest.mark.asyncio
async def test_layer2_high_value_escalation_pipeline(test_settings: Settings):
    """Verify high-value payment failure cleanly escalates in the pipeline."""
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        case = RecoveryCaseModel(
            case_id="case_high_val_01",
            failed_payment_id="pay_high_val_01",
            amount=75_000_00,  # ₹75,000
            currency="INR",
            state=CaseState.FAILED_INGESTED.value,
            failure_code="CARD_DECLINED",
            failure_context={"error_reason": "card_declined"},
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(case)
        await session.commit()

        service = RecoveryTriageService(session)
        case, decision = await service.process_triage_pipeline(
            "case_high_val_01", fetch_from_gateway=False
        )

        assert case.state == CaseState.ESCALATED.value
        assert case.eligibility_status == EligibilityStatus.REQUIRES_ESCALATION.value
        assert decision.eligible is False


@pytest.mark.asyncio
async def test_layer2_unsupported_category_pipeline(test_settings: Settings):
    """Verify C4 (Risk) failure transitions to TERMINAL_NO_ACTION."""
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        case = RecoveryCaseModel(
            case_id="case_risk_01",
            failed_payment_id="pay_risk_01",
            amount=100000,
            currency="INR",
            state=CaseState.FAILED_INGESTED.value,
            failure_code="TRANSACTION_LIMIT_EXCEEDED",
            failure_context={"error_reason": "limit_exceeded"},
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(case)
        await session.commit()

        service = RecoveryTriageService(session)
        case, decision = await service.process_triage_pipeline(
            "case_risk_01", fetch_from_gateway=False
        )

        assert case.failure_category == FailureCategory.C4.value
        assert case.state == CaseState.TERMINAL_NO_ACTION.value
        assert case.eligibility_status == EligibilityStatus.INELIGIBLE.value
        assert decision.eligible is False


@pytest.mark.asyncio
async def test_layer2_customer_cooldown_exhaustion(test_settings: Settings):
    """Verify customer exceeding daily cooldown transitions to TERMINAL_NO_ACTION."""
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        # Create 3 prior recovery cases with payment links for this customer
        for i in range(3):
            prior_case = RecoveryCaseModel(
                case_id=f"case_prior_cool_{i}",
                failed_payment_id=f"pay_prior_cool_{i}",
                customer_id="cust_cooldown_user",
                amount=50000,
                currency="INR",
                state=CaseState.ACTION_EXECUTED.value,
                payment_link_id=f"plink_cool_{i}",
                created_at=utc_now(),
                updated_at=utc_now(),
            )
            session.add(prior_case)

        # Create 4th case for same customer
        new_case = RecoveryCaseModel(
            case_id="case_4th_cooldown_case",
            failed_payment_id="pay_4th_cooldown",
            customer_id="cust_cooldown_user",
            amount=50000,
            currency="INR",
            state=CaseState.FAILED_INGESTED.value,
            failure_code="AUTHENTICATION_FAILED",
            failure_context={"error_reason": "otp_timeout"},
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(new_case)
        await session.commit()

        service = RecoveryTriageService(session)
        case, decision = await service.process_triage_pipeline(
            "case_4th_cooldown_case", fetch_from_gateway=False
        )

        assert decision.eligible is False
        assert decision.reason_code.value == "INELIGIBLE_COOLDOWN"
        assert case.state == CaseState.TERMINAL_NO_ACTION.value
