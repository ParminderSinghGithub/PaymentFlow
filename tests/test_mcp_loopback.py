"""Focused loopback integration tests verifying MCP client-server protocol execution."""

import pytest
from sqlalchemy import select

from paymentflow.db.models import AuditEventModel, RecoveryCaseModel, utc_now
from paymentflow.db.session import get_sessionmaker
from paymentflow.domain.enums import CaseState, EligibilityStatus, FailureCategory
from paymentflow.mcp.client import RecoveryAgentClient
from paymentflow.mcp.server import mcp_server


@pytest.mark.asyncio
async def test_mcp_client_tool_discovery():
    """Verify RecoveryAgentClient dynamically discovers all registered tools via MCP list_tools."""
    client = RecoveryAgentClient(server=mcp_server)
    tools = await client.discover_tools()
    tool_names = [t["name"] for t in tools]

    assert len(tools) == 5
    assert "get_allowed_recovery_policies" in tool_names
    assert "get_payment_context" in tool_names
    assert "get_recovery_case" in tool_names
    assert "get_recovery_status" in tool_names
    assert "request_recovery_action" in tool_names

    # Verify input schemas are exposed
    for tool in tools:
        assert "description" in tool
        assert "input_schema" in tool


@pytest.mark.asyncio
async def test_mcp_loopback_read_tool_protocol_call():
    """Verify MCP client executes get_payment_context tool via MCP call_tool protocol."""
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        case = RecoveryCaseModel(
            case_id="case_mcp_loop_01",
            failed_payment_id="pay_mcp_loop_01",
            amount=349900,
            currency="INR",
            state=CaseState.ELIGIBILITY_CHECKED.value,
            failure_category=FailureCategory.C1.value,
            failure_code="BAD_REQUEST_ERROR",
            failure_description="Card authentication failed",
            failure_context={"error_source": "customer", "error_reason": "otp_timeout"},
            eligibility_status=EligibilityStatus.ELIGIBLE.value,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(case)
        await session.commit()

    client = RecoveryAgentClient(server=mcp_server)
    result = await client.call_tool("get_payment_context", {"payment_id": "pay_mcp_loop_01"})

    assert isinstance(result, dict)
    assert result["payment_id"] == "pay_mcp_loop_01"
    assert result["amount_paise"] == 349900
    assert result["amount_inr"] == "₹3499.00"
    assert result["failure_code"] == "BAD_REQUEST_ERROR"


@pytest.mark.asyncio
async def test_mcp_loopback_action_tool_guardrail_bound():
    """Verify MCP client invokes request_recovery_action over MCP protocol into guardrails."""
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        case = RecoveryCaseModel(
            case_id="case_mcp_loop_action_01",
            failed_payment_id="pay_mcp_loop_action_01",
            amount=199900,
            currency="INR",
            state=CaseState.ELIGIBILITY_CHECKED.value,
            failure_category=FailureCategory.C1.value,
            failure_code="PAYMENT_AUTHENTICATION_ERROR",
            eligibility_status=EligibilityStatus.ELIGIBLE.value,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(case)
        await session.commit()

    client = RecoveryAgentClient(server=mcp_server)
    result = await client.call_tool(
        "request_recovery_action",
        {
            "case_id": "case_mcp_loop_action_01",
            "proposed_policy": "P_CREATE_LINK_IMMEDIATE",
            "proposed_amount": 199900,
            "proposed_currency": "INR",
            "explanation": "Valid loopback test proposal.",
        },
    )

    assert isinstance(result, dict)
    assert result["authorized"] is True
    assert result["decision"] == "APPROVE"
    assert result["effective_policy"] == "P_CREATE_LINK_IMMEDIATE"
    assert result["case_state"] == CaseState.ACTION_APPROVED.value

    # Verify audit event in DB
    async with sessionmaker() as session:
        audit_res = await session.execute(
            select(AuditEventModel).where(AuditEventModel.case_id == "case_mcp_loop_action_01")
        )
        audits = audit_res.scalars().all()
        assert any(a.event_type == "POLICY_GUARDRAIL_VALIDATED" for a in audits)


@pytest.mark.asyncio
async def test_mcp_loopback_tampered_amount_rejection():
    """Verify MCP protocol call attempting amount mutation is rejected by PolicyGuardrailEngine."""
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        case = RecoveryCaseModel(
            case_id="case_mcp_loop_tamper_01",
            failed_payment_id="pay_mcp_loop_tamper_01",
            amount=500000,
            currency="INR",
            state=CaseState.ELIGIBILITY_CHECKED.value,
            failure_category=FailureCategory.C1.value,
            failure_code="AUTH_FAILED",
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(case)
        await session.commit()

    client = RecoveryAgentClient(server=mcp_server)
    result = await client.call_tool(
        "request_recovery_action",
        {
            "case_id": "case_mcp_loop_tamper_01",
            "proposed_policy": "P_CREATE_LINK_IMMEDIATE",
            "proposed_amount": 10000,  # Tampered
            "proposed_currency": "INR",
        },
    )

    assert result["authorized"] is False
    assert result["decision"] == "REJECT"
    assert result["reason_code"] == "AMOUNT_MUTATION_FORBIDDEN"
    assert result["effective_policy"] == "P_NO_ACTION"
