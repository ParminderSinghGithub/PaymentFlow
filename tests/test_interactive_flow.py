"""Comprehensive unit and integration tests for Phase 2B Interactive Recovery Flow."""

from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from paymentflow.adapters.razorpay_adapter import RazorpayAdapter
from paymentflow.db.models import AuditEventModel, RecoveryCaseModel
from paymentflow.db.session import get_sessionmaker
from paymentflow.domain.enums import CaseState
from paymentflow.eval.canonical_batch import seed_canonical_demonstration_batch
from paymentflow.main import app
from paymentflow.services.interactive_service import (
    INTERACTIVE_CASE_ID,
    InteractiveRecoveryService,
)


@pytest.fixture
def mock_razorpay_adapter():
    """Mock RazorpayAdapter returning realistic Test Mode responses."""
    adapter = AsyncMock(spec=RazorpayAdapter)
    adapter.create_payment_link.return_value = {
        "id": "plink_mock_live_cs01",
        "short_url": "https://rzp.io/rzp/mockCS01",
        "status": "created",
        "amount": 250000,
        "currency": "INR",
    }
    adapter.get_payment_link.return_value = {
        "id": "plink_mock_live_cs01",
        "short_url": "https://rzp.io/rzp/mockCS01",
        "status": "created",
        "amount": 250000,
        "currency": "INR",
        "payments": [],
    }
    adapter.get_payment.return_value = {
        "id": "pay_mock_rec_cs01",
        "status": "captured",
        "amount": 250000,
        "currency": "INR",
        "payment_link_id": "plink_mock_live_cs01",
    }
    return adapter


@pytest.mark.asyncio
async def test_interactive_launch_creates_isolated_case(mock_razorpay_adapter):
    """Verify launch creates an isolated interactive case through recovery pipeline."""
    service = InteractiveRecoveryService(razorpay_adapter=mock_razorpay_adapter)

    res = await service.launch_scenario(
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
async def test_interactive_status_query(mock_razorpay_adapter):
    """Verify status endpoint returns current state, payment link, and audit trail."""
    service = InteractiveRecoveryService(razorpay_adapter=mock_razorpay_adapter)
    await service.launch_scenario(scenario_id="CS01", amount_paise=250000, reset_previous=True)

    status_data = await service.get_status()
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
async def test_interactive_verify_unpaid_link(mock_razorpay_adapter):
    """Verify that an unpaid link returns verified=False and does not attribute revenue."""
    mock_razorpay_adapter.get_payment_link.return_value = {
        "id": "plink_mock_live_cs01",
        "status": "created",
        "payments": [],
    }
    service = InteractiveRecoveryService(razorpay_adapter=mock_razorpay_adapter)
    await service.launch_scenario(scenario_id="CS01", amount_paise=250000, reset_previous=True)

    ver_res = await service.verify_payment()
    assert ver_res["verified"] is False
    assert ver_res["payment_link_status"] == "created"

    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        case = await session.get(RecoveryCaseModel, INTERACTIVE_CASE_ID)
        assert case.state != CaseState.RECOVERED.value
        assert case.recovered_amount is None


@pytest.mark.asyncio
async def test_interactive_verify_captured_payment(mock_razorpay_adapter):
    """Verify captured payment transitions to RECOVERED and attributes revenue."""
    mock_razorpay_adapter.get_payment_link.return_value = {
        "id": "plink_mock_live_cs01",
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
    mock_razorpay_adapter.get_payment.return_value = {
        "id": "pay_mock_rec_cs01",
        "status": "captured",
        "amount": 250000,
        "currency": "INR",
        "payment_link_id": "plink_mock_live_cs01",
    }
    service = InteractiveRecoveryService(razorpay_adapter=mock_razorpay_adapter)
    await service.launch_scenario(scenario_id="CS01", amount_paise=250000, reset_previous=True)

    ver_res = await service.verify_payment()
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
async def test_interactive_verify_duplicate_idempotency(mock_razorpay_adapter):
    """Verify repeated verify calls do not double-credit revenue or duplicate records."""
    mock_razorpay_adapter.get_payment_link.return_value = {
        "id": "plink_mock_live_cs01",
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
    mock_razorpay_adapter.get_payment.return_value = {
        "id": "pay_mock_rec_cs01",
        "status": "captured",
        "amount": 250000,
        "currency": "INR",
        "payment_link_id": "plink_mock_live_cs01",
    }
    service = InteractiveRecoveryService(razorpay_adapter=mock_razorpay_adapter)
    await service.launch_scenario(scenario_id="CS01", amount_paise=250000, reset_previous=True)

    # First verify
    res1 = await service.verify_payment()
    assert res1["verified"] is True

    # Second verify
    res2 = await service.verify_payment()
    assert res2["verified"] is True
    assert res2["already_recovered"] is True
    assert res2["recovered_amount_inr"] == 2500.0


@pytest.mark.asyncio
async def test_interactive_verify_amount_mismatch_escalates(mock_razorpay_adapter):
    """Verify that amount mismatch during verification escalates rather than attributing."""
    mock_razorpay_adapter.get_payment_link.return_value = {
        "id": "plink_mock_live_cs01",
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
    mock_razorpay_adapter.get_payment.return_value = {
        "id": "pay_mock_tampered",
        "status": "captured",
        "amount": 100000,
        "currency": "INR",
        "payment_link_id": "plink_mock_live_cs01",
    }
    service = InteractiveRecoveryService(razorpay_adapter=mock_razorpay_adapter)
    await service.launch_scenario(scenario_id="CS01", amount_paise=250000, reset_previous=True)

    ver_res = await service.verify_payment()
    assert ver_res["verified"] is False
    assert ver_res["state"] == CaseState.ESCALATED.value

    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        case = await session.get(RecoveryCaseModel, INTERACTIVE_CASE_ID)
        assert case.state == CaseState.ESCALATED.value
        assert case.recovered_amount is None


@pytest.mark.asyncio
async def test_interactive_verify_currency_mismatch_escalates(mock_razorpay_adapter):
    """Verify that currency mismatch during verification escalates without attributing."""
    mock_razorpay_adapter.get_payment_link.return_value = {
        "id": "plink_mock_live_cs01",
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
    mock_razorpay_adapter.get_payment.return_value = {
        "id": "pay_mock_usd",
        "status": "captured",
        "amount": 250000,
        "currency": "USD",
        "payment_link_id": "plink_mock_live_cs01",
    }
    service = InteractiveRecoveryService(razorpay_adapter=mock_razorpay_adapter)
    await service.launch_scenario(scenario_id="CS01", amount_paise=250000, reset_previous=True)

    ver_res = await service.verify_payment()
    assert ver_res["verified"] is False
    assert ver_res["state"] == CaseState.ESCALATED.value


@pytest.mark.asyncio
async def test_interactive_reset_isolation():
    """Verify reset removes only interactive case and leaves canonical cases intact."""
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        await seed_canonical_demonstration_batch(session=session, reset_first=True)

    service = InteractiveRecoveryService()
    await service.reset()

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
async def test_interactive_repeated_launch_creates_fresh_run(mock_razorpay_adapter):
    """Verify repeated launches reset previous runs and create fresh, clean executions."""
    service = InteractiveRecoveryService(razorpay_adapter=mock_razorpay_adapter)

    # First run
    res1 = await service.launch_scenario(
        scenario_id="CS01", amount_paise=250000, reset_previous=True
    )
    assert res1["status"] == "success"

    # Second run
    res2 = await service.launch_scenario(
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
async def test_api_interactive_endpoints():
    """Verify REST API interactive routes via AsyncClient."""
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
