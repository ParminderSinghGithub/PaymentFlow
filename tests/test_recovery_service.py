"""Unit and service tests for RecoveryTriageService."""

import httpx
import pytest

from paymentflow.adapters.razorpay_adapter import RazorpayAdapter
from paymentflow.config import Settings
from paymentflow.db.models import RecoveryCaseModel, utc_now
from paymentflow.db.session import get_sessionmaker
from paymentflow.domain.enums import CaseState, EligibilityStatus, FailureCategory
from paymentflow.domain.exceptions import DomainError
from paymentflow.services.recovery_service import RecoveryTriageService


@pytest.fixture
def mock_razorpay_client() -> httpx.AsyncClient:
    """Mock transport returning standard Razorpay responses."""
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if "/v1/payments/pay_mock_001" in path:
            return httpx.Response(
                200,
                json={
                    "id": "pay_mock_001",
                    "entity": "payment",
                    "amount": 299900,
                    "currency": "INR",
                    "status": "failed",
                    "order_id": "order_mock_001",
                    "customer_id": "cust_mock_001",
                    "method": "card",
                    "error_code": "BAD_REQUEST_ERROR",
                    "error_description": "Card was declined by issuing bank",
                    "error_source": "bank",
                    "error_step": "payment_authorization",
                    "error_reason": "card_declined",
                },
            )
        if "/v1/orders/order_mock_001" in path:
            return httpx.Response(
                200,
                json={
                    "id": "order_mock_001",
                    "entity": "order",
                    "amount": 299900,
                    "status": "attempted",
                },
            )
        return httpx.Response(404, json={"error": {"description": "Not found"}})

    transport = httpx.MockTransport(handler)
    return httpx.AsyncClient(transport=transport)


@pytest.mark.asyncio
async def test_recovery_triage_service_enrichment(mock_razorpay_client: httpx.AsyncClient):
    """Verify context enrichment transitions state to CONTEXT_RETRIEVED and updates data."""
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        # Create initial case
        case = RecoveryCaseModel(
            case_id="case_srv_test_01",
            failed_payment_id="pay_mock_001",
            amount=1000,
            currency="INR",
            state=CaseState.FAILED_INGESTED.value,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(case)
        await session.commit()

        adapter = RazorpayAdapter(
            settings=Settings(razorpay_key_id="test", razorpay_key_secret="test"),
            http_client=mock_razorpay_client,
        )
        service = RecoveryTriageService(session, razorpay_adapter=adapter)

        enriched_case = await service.enrich_context("case_srv_test_01")
        assert enriched_case.state == CaseState.CONTEXT_RETRIEVED.value
        assert enriched_case.amount == 299900
        assert enriched_case.customer_id == "cust_mock_001"
        assert enriched_case.order_id == "order_mock_001"
        assert enriched_case.payment_method == "card"


@pytest.mark.asyncio
async def test_recovery_triage_service_classification_and_eligibility():
    """Verify classification and eligibility evaluation update case and transition state."""
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        case = RecoveryCaseModel(
            case_id="case_srv_test_02",
            failed_payment_id="pay_mock_002",
            customer_id="cust_srv_02",
            amount=450000,
            currency="INR",
            failure_code="PAYMENT_AUTHENTICATION_ERROR",
            failure_description="OTP expired",
            failure_context={"error_reason": "otp_timeout"},
            state=CaseState.CONTEXT_RETRIEVED.value,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(case)
        await session.commit()

        service = RecoveryTriageService(session)

        # 1. Classify
        classified = await service.classify_case("case_srv_test_02")
        assert classified.failure_category == FailureCategory.C1.value
        assert classified.classification_evidence is not None

        # 2. Evaluate Eligibility
        eval_case, decision = await service.evaluate_eligibility("case_srv_test_02")
        assert eval_case.state == CaseState.ELIGIBILITY_CHECKED.value
        assert eval_case.eligibility_status == EligibilityStatus.ELIGIBLE.value
        assert decision.eligible is True


@pytest.mark.asyncio
async def test_recovery_triage_service_high_value_escalation():
    """Verify high-value case transitions to ESCALATED."""
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        case = RecoveryCaseModel(
            case_id="case_srv_high_01",
            failed_payment_id="pay_high_001",
            amount=60_000_00,  # ₹60,000 > ₹50,000 threshold
            currency="INR",
            failure_category=FailureCategory.C1.value,
            state=CaseState.CONTEXT_RETRIEVED.value,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(case)
        await session.commit()

        service = RecoveryTriageService(session)
        eval_case, decision = await service.evaluate_eligibility("case_srv_high_01")
        assert eval_case.state == CaseState.ESCALATED.value
        assert eval_case.eligibility_status == EligibilityStatus.REQUIRES_ESCALATION.value
        assert decision.eligible is False


@pytest.mark.asyncio
async def test_recovery_triage_service_gateway_error_safe_terminal():
    """Verify gateway error fails safely and transitions to ERROR_TERMINAL."""
    def error_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Network unreachable")

    transport = httpx.MockTransport(error_handler)
    async with httpx.AsyncClient(transport=transport) as error_client:
        sessionmaker = get_sessionmaker()
        async with sessionmaker() as session:
            case = RecoveryCaseModel(
                case_id="case_srv_err_01",
                failed_payment_id="pay_err_001",
                amount=5000,
                currency="INR",
                state=CaseState.FAILED_INGESTED.value,
                created_at=utc_now(),
                updated_at=utc_now(),
            )
            session.add(case)
            await session.commit()

            adapter = RazorpayAdapter(http_client=error_client)
            service = RecoveryTriageService(session, razorpay_adapter=adapter)

            with pytest.raises(DomainError):
                await service.enrich_context("case_srv_err_01")

            reloaded_case = await service.get_case("case_srv_err_01")
            assert reloaded_case.state == CaseState.ERROR_TERMINAL.value
