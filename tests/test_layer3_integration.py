"""End-to-end integration tests for Layer 3: Agent Reasoning, Guardrails & MCP."""

import json

import httpx
import pytest
from sqlalchemy import delete, select

from paymentflow.adapters.llm_adapter import LLMClient
from paymentflow.config import Settings
from paymentflow.db.models import AuditEventModel, RecoveryCaseModel, utc_now
from paymentflow.db.session import get_sessionmaker
from paymentflow.domain.enums import CaseState, EligibilityStatus, FailureCategory
from paymentflow.mcp.client import RecoveryAgentClient


@pytest.fixture
def mock_gemini_client() -> httpx.AsyncClient:
    """Mock Gemini API returning valid immediate recovery proposal."""

    def handler(request: httpx.Request) -> httpx.Response:
        gemini_response = {
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
                                        "explanation": "Customer auth failed; link recommended.",
                                    }
                                )
                            }
                        ],
                        "role": "model",
                    }
                }
            ]
        }
        return httpx.Response(200, json=gemini_response)

    transport = httpx.MockTransport(handler)
    return httpx.AsyncClient(transport=transport)


@pytest.mark.asyncio
async def test_layer3_full_pipeline_success(
    test_settings: Settings,
    mock_gemini_client: httpx.AsyncClient,
):
    """End-to-end flow: Ingested Case -> Triage -> MCP Read -> LLM Proposal -> Guardrail Approve."""
    settings = test_settings.model_copy(update={"llm_api_key": "valid_mock_key"})
    sessionmaker = get_sessionmaker()
    case_id = "case_l3_e2e_01"

    try:
        # 1. Setup case in ELIGIBILITY_CHECKED
        async with sessionmaker() as session:
            case = RecoveryCaseModel(
                case_id=case_id,
                failed_payment_id="pay_l3_e2e_01",
                amount=299900,
                currency="INR",
                state=CaseState.ELIGIBILITY_CHECKED.value,
                payment_method="card",
                failure_category=FailureCategory.C1.value,
                failure_code="BAD_REQUEST_ERROR",
                failure_description="Card authentication timed out",
                failure_context={"error_source": "customer", "error_reason": "otp_timeout"},
                eligibility_status=EligibilityStatus.ELIGIBLE.value,
                eligibility_reason="ELIGIBLE",
                created_at=utc_now(),
                updated_at=utc_now(),
            )
            session.add(case)
            await session.commit()

        # 2. Run Layer 3 Agent Client
        llm = LLMClient(settings=settings, http_client=mock_gemini_client)
        agent = RecoveryAgentClient(settings=settings, llm_client=llm)

        result = await agent.run_recovery_triage(case_id)

        assert result["success"] is True
        assert result["llm_metadata"]["is_fallback"] is False
        assert result["mcp_action_result"]["authorized"] is True
        assert result["mcp_action_result"]["decision"] == "APPROVE"
        assert result["mcp_action_result"]["effective_policy"] == "P_CREATE_LINK_IMMEDIATE"

        # 3. Verify Database Updates
        async with sessionmaker() as session:
            reloaded = await session.get(RecoveryCaseModel, case_id)
            assert reloaded is not None
            assert reloaded.state == CaseState.ACTION_APPROVED.value
            assert reloaded.validated_policy_id == "P_CREATE_LINK_IMMEDIATE"
            assert reloaded.ai_policy_id == "P_CREATE_LINK_IMMEDIATE"

            # 4. Verify Audit Trail
            audit_res = await session.execute(
                select(AuditEventModel).where(AuditEventModel.case_id == case_id)
            )
            audits = audit_res.scalars().all()
            assert any(a.event_type == "POLICY_GUARDRAIL_VALIDATED" for a in audits)
    finally:
        async with sessionmaker() as session:
            await session.execute(delete(AuditEventModel).where(AuditEventModel.case_id == case_id))
            await session.execute(delete(RecoveryCaseModel).where(RecoveryCaseModel.case_id == case_id))
            await session.commit()


@pytest.mark.asyncio
async def test_layer3_pipeline_high_value_escalation(
    test_settings: Settings,
    mock_gemini_client: httpx.AsyncClient,
):
    """Verify high-value case (>₹50k) is escalated by guardrail engine despite LLM link proposal."""
    settings = test_settings.model_copy(update={"llm_api_key": "valid_mock_key"})
    sessionmaker = get_sessionmaker()
    case_id = "case_l3_high_01"

    try:
        async with sessionmaker() as session:
            case = RecoveryCaseModel(
                case_id=case_id,
                failed_payment_id="pay_l3_high_01",
                amount=75_000_00,  # ₹75,000
                currency="INR",
                state=CaseState.ELIGIBILITY_CHECKED.value,
                payment_method="card",
                failure_category=FailureCategory.C1.value,
                failure_code="BAD_REQUEST_ERROR",
                failure_description="Authentication failed",
                created_at=utc_now(),
                updated_at=utc_now(),
            )
            session.add(case)
            await session.commit()

        llm = LLMClient(settings=settings, http_client=mock_gemini_client)
        agent = RecoveryAgentClient(settings=settings, llm_client=llm)

        result = await agent.run_recovery_triage(case_id)

        assert result["success"] is True
        assert result["mcp_action_result"]["authorized"] is False
        assert result["mcp_action_result"]["decision"] == "ESCALATE"
        assert result["mcp_action_result"]["effective_policy"] == "P_ESCALATE_ONLY"
        assert result["mcp_action_result"]["case_state"] == CaseState.ESCALATED.value

        # Verify DB persistence
        async with sessionmaker() as session:
            reloaded = await session.get(RecoveryCaseModel, case_id)
            assert reloaded.state == CaseState.ESCALATED.value
            assert reloaded.validated_policy_id == "P_ESCALATE_ONLY"
    finally:
        async with sessionmaker() as session:
            await session.execute(delete(AuditEventModel).where(AuditEventModel.case_id == case_id))
            await session.execute(delete(RecoveryCaseModel).where(RecoveryCaseModel.case_id == case_id))
            await session.commit()


@pytest.mark.asyncio
async def test_layer3_pipeline_llm_failure_safe_fallback(test_settings: Settings):
    """Verify LLM timeout / network failure gracefully defaults to safe deterministic fallback."""
    settings = test_settings.model_copy(update={"llm_api_key": "valid_mock_key"})
    sessionmaker = get_sessionmaker()
    case_id = "case_l3_fallback_01"

    try:
        async with sessionmaker() as session:
            case = RecoveryCaseModel(
                case_id=case_id,
                failed_payment_id="pay_l3_fallback_01",
                amount=100000,
                currency="INR",
                state=CaseState.ELIGIBILITY_CHECKED.value,
                payment_method="upi",
                failure_category=FailureCategory.C1.value,
                failure_code="BAD_REQUEST_ERROR",
                created_at=utc_now(),
                updated_at=utc_now(),
            )
            session.add(case)
            await session.commit()

        def timeout_handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("Gemini timeout")

        transport = httpx.MockTransport(timeout_handler)
        async with httpx.AsyncClient(transport=transport) as http_client:
            llm = LLMClient(settings=settings, http_client=http_client)
            agent = RecoveryAgentClient(settings=settings, llm_client=llm)

            result = await agent.run_recovery_triage(case_id)

            assert result["success"] is True
            assert result["llm_metadata"]["is_fallback"] is True
            assert result["llm_proposal"]["policy_id"] == "P_NO_ACTION"
            assert result["mcp_action_result"]["effective_policy"] == "P_NO_ACTION"
            assert result["mcp_action_result"]["case_state"] in {
                CaseState.ACTION_APPROVED.value,
                CaseState.TERMINAL_NO_ACTION.value,
            }
    finally:
        async with sessionmaker() as session:
            await session.execute(delete(AuditEventModel).where(AuditEventModel.case_id == case_id))
            await session.execute(delete(RecoveryCaseModel).where(RecoveryCaseModel.case_id == case_id))
            await session.commit()
