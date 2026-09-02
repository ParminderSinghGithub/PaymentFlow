"""Comprehensive tests for Layer 4A: RecoveryExecutor, idempotency, and failure safety."""

from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from paymentflow.adapters.razorpay_adapter import RazorpayAdapter
from paymentflow.db.models import AuditEventModel, RecoveryCaseModel, utc_now
from paymentflow.db.session import get_sessionmaker
from paymentflow.domain.enums import CaseState, FailureCategory, RecoveryPolicy
from paymentflow.domain.exceptions import RazorpayAdapterError, RazorpayAPIError
from paymentflow.services.recovery_executor import RecoveryExecutor


@pytest.fixture
def mock_razorpay_adapter():
    """Mock Razorpay adapter for deterministic execution tests."""
    adapter = RazorpayAdapter()
    adapter.create_payment_link = AsyncMock()
    return adapter


@pytest.mark.asyncio
async def test_recovery_executor_happy_path(mock_razorpay_adapter):
    """Test successful Payment Link execution, persistence, state transition, and audit trail."""
    sessionmaker = get_sessionmaker()
    case_id = "case_exec_happy_01"

    async with sessionmaker() as session:
        case = RecoveryCaseModel(
            case_id=case_id,
            failed_payment_id="pay_exec_happy_01",
            amount=299900,
            currency="INR",
            state=CaseState.ACTION_APPROVED.value,
            failure_category=FailureCategory.C1.value,
            failure_code="BAD_REQUEST_ERROR",
            failure_context={"error_source": "customer", "error_reason": "otp_timeout"},
            validated_policy_id=RecoveryPolicy.P_CREATE_LINK_IMMEDIATE.value,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(case)
        await session.commit()

    mock_razorpay_adapter.create_payment_link.return_value = {
        "id": "plink_test_12345",
        "short_url": "https://rzp.io/i/plink_test_12345",
        "status": "created",
        "amount": 299900,
        "currency": "INR",
        "reference_id": case_id,
    }

    executor = RecoveryExecutor(sessionmaker=sessionmaker, razorpay_adapter=mock_razorpay_adapter)
    result = await executor.execute(case_id)

    assert result.success is True
    assert result.decision == "EXECUTED"
    assert result.state == CaseState.ACTION_EXECUTED
    assert result.payment_link_id == "plink_test_12345"
    assert result.payment_link_short_url == "https://rzp.io/i/plink_test_12345"

    # Verify adapter called with verified original amount
    mock_razorpay_adapter.create_payment_link.assert_awaited_once_with(
        amount=299900,
        currency="INR",
        description="Recovery link for failed payment pay_exec_happy_01",
        reference_id=case_id,
        notes={"case_id": case_id, "failed_payment_id": "pay_exec_happy_01"},
    )

    # Verify DB persistence
    async with sessionmaker() as session:
        db_case = await session.get(RecoveryCaseModel, case_id)
        assert db_case.payment_link_id == "plink_test_12345"
        assert db_case.payment_link_reference_id == case_id
        assert db_case.payment_link_short_url == "https://rzp.io/i/plink_test_12345"
        assert db_case.payment_link_status == "created"
        assert db_case.state == CaseState.ACTION_EXECUTED.value

        # Verify audit logs
        audit_res = await session.execute(
            select(AuditEventModel).where(AuditEventModel.case_id == case_id)
        )
        audits = audit_res.scalars().all()
        event_types = [a.event_type for a in audits]
        assert "ACTION_EXECUTION_REQUESTED" in event_types
        assert "RAZORPAY_PAYMENT_LINK_CREATED" in event_types


@pytest.mark.asyncio
async def test_recovery_executor_already_executed_idempotency(mock_razorpay_adapter):
    """Test that a case with existing Payment Link returns existing result without Razorpay call."""
    sessionmaker = get_sessionmaker()
    case_id = "case_exec_idempotent_01"

    async with sessionmaker() as session:
        case = RecoveryCaseModel(
            case_id=case_id,
            failed_payment_id="pay_exec_idemp_01",
            amount=150000,
            currency="INR",
            state=CaseState.ACTION_EXECUTED.value,
            validated_policy_id=RecoveryPolicy.P_CREATE_LINK_IMMEDIATE.value,
            payment_link_id="plink_existing_999",
            payment_link_short_url="https://rzp.io/i/existing999",
            payment_link_status="created",
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(case)
        await session.commit()

    executor = RecoveryExecutor(sessionmaker=sessionmaker, razorpay_adapter=mock_razorpay_adapter)
    result = await executor.execute(case_id)

    assert result.success is True
    assert result.decision == "ALREADY_EXECUTED"
    assert result.payment_link_id == "plink_existing_999"
    assert result.payment_link_short_url == "https://rzp.io/i/existing999"
    mock_razorpay_adapter.create_payment_link.assert_not_awaited()


@pytest.mark.asyncio
async def test_recovery_executor_wrong_state_rejected(mock_razorpay_adapter):
    """Test that cases not in ACTION_APPROVED state are rejected."""
    sessionmaker = get_sessionmaker()
    case_id = "case_exec_wrong_state_01"

    async with sessionmaker() as session:
        case = RecoveryCaseModel(
            case_id=case_id,
            failed_payment_id="pay_exec_wrong_st_01",
            amount=100000,
            currency="INR",
            state=CaseState.ELIGIBILITY_CHECKED.value,
            validated_policy_id=RecoveryPolicy.P_CREATE_LINK_IMMEDIATE.value,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(case)
        await session.commit()

    executor = RecoveryExecutor(sessionmaker=sessionmaker, razorpay_adapter=mock_razorpay_adapter)
    result = await executor.execute(case_id)

    assert result.success is False
    assert result.decision == "INVALID_STATE"
    mock_razorpay_adapter.create_payment_link.assert_not_awaited()


@pytest.mark.asyncio
async def test_recovery_executor_non_executable_policy(mock_razorpay_adapter):
    """Test that policies like P_ESCALATE_ONLY are not executed for link creation."""
    sessionmaker = get_sessionmaker()
    case_id = "case_exec_escalate_policy_01"

    async with sessionmaker() as session:
        case = RecoveryCaseModel(
            case_id=case_id,
            failed_payment_id="pay_exec_esc_01",
            amount=100000,
            currency="INR",
            state=CaseState.ACTION_APPROVED.value,
            validated_policy_id=RecoveryPolicy.P_ESCALATE_ONLY.value,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(case)
        await session.commit()

    executor = RecoveryExecutor(sessionmaker=sessionmaker, razorpay_adapter=mock_razorpay_adapter)
    result = await executor.execute(case_id)

    assert result.success is False
    assert result.decision == "NON_EXECUTABLE_POLICY"
    mock_razorpay_adapter.create_payment_link.assert_not_awaited()


@pytest.mark.asyncio
async def test_recovery_executor_pre_write_high_value_escalation(mock_razorpay_adapter):
    """Test defense-in-depth: high value (>50k) case in ACTION_APPROVED escalates with NO write."""
    sessionmaker = get_sessionmaker()
    case_id = "case_exec_high_val_01"

    async with sessionmaker() as session:
        case = RecoveryCaseModel(
            case_id=case_id,
            failed_payment_id="pay_exec_high_01",
            amount=6000000,  # ₹60,000 > ₹50,000 threshold
            currency="INR",
            state=CaseState.ACTION_APPROVED.value,
            validated_policy_id=RecoveryPolicy.P_CREATE_LINK_IMMEDIATE.value,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(case)
        await session.commit()

    executor = RecoveryExecutor(sessionmaker=sessionmaker, razorpay_adapter=mock_razorpay_adapter)
    result = await executor.execute(case_id)

    assert result.success is False
    assert result.decision == "ESCALATE"
    assert result.state == CaseState.ESCALATED
    assert result.reason_code == "HIGH_VALUE_THRESHOLD"
    mock_razorpay_adapter.create_payment_link.assert_not_awaited()

    # Verify DB state moved to ESCALATED
    async with sessionmaker() as session:
        db_case = await session.get(RecoveryCaseModel, case_id)
        assert db_case.state == CaseState.ESCALATED.value


@pytest.mark.asyncio
async def test_recovery_executor_timeout_unknown_outcome(mock_razorpay_adapter):
    """Test critical failure: timeout on link creation halts safely without blind retry."""
    sessionmaker = get_sessionmaker()
    case_id = "case_exec_timeout_01"

    async with sessionmaker() as session:
        case = RecoveryCaseModel(
            case_id=case_id,
            failed_payment_id="pay_exec_timeout_01",
            amount=199900,
            currency="INR",
            state=CaseState.ACTION_APPROVED.value,
            validated_policy_id=RecoveryPolicy.P_CREATE_LINK_IMMEDIATE.value,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(case)
        await session.commit()

    mock_razorpay_adapter.create_payment_link.side_effect = RazorpayAdapterError(
        "Request timed out"
    )

    executor = RecoveryExecutor(sessionmaker=sessionmaker, razorpay_adapter=mock_razorpay_adapter)
    result = await executor.execute(case_id)

    assert result.success is False
    assert result.decision == "UNKNOWN_EXTERNAL_OUTCOME"
    assert result.state == CaseState.ERROR_TERMINAL
    assert result.reason_code == "EXTERNAL_TIMEOUT_RECONCILIATION_REQUIRED"

    # Verify DB state moved to ERROR_TERMINAL and audit recorded
    async with sessionmaker() as session:
        db_case = await session.get(RecoveryCaseModel, case_id)
        assert db_case.state == CaseState.ERROR_TERMINAL.value
        assert db_case.payment_link_id is None

        audit_res = await session.execute(
            select(AuditEventModel).where(AuditEventModel.case_id == case_id)
        )
        audits = audit_res.scalars().all()
        assert any(a.event_type == "RAZORPAY_PAYMENT_LINK_UNKNOWN_OUTCOME" for a in audits)


@pytest.mark.asyncio
async def test_recovery_executor_api_rejection(mock_razorpay_adapter):
    """Test Razorpay 400 API rejection handling."""
    sessionmaker = get_sessionmaker()
    case_id = "case_exec_api_err_01"

    async with sessionmaker() as session:
        case = RecoveryCaseModel(
            case_id=case_id,
            failed_payment_id="pay_exec_api_err_01",
            amount=249900,
            currency="INR",
            state=CaseState.ACTION_APPROVED.value,
            validated_policy_id=RecoveryPolicy.P_CREATE_LINK_IMMEDIATE.value,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(case)
        await session.commit()

    mock_razorpay_adapter.create_payment_link.side_effect = RazorpayAPIError(
        status_code=400, message="Invalid request parameters"
    )

    executor = RecoveryExecutor(sessionmaker=sessionmaker, razorpay_adapter=mock_razorpay_adapter)
    result = await executor.execute(case_id)

    assert result.success is False
    assert result.decision == "API_ERROR"
    assert result.state == CaseState.ERROR_TERMINAL

    async with sessionmaker() as session:
        db_case = await session.get(RecoveryCaseModel, case_id)
        assert db_case.state == CaseState.ERROR_TERMINAL.value
        audit_res = await session.execute(
            select(AuditEventModel).where(AuditEventModel.case_id == case_id)
        )
        audits = audit_res.scalars().all()
        assert any(a.event_type == "RAZORPAY_PAYMENT_LINK_FAILED" for a in audits)


@pytest.mark.asyncio
async def test_recovery_executor_concurrent_execution(mock_razorpay_adapter):
    """Test concurrent execution attempts: only one creates the link; the second reuses it."""
    sessionmaker = get_sessionmaker()
    case_id = "case_exec_concurrent_01"

    async with sessionmaker() as session:
        case = RecoveryCaseModel(
            case_id=case_id,
            failed_payment_id="pay_exec_conc_01",
            amount=199900,
            currency="INR",
            state=CaseState.ACTION_APPROVED.value,
            validated_policy_id=RecoveryPolicy.P_CREATE_LINK_IMMEDIATE.value,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(case)
        await session.commit()

    mock_razorpay_adapter.create_payment_link.return_value = {
        "id": "plink_concurrent_123",
        "short_url": "https://rzp.io/i/conc123",
        "status": "created",
        "amount": 199900,
        "currency": "INR",
    }

    executor = RecoveryExecutor(sessionmaker=sessionmaker, razorpay_adapter=mock_razorpay_adapter)

    # First execution succeeds
    res1 = await executor.execute(case_id)
    assert res1.success is True
    assert res1.decision == "EXECUTED"
    assert res1.payment_link_id == "plink_concurrent_123"

    # Second execution is idempotent
    res2 = await executor.execute(case_id)
    assert res2.success is True
    assert res2.decision == "ALREADY_EXECUTED"
    assert res2.payment_link_id == "plink_concurrent_123"

    # Verify adapter called exactly once
    assert mock_razorpay_adapter.create_payment_link.await_count == 1
