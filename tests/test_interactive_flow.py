"""Comprehensive unit and integration tests for Phase 2B Interactive Recovery Flow.

Hermetic test suite exercising the real InteractiveRecoveryService + RecoveryOrchestrator +
PolicyGuardrailEngine pipeline with injected deterministic mock LLM and Razorpay adapters.
"""

import json
from typing import Any

import httpx
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from paymentflow.adapters.llm_adapter import LLMClient
from paymentflow.adapters.razorpay_adapter import RazorpayAdapter
from paymentflow.api.interactive import get_interactive_service
from paymentflow.config import Settings
from paymentflow.db.models import AuditEventModel, RecoveryCaseModel
from paymentflow.db.session import get_sessionmaker
from paymentflow.domain.enums import CaseState
from paymentflow.eval.canonical_batch import seed_canonical_demonstration_batch
from paymentflow.main import app
from paymentflow.mcp.client import RecoveryAgentClient
from paymentflow.services.interactive_service import (
    INTERACTIVE_CASE_ID,
    InteractiveRecoveryService,
)
from paymentflow.services.recovery_executor import RecoveryExecutor
from paymentflow.services.recovery_orchestrator import RecoveryOrchestrator


@pytest.fixture
def mock_gemini_cs01() -> httpx.AsyncClient:
    """Mock Gemini transport returning valid CS01 advisory proposal deterministically."""

    def handler(request: httpx.Request) -> httpx.Response:
        resp = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": json.dumps(
                                    {
                                        "failure_category": "C1",
                                        "policy_id": "P_CREATE_LINK_IMMEDIATE",
                                        "template_id": "TPL_RECOVERY_STANDARD",
                                        "explanation": (
                                            "Customer dropped off during OTP entry. "
                                            "Immediate recovery payment link recommended."
                                        ),
                                    }
                                )
                            }
                        ]
                    }
                }
            ]
        }
        return httpx.Response(200, json=resp, request=request)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.fixture
def mock_razorpay_adapter(test_settings: Settings) -> RazorpayAdapter:
    """Mock RazorpayAdapter returning realistic Test Mode responses."""
    adapter = RazorpayAdapter(settings=test_settings)

    async def mock_get_payment(payment_id: str) -> dict[str, Any]:
        return {
            "id": payment_id,
            "entity": "payment",
            "amount": 250000,
            "currency": "INR",
            "status": "captured",
            "payment_link_id": "plink_mock_live_cs01",
        }

    async def mock_get_payment_link(payment_link_id: str) -> dict[str, Any]:
        return {
            "id": payment_link_id,
            "short_url": "https://rzp.io/rzp/mockCS01",
            "status": "created",
            "amount": 250000,
            "currency": "INR",
            "payments": [],
        }

    async def mock_create_payment_link(
        amount: int,
        currency: str = "INR",
        description: str = "",
        reference_id: str | None = None,
        expire_by: int | None = None,
        notes: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        return {
            "id": "plink_mock_live_cs01",
            "amount": amount,
            "currency": currency,
            "status": "created",
            "short_url": "https://rzp.io/rzp/mockCS01",
            "reference_id": reference_id,
        }

    adapter.get_payment = mock_get_payment  # type: ignore
    adapter.get_payment_link = mock_get_payment_link  # type: ignore
    adapter.create_payment_link = mock_create_payment_link  # type: ignore
    return adapter


@pytest.fixture
def interactive_service(
    test_settings: Settings,
    mock_gemini_cs01: httpx.AsyncClient,
    mock_razorpay_adapter: RazorpayAdapter,
) -> InteractiveRecoveryService:
    """Construct InteractiveRecoveryService with real orchestrator and mock adapters."""
    settings = test_settings.model_copy(
        update={
            "llm_api_key": "valid_test_gemini_key",
            "llm_model": "gemini-3.5-flash-lite",
        }
    )
    sessionmaker = get_sessionmaker()
    llm_client = LLMClient(settings=settings, http_client=mock_gemini_cs01)
    agent_client = RecoveryAgentClient(settings=settings, llm_client=llm_client)
    executor = RecoveryExecutor(
        sessionmaker=sessionmaker,
        razorpay_adapter=mock_razorpay_adapter,
        settings=settings,
    )
    orchestrator = RecoveryOrchestrator(
        sessionmaker=sessionmaker,
        razorpay_adapter=mock_razorpay_adapter,
        agent_client=agent_client,
        executor=executor,
        settings=settings,
    )
    return InteractiveRecoveryService(
        sessionmaker=sessionmaker,
        razorpay_adapter=mock_razorpay_adapter,
        orchestrator=orchestrator,
        settings=settings,
    )


@pytest.mark.asyncio
async def test_interactive_launch_creates_isolated_case(
    interactive_service: InteractiveRecoveryService,
):
    """Verify launch creates an isolated interactive case through recovery pipeline."""
    res = await interactive_service.launch_scenario(
        scenario_id="CS01", amount_paise=250000, reset_previous=True
    )
    assert res["status"] == "success"
    assert res["case_id"] == INTERACTIVE_CASE_ID
    assert res["amount_inr"] == 2500.0
    assert res["failure_category"] == "C1"
    assert res["payment_link_id"] == "plink_mock_live_cs01"
    assert res["payment_link_url"] == "https://rzp.io/rzp/mockCS01"

    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        case = await session.get(RecoveryCaseModel, INTERACTIVE_CASE_ID)
        assert case is not None
        assert case.amount == 250000
        assert case.failed_payment_id.startswith("pay_interactive_cs01")
        assert case.payment_link_id == "plink_mock_live_cs01"

        actual_audit_count = await session.scalar(
            select(func.count(AuditEventModel.id)).where(
                AuditEventModel.case_id == INTERACTIVE_CASE_ID
            )
        )
        assert res["audit_trail_count"] == actual_audit_count


@pytest.mark.asyncio
async def test_interactive_status_query(
    interactive_service: InteractiveRecoveryService,
):
    """Verify status endpoint returns current state, payment link, and audit trail."""
    await interactive_service.launch_scenario(
        scenario_id="CS01", amount_paise=250000, reset_previous=True
    )

    status_data = await interactive_service.get_status()
    assert status_data["exists"] is True
    assert status_data["case_id"] == INTERACTIVE_CASE_ID
    assert status_data["amount_inr"] == 2500.0
    assert status_data["payment_link_url"] == "https://rzp.io/rzp/mockCS01"

    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        actual_audit_count = await session.scalar(
            select(func.count(AuditEventModel.id)).where(
                AuditEventModel.case_id == INTERACTIVE_CASE_ID
            )
        )
    assert len(status_data["audit_trail"]) == actual_audit_count


@pytest.mark.asyncio
async def test_interactive_verify_unpaid_link(
    interactive_service: InteractiveRecoveryService,
    mock_razorpay_adapter: RazorpayAdapter,
):
    """Verify that an unpaid link returns verified=False and does not attribute revenue."""

    async def mock_unpaid_link(link_id: str) -> dict[str, Any]:
        return {
            "id": link_id,
            "status": "created",
            "payments": [],
        }

    mock_razorpay_adapter.get_payment_link = mock_unpaid_link  # type: ignore

    await interactive_service.launch_scenario(
        scenario_id="CS01", amount_paise=250000, reset_previous=True
    )

    ver_res = await interactive_service.verify_payment()
    assert ver_res["verified"] is False
    assert ver_res["payment_link_status"] == "created"

    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        case = await session.get(RecoveryCaseModel, INTERACTIVE_CASE_ID)
        assert case.state != CaseState.RECOVERED.value
        assert case.recovered_amount is None


@pytest.mark.asyncio
async def test_interactive_verify_captured_payment(
    interactive_service: InteractiveRecoveryService,
    mock_razorpay_adapter: RazorpayAdapter,
):
    """Verify captured payment transitions to RECOVERED and attributes revenue."""

    async def mock_paid_link(link_id: str) -> dict[str, Any]:
        return {
            "id": link_id,
            "status": "paid",
            "amount": 250000,
            "currency": "INR",
            "payments": [
                {
                    "id": "pay_mock_rec_cs01",
                    "payment_id": "pay_mock_rec_cs01",
                    "status": "captured",
                    "amount": 250000,
                    "currency": "INR",
                }
            ],
        }

    async def mock_captured_payment(payment_id: str) -> dict[str, Any]:
        return {
            "id": payment_id,
            "status": "captured",
            "amount": 250000,
            "currency": "INR",
            "payment_link_id": "plink_mock_live_cs01",
        }

    mock_razorpay_adapter.get_payment_link = mock_paid_link  # type: ignore
    mock_razorpay_adapter.get_payment = mock_captured_payment  # type: ignore

    await interactive_service.launch_scenario(
        scenario_id="CS01", amount_paise=250000, reset_previous=True
    )

    ver_res = await interactive_service.verify_payment()
    assert ver_res["verified"] is True
    assert ver_res["state"] == CaseState.RECOVERED.value
    assert ver_res["recovered_amount_inr"] == 2500.0
    assert ver_res["recovered_payment_id"] == "pay_mock_rec_cs01"

    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        case = await session.get(RecoveryCaseModel, INTERACTIVE_CASE_ID)
        assert case.state == CaseState.RECOVERED.value
        assert case.recovered_amount == 250000
        assert case.recovered_payment_id == "pay_mock_rec_cs01"

        actual_audit_count = await session.scalar(
            select(func.count(AuditEventModel.id)).where(
                AuditEventModel.case_id == INTERACTIVE_CASE_ID
            )
        )
        assert ver_res["audit_trail_count"] == actual_audit_count


@pytest.mark.asyncio
async def test_interactive_verify_duplicate_idempotency(
    interactive_service: InteractiveRecoveryService,
    mock_razorpay_adapter: RazorpayAdapter,
):
    """Verify repeated verify calls do not double-credit revenue or duplicate records."""

    async def mock_paid_link(link_id: str) -> dict[str, Any]:
        return {
            "id": link_id,
            "status": "paid",
            "amount": 250000,
            "currency": "INR",
            "payments": [
                {
                    "id": "pay_mock_rec_cs01",
                    "payment_id": "pay_mock_rec_cs01",
                    "status": "captured",
                    "amount": 250000,
                    "currency": "INR",
                }
            ],
        }

    async def mock_captured_payment(payment_id: str) -> dict[str, Any]:
        return {
            "id": payment_id,
            "status": "captured",
            "amount": 250000,
            "currency": "INR",
            "payment_link_id": "plink_mock_live_cs01",
        }

    mock_razorpay_adapter.get_payment_link = mock_paid_link  # type: ignore
    mock_razorpay_adapter.get_payment = mock_captured_payment  # type: ignore

    await interactive_service.launch_scenario(
        scenario_id="CS01", amount_paise=250000, reset_previous=True
    )

    # First verify
    res1 = await interactive_service.verify_payment()
    assert res1["verified"] is True

    # Second verify
    res2 = await interactive_service.verify_payment()
    assert res2["verified"] is True
    assert res2["already_recovered"] is True
    assert res2["recovered_amount_inr"] == 2500.0


@pytest.mark.asyncio
async def test_interactive_verify_amount_mismatch_escalates(
    interactive_service: InteractiveRecoveryService,
    mock_razorpay_adapter: RazorpayAdapter,
):
    """Verify that amount mismatch during verification escalates rather than attributing."""

    async def mock_tampered_link(link_id: str) -> dict[str, Any]:
        return {
            "id": link_id,
            "status": "paid",
            "amount": 100000,  # ₹1,000 instead of ₹2,500
            "currency": "INR",
            "payments": [
                {
                    "id": "pay_mock_tampered",
                    "payment_id": "pay_mock_tampered",
                    "status": "captured",
                    "amount": 100000,
                    "currency": "INR",
                }
            ],
        }

    async def mock_tampered_payment(payment_id: str) -> dict[str, Any]:
        return {
            "id": payment_id,
            "status": "captured",
            "amount": 100000,
            "currency": "INR",
            "payment_link_id": "plink_mock_live_cs01",
        }

    mock_razorpay_adapter.get_payment_link = mock_tampered_link  # type: ignore
    mock_razorpay_adapter.get_payment = mock_tampered_payment  # type: ignore

    await interactive_service.launch_scenario(
        scenario_id="CS01", amount_paise=250000, reset_previous=True
    )

    ver_res = await interactive_service.verify_payment()
    assert ver_res["verified"] is False
    assert ver_res["state"] == CaseState.ESCALATED.value

    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        case = await session.get(RecoveryCaseModel, INTERACTIVE_CASE_ID)
        assert case.state == CaseState.ESCALATED.value
        assert case.recovered_amount is None


@pytest.mark.asyncio
async def test_interactive_verify_currency_mismatch_escalates(
    interactive_service: InteractiveRecoveryService,
    mock_razorpay_adapter: RazorpayAdapter,
):
    """Verify that currency mismatch during verification escalates without attributing."""

    async def mock_usd_link(link_id: str) -> dict[str, Any]:
        return {
            "id": link_id,
            "status": "paid",
            "amount": 250000,
            "currency": "USD",  # USD instead of INR
            "payments": [
                {
                    "id": "pay_mock_usd",
                    "payment_id": "pay_mock_usd",
                    "status": "captured",
                    "amount": 250000,
                    "currency": "USD",
                }
            ],
        }

    async def mock_usd_payment(payment_id: str) -> dict[str, Any]:
        return {
            "id": payment_id,
            "status": "captured",
            "amount": 250000,
            "currency": "USD",
            "payment_link_id": "plink_mock_live_cs01",
        }

    mock_razorpay_adapter.get_payment_link = mock_usd_link  # type: ignore
    mock_razorpay_adapter.get_payment = mock_usd_payment  # type: ignore

    await interactive_service.launch_scenario(
        scenario_id="CS01", amount_paise=250000, reset_previous=True
    )

    ver_res = await interactive_service.verify_payment()
    assert ver_res["verified"] is False
    assert ver_res["state"] == CaseState.ESCALATED.value


@pytest.mark.asyncio
async def test_interactive_reset_isolation(
    interactive_service: InteractiveRecoveryService,
):
    """Verify reset removes only interactive case and leaves canonical cases intact."""
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        await seed_canonical_demonstration_batch(session=session, reset_first=True)

    await interactive_service.reset()

    async with sessionmaker() as session:
        interactive_case = await session.get(RecoveryCaseModel, INTERACTIVE_CASE_ID)
        assert interactive_case is None

        canonical_count = await session.scalar(
            select(func.count(RecoveryCaseModel.case_id)).where(
                RecoveryCaseModel.case_id.like("case_demo_%")
            )
        )
        assert canonical_count == 15


@pytest.mark.asyncio
async def test_interactive_repeated_launch_creates_fresh_run(
    interactive_service: InteractiveRecoveryService,
):
    """Verify repeated launches reset previous runs and create fresh, clean executions."""
    # First run
    res1 = await interactive_service.launch_scenario(
        scenario_id="CS01", amount_paise=250000, reset_previous=True
    )
    assert res1["status"] == "success"

    # Second run
    res2 = await interactive_service.launch_scenario(
        scenario_id="CS01", amount_paise=250000, reset_previous=True
    )
    assert res2["status"] == "success"

    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        count = await session.scalar(
            select(func.count(RecoveryCaseModel.case_id)).where(
                RecoveryCaseModel.case_id == INTERACTIVE_CASE_ID
            )
        )
        assert count == 1


@pytest.mark.asyncio
async def test_api_interactive_endpoints(
    interactive_service: InteractiveRecoveryService,
):
    """Verify REST API interactive routes via AsyncClient."""
    app.dependency_overrides[get_interactive_service] = lambda: interactive_service
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Launch
            res_launch = await client.post(
                "/cases/interactive/launch",
                json={"scenario_id": "CS01", "amount_paise": 250000, "reset_previous": True},
            )
            assert res_launch.status_code == 200
            data_launch = res_launch.json()
            assert data_launch["case_id"] == INTERACTIVE_CASE_ID
            assert data_launch["amount_inr"] == 2500.0

            # 2. Status
            res_status = await client.get("/cases/interactive/status")
            assert res_status.status_code == 200
            data_status = res_status.json()
            assert data_status["exists"] is True
            assert data_status["case_id"] == INTERACTIVE_CASE_ID

            # 3. Reset
            res_reset = await client.post("/cases/interactive/reset")
            assert res_reset.status_code == 200
            assert res_reset.json()["status"] == "success"

            # 4. Status after reset
            res_status_after = await client.get("/cases/interactive/status")
            assert res_status_after.status_code == 200
            assert res_status_after.json()["exists"] is False
    finally:
        app.dependency_overrides.pop(get_interactive_service, None)
