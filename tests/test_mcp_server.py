"""Tests for MCP server, typed read tools, and bounded action-request boundary."""

import pytest
from sqlalchemy import select

from paymentflow.db.models import AuditEventModel, RecoveryCaseModel, utc_now
from paymentflow.db.session import get_sessionmaker
from paymentflow.domain.enums import CaseState, EligibilityStatus, FailureCategory
from paymentflow.mcp.client import RecoveryAgentClient
from paymentflow.mcp.server import (
    get_allowed_recovery_policies,
    get_payment_context,
    get_recovery_case,
    get_recovery_status,
    request_recovery_action,
)


@pytest.mark.asyncio
async def test_mcp_get_allowed_recovery_policies():
    """Verify get_allowed_recovery_policies returns exactly the four frozen policies."""
    policies = await get_allowed_recovery_policies()
    policy_ids = [p["policy_id"] for p in policies]

    assert len(policies) == 4
    assert "P_CREATE_LINK_IMMEDIATE" in policy_ids
    assert "P_CREATE_LINK_DELAYED" in policy_ids
    assert "P_ESCALATE_ONLY" in policy_ids
    assert "P_NO_ACTION" in policy_ids


@pytest.mark.asyncio
async def test_mcp_read_tools():
    """Verify MCP read tools retrieve sanitized context and status from DB."""
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        case = RecoveryCaseModel(
            case_id="case_mcp_read_01",
            failed_payment_id="pay_mcp_read_01",
            amount=499900,
            currency="INR",
            state=CaseState.ELIGIBILITY_CHECKED.value,
            failure_category=FailureCategory.C1.value,
            failure_code="CARD_DECLINED",
            failure_description="Card declined by issuer bank",
            failure_context={"error_source": "bank", "error_reason": "card_declined"},
            eligibility_status=EligibilityStatus.ELIGIBLE.value,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(case)
        await session.commit()

    # 1. Test get_payment_context
    ctx = await get_payment_context("pay_mcp_read_01")
    assert ctx["payment_id"] == "pay_mcp_read_01"
    assert ctx["amount_paise"] == 499900
    assert ctx["amount_inr"] == "₹4999.00"
    assert ctx["failure_code"] == "CARD_DECLINED"

    # 2. Test get_recovery_case
    c_info = await get_recovery_case("case_mcp_read_01")
    assert c_info["case_id"] == "case_mcp_read_01"
    assert c_info["eligibility_status"] == "ELIGIBLE"

    # 3. Test get_recovery_status
    status = await get_recovery_status("case_mcp_read_01")
    assert status["case_id"] == "case_mcp_read_01"
    assert status["state"] == CaseState.ELIGIBILITY_CHECKED.value
    assert status["is_eligible"] is True
    assert status["is_terminal"] is False


@pytest.mark.asyncio
async def test_mcp_read_tools_errors_and_missing_inputs():
    """Verify MCP read tools handle empty or non-existent inputs safely."""
    # Empty inputs
    assert "error" in await get_payment_context("")
    assert "error" in await get_recovery_case("")
    assert "error" in await get_recovery_status("")

    # Not found inputs
    assert "not found" in (await get_payment_context("pay_nonexistent_999"))["error"]
    assert "not found" in (await get_recovery_case("case_nonexistent_999"))["error"]
    assert "not found" in (await get_recovery_status("case_nonexistent_999"))["error"]


@pytest.mark.asyncio
async def test_mcp_request_recovery_action_approved():
    """Verify valid action proposal passes guardrails, updates DB, and records audit trail."""
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        case = RecoveryCaseModel(
            case_id="case_mcp_action_01",
            failed_payment_id="pay_mcp_action_01",
            amount=150000,
            currency="INR",
            state=CaseState.ELIGIBILITY_CHECKED.value,
            failure_category=FailureCategory.C1.value,
            failure_code="AUTH_FAILED",
            eligibility_status=EligibilityStatus.ELIGIBLE.value,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(case)
        await session.commit()

    # Request immediate link action
    result = await request_recovery_action(
        case_id="case_mcp_action_01",
        proposed_policy="P_CREATE_LINK_IMMEDIATE",
        proposed_amount=150000,
        proposed_currency="INR",
        explanation="Customer OTP expired; issue immediate recovery link.",
    )

    assert result["authorized"] is True
    assert result["decision"] == "APPROVE"
    assert result["effective_policy"] == "P_CREATE_LINK_IMMEDIATE"
    assert result["case_state"] == CaseState.ACTION_APPROVED.value

    # Verify DB persistence and Audit Trail
    async with sessionmaker() as session:
        reloaded = await session.get(RecoveryCaseModel, "case_mcp_action_01")
        assert reloaded.state == CaseState.ACTION_APPROVED.value
        assert reloaded.validated_policy_id == "P_CREATE_LINK_IMMEDIATE"

        audit_res = await session.execute(
            select(AuditEventModel).where(AuditEventModel.case_id == "case_mcp_action_01")
        )
        audits = audit_res.scalars().all()
        assert any(a.event_type == "POLICY_GUARDRAIL_VALIDATED" for a in audits)


@pytest.mark.asyncio
async def test_mcp_request_action_tampered_amount_rejected():
    """Verify MCP rejects mutated amounts and prevents unauthorized actions."""
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        case = RecoveryCaseModel(
            case_id="case_mcp_tamper_01",
            failed_payment_id="pay_mcp_tamper_01",
            amount=200000,
            currency="INR",
            state=CaseState.ELIGIBILITY_CHECKED.value,
            failure_category=FailureCategory.C1.value,
            failure_code="AUTH_FAILED",
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(case)
        await session.commit()

    # Submit tampered amount
    result = await request_recovery_action(
        case_id="case_mcp_tamper_01",
        proposed_policy="P_CREATE_LINK_IMMEDIATE",
        proposed_amount=50000,  # Altered amount!
        proposed_currency="INR",
    )

    assert result["authorized"] is False
    assert result["decision"] == "REJECT"
    assert result["reason_code"] == "AMOUNT_MUTATION_FORBIDDEN"
    assert result["effective_policy"] == "P_NO_ACTION"


@pytest.mark.asyncio
async def test_mcp_request_action_high_value_escalates():
    """Verify MCP escalates > ₹50,000 cases to P_ESCALATE_ONLY."""
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        case = RecoveryCaseModel(
            case_id="case_mcp_high_01",
            failed_payment_id="pay_mcp_high_01",
            amount=80_000_00,  # ₹80,000
            currency="INR",
            state=CaseState.ELIGIBILITY_CHECKED.value,
            failure_category=FailureCategory.C1.value,
            failure_code="AUTH_FAILED",
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(case)
        await session.commit()

    result = await request_recovery_action(
        case_id="case_mcp_high_01",
        proposed_policy="P_CREATE_LINK_IMMEDIATE",
        proposed_amount=80_000_00,
        proposed_currency="INR",
    )

    assert result["authorized"] is False
    assert result["decision"] == "ESCALATE"
    assert result["effective_policy"] == "P_ESCALATE_ONLY"
    assert result["case_state"] == CaseState.ESCALATED.value


@pytest.mark.asyncio
async def test_mcp_request_action_validation_errors():
    """Verify request_recovery_action handles empty, not found, or terminal case states."""
    # Empty case_id
    assert "required" in (await request_recovery_action("", "P_CREATE_LINK_IMMEDIATE"))["error"]

    # Non-existent case_id
    assert (
        "not found"
        in (await request_recovery_action("case_nonexistent", "P_CREATE_LINK_IMMEDIATE"))["error"]
    )

    # Terminal case state
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        case = RecoveryCaseModel(
            case_id="case_mcp_terminal_01",
            failed_payment_id="pay_mcp_term_01",
            amount=100000,
            currency="INR",
            state=CaseState.RECOVERED.value,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(case)
        await session.commit()

    res = await request_recovery_action("case_mcp_terminal_01", "P_CREATE_LINK_IMMEDIATE")
    assert res["authorized"] is False
    assert "terminal" in res["error"]


@pytest.mark.asyncio
async def test_mcp_agent_client_terminal_and_error_handling():
    """Verify RecoveryAgentClient handles terminal or missing cases cleanly."""
    agent = RecoveryAgentClient()

    # Missing case
    res_missing = await agent.run_recovery_triage("case_nonexistent_client")
    assert res_missing["success"] is False
    assert "not found" in res_missing["error"]

    # Terminal case
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        case = RecoveryCaseModel(
            case_id="case_client_terminal",
            failed_payment_id="pay_client_term",
            amount=100000,
            currency="INR",
            state=CaseState.TERMINAL_NO_ACTION.value,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(case)
        await session.commit()

    res_terminal = await agent.run_recovery_triage("case_client_terminal")
    assert res_terminal["success"] is False
    assert "terminal" in res_terminal["error"]
