"""Comprehensive unit and regression tests for Layer 5D LLM Provider and MCP Boundary."""

import json

import httpx
import pytest

from paymentflow.config import Settings
from paymentflow.domain.enums import FailureCategory, RecoveryPolicy
from paymentflow.eval.dataset import load_evaluation_dataset
from paymentflow.eval.llm_provider import LLMAgentDecisionProvider
from paymentflow.eval.models import AgentDecision
from paymentflow.mcp.client import RecoveryAgentClient
from paymentflow.mcp.eval_server import (
    clear_eval_contexts,
    eval_mcp_server,
    register_eval_context,
)

# =============================================================================
# 1. Ground-Truth Leakage & Serialization Tests
# =============================================================================


def test_llm_input_strictly_zero_ground_truth_leakage():
    """Verify serialized prompt context contains NO hidden ground truth or probabilities."""
    cases = load_evaluation_dataset()
    case = cases[0]
    dc = case.get_decision_context()

    provider = LLMAgentDecisionProvider()
    serialized = provider.serialize_decision_context(dc)
    prompt = provider._build_user_prompt(dc)

    # 1. Dictionary checks
    forbidden_keys = [
        "ground_truth",
        "p_recovery_immediate_link",
        "p_recovery_delayed_link",
        "p_recovery_no_action",
        "p_recovery_escalate",
        "latent_intent",
        "customer_response_probability",
        "future_outcome",
        "baseline_outcome",
    ]
    for key in forbidden_keys:
        assert key not in serialized, f"Ground-truth key '{key}' leaked in serialized context!"
        assert key not in prompt, f"Ground-truth key '{key}' leaked in LLM prompt!"

    # 2. Assert values in ground_truth are not in prompt text
    assert str(case.ground_truth.p_recovery_immediate_link) not in prompt
    assert str(case.ground_truth.p_recovery_delayed_link) not in prompt


# =============================================================================
# 2. LLM Provider Decision & Structured Output Tests
# =============================================================================


def test_llm_provider_unconfigured_credentials_safe_fallback():
    """Verify provider safely falls back when credentials are unconfigured or placeholder."""
    cases = load_evaluation_dataset()
    dc = cases[0].get_decision_context()

    settings = Settings(llm_api_key="placeholder_llm_api_key")
    provider = LLMAgentDecisionProvider(settings=settings)

    decision = provider.decide(dc)
    assert isinstance(decision, AgentDecision)
    assert decision.case_id == dc.case_id
    assert decision.proposed_policy_id == RecoveryPolicy.P_NO_ACTION
    assert decision.confidence_score == 0.0
    assert "not configured" in decision.reasoning
    assert provider.telemetry.fallback_count == 1
    assert provider.telemetry.call_count == 1


def test_llm_provider_unconfigured_high_value_escalation_fallback():
    """Verify unconfigured credentials safely escalate high-value cases rather than closing."""
    cases = load_evaluation_dataset()
    hv_case = next(c for c in cases if c.decision_context.amount > 5_000_000)
    dc = hv_case.get_decision_context()

    settings = Settings(llm_api_key="placeholder_llm_api_key")
    provider = LLMAgentDecisionProvider(settings=settings)

    decision = provider.decide(dc)
    assert decision.proposed_policy_id == RecoveryPolicy.P_ESCALATE_ONLY
    assert decision.confidence_score == 0.0
    assert "high-value" in decision.reasoning


def test_llm_provider_gemini_format_success():
    """Verify provider parses standard Gemini REST response into valid AgentDecision."""
    cases = load_evaluation_dataset()
    dc = cases[0].get_decision_context()

    mock_response_content = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": json.dumps({
                                "case_id": dc.case_id,
                                "failure_category": "C1",
                                "proposed_policy_id": "P_CREATE_LINK_DELAYED",
                                "reasoning": "Gateway transient issue; recommend delayed recovery.",
                                "confidence_score": 0.92,
                                "proposed_amount": dc.amount,
                                "proposed_currency": dc.currency,
                            })
                        }
                    ]
                }
            }
        ],
        "usageMetadata": {
            "promptTokenCount": 180,
            "candidatesTokenCount": 45,
        },
    }

    def mock_transport_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=mock_response_content, request=request)

    mock_client = httpx.Client(transport=httpx.MockTransport(mock_transport_handler))
    provider = LLMAgentDecisionProvider(
        api_key="valid_test_key",
        http_client=mock_client,
    )

    decision = provider.decide(dc)
    assert decision.case_id == dc.case_id
    assert decision.failure_category == FailureCategory.C1
    assert decision.proposed_policy_id == RecoveryPolicy.P_CREATE_LINK_DELAYED
    assert decision.confidence_score == 0.92
    assert provider.telemetry.call_count == 1
    assert provider.telemetry.fallback_count == 0
    assert provider.telemetry.prompt_tokens == 180
    assert provider.telemetry.completion_tokens == 45
    assert provider.telemetry.total_tokens == 225


def test_llm_provider_openai_format_success():
    """Verify provider parses standard OpenAI chat completions response into valid AgentDecision."""
    cases = load_evaluation_dataset()
    dc = cases[0].get_decision_context()

    mock_response_content = {
        "choices": [
            {
                "message": {
                    "content": json.dumps({
                        "case_id": dc.case_id,
                        "failure_category": "C2",
                        "proposed_policy_id": "P_CREATE_LINK_IMMEDIATE",
                        "reasoning": "User dropoff; immediate link recommended.",
                        "confidence_score": 0.95,
                    })
                }
            }
        ],
        "usage": {
            "prompt_tokens": 150,
            "completion_tokens": 40,
        },
    }

    def mock_transport_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=mock_response_content, request=request)

    mock_client = httpx.Client(transport=httpx.MockTransport(mock_transport_handler))
    provider = LLMAgentDecisionProvider(
        api_key="valid_openai_key",
        provider_type="openai",
        http_client=mock_client,
    )

    decision = provider.decide(dc)
    assert decision.failure_category == FailureCategory.C2
    assert decision.proposed_policy_id == RecoveryPolicy.P_CREATE_LINK_IMMEDIATE
    assert decision.proposed_amount == dc.amount
    assert decision.proposed_currency == dc.currency
    assert provider.telemetry.total_tokens == 190


# =============================================================================
# 3. LLM Failure Modes & Safe Fallback Tests
# =============================================================================


def test_llm_provider_timeout_fallback():
    """Verify HTTP timeout produces deterministic safe fallback."""
    cases = load_evaluation_dataset()
    dc = cases[0].get_decision_context()

    def timeout_transport(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("Read timed out", request=request)

    mock_client = httpx.Client(transport=httpx.MockTransport(timeout_transport))
    provider = LLMAgentDecisionProvider(
        api_key="valid_test_key",
        http_client=mock_client,
    )

    decision = provider.decide(dc)
    assert decision.proposed_policy_id == RecoveryPolicy.P_NO_ACTION
    assert provider.telemetry.fallback_count == 1
    assert "TimeoutException" in provider.telemetry.errors[0]


def test_llm_provider_http_500_fallback():
    """Verify HTTP 500 error produces deterministic safe fallback."""
    cases = load_evaluation_dataset()
    dc = cases[0].get_decision_context()

    def error_transport(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="Internal Server Error", request=request)

    mock_client = httpx.Client(transport=httpx.MockTransport(error_transport))
    provider = LLMAgentDecisionProvider(
        api_key="valid_test_key",
        http_client=mock_client,
    )

    decision = provider.decide(dc)
    assert decision.proposed_policy_id == RecoveryPolicy.P_NO_ACTION
    assert provider.telemetry.fallback_count == 1
    assert "HTTP 500" in provider.telemetry.errors[0]


def test_llm_provider_malformed_json_fallback():
    """Verify unparseable non-JSON LLM output produces deterministic safe fallback."""
    cases = load_evaluation_dataset()
    dc = cases[0].get_decision_context()

    mock_response = {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": "I suggest we create a payment link immediately."}]
                }
            }
        ]
    }

    def json_error_transport(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=mock_response, request=request)

    mock_client = httpx.Client(transport=httpx.MockTransport(json_error_transport))
    provider = LLMAgentDecisionProvider(
        api_key="valid_test_key",
        http_client=mock_client,
    )

    decision = provider.decide(dc)
    assert decision.proposed_policy_id == RecoveryPolicy.P_NO_ACTION
    assert provider.telemetry.fallback_count == 1
    assert "SchemaValidationError" in provider.telemetry.errors[0]


def test_llm_provider_invalid_policy_id_fallback():
    """Verify unallowed policy ID in LLM JSON output produces deterministic safe fallback."""
    cases = load_evaluation_dataset()
    dc = cases[0].get_decision_context()

    mock_response = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": json.dumps({
                                "case_id": dc.case_id,
                                "failure_category": "C1",
                                "proposed_policy_id": "P_UNAUTHORIZED_HACK",
                                "reasoning": "Invalid policy test.",
                                "confidence_score": 0.9,
                            })
                        }
                    ]
                }
            }
        ]
    }

    def invalid_policy_transport(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=mock_response, request=request)

    mock_client = httpx.Client(transport=httpx.MockTransport(invalid_policy_transport))
    provider = LLMAgentDecisionProvider(
        api_key="valid_test_key",
        http_client=mock_client,
    )

    decision = provider.decide(dc)
    assert decision.proposed_policy_id == RecoveryPolicy.P_NO_ACTION
    assert provider.telemetry.fallback_count == 1


# =============================================================================
# 4. MCP Server & Tool Independent Tests (Offline)
# =============================================================================


@pytest.mark.asyncio
async def test_eval_mcp_server_allowed_policies_tool():
    """Verify get_allowed_recovery_policies tool returns all 4 policies."""
    client = RecoveryAgentClient(server=eval_mcp_server)
    policies = await client.call_tool("get_allowed_recovery_policies")

    assert isinstance(policies, list)
    assert len(policies) == 4
    policy_ids = [p["policy_id"] for p in policies]
    assert "P_CREATE_LINK_IMMEDIATE" in policy_ids
    assert "P_CREATE_LINK_DELAYED" in policy_ids
    assert "P_ESCALATE_ONLY" in policy_ids
    assert "P_NO_ACTION" in policy_ids


@pytest.mark.asyncio
async def test_eval_mcp_server_read_tools():
    """Verify MCP read tools return sanitized diagnostic details for registered case."""
    clear_eval_contexts()
    cases = load_evaluation_dataset()
    case = cases[0]
    dc = case.get_decision_context()
    register_eval_context(dc)

    client = RecoveryAgentClient(server=eval_mcp_server)

    # 1. get_payment_context
    p_ctx = await client.call_tool("get_payment_context", {"payment_id": dc.failed_payment_id})
    assert p_ctx["payment_id"] == dc.failed_payment_id
    assert p_ctx["amount_paise"] == dc.amount
    assert p_ctx["currency"] == dc.currency

    # 2. get_recovery_case
    c_info = await client.call_tool("get_recovery_case", {"case_id": dc.case_id})
    assert c_info["case_id"] == dc.case_id
    assert c_info["state"] == "ELIGIBILITY_CHECKED"

    # 3. get_recovery_status
    s_info = await client.call_tool("get_recovery_status", {"case_id": dc.case_id})
    assert s_info["case_id"] == dc.case_id
    assert s_info["is_eligible"] is True

    # Unknown case error check
    unknown = await client.call_tool("get_recovery_case", {"case_id": "nonexistent_case"})
    assert "error" in unknown


@pytest.mark.asyncio
async def test_eval_mcp_server_action_tool_guardrails():
    """Verify request_recovery_action executes deterministic guardrails without side effects."""
    clear_eval_contexts()
    cases = load_evaluation_dataset()

    # 1. Valid proposal -> APPROVE
    case_0 = cases[0]
    dc_0 = case_0.get_decision_context()
    register_eval_context(dc_0)

    client = RecoveryAgentClient(server=eval_mcp_server)
    res_0 = await client.call_tool(
        "request_recovery_action",
        {
            "case_id": dc_0.case_id,
            "proposed_policy": "P_CREATE_LINK_DELAYED",
            "proposed_amount": dc_0.amount,
            "proposed_currency": dc_0.currency,
            "explanation": "Valid delayed link proposal.",
        },
    )
    assert res_0["authorized"] is True
    assert res_0["decision"] == "APPROVE"
    assert res_0["effective_policy"] == "P_CREATE_LINK_DELAYED"

    # 2. High-value proposal -> ESCALATE
    hv_case = next(c for c in cases if c.decision_context.amount > 5_000_000)
    dc_hv = hv_case.get_decision_context()
    register_eval_context(dc_hv)

    res_hv = await client.call_tool(
        "request_recovery_action",
        {
            "case_id": dc_hv.case_id,
            "proposed_policy": "P_CREATE_LINK_IMMEDIATE",
            "proposed_amount": dc_hv.amount,
            "proposed_currency": dc_hv.currency,
        },
    )
    assert res_hv["authorized"] is False
    assert res_hv["decision"] == "ESCALATE"
    assert res_hv["effective_policy"] == "P_ESCALATE_ONLY"
    assert res_hv["reason_code"] == "HIGH_VALUE_THRESHOLD"

    # 3. Amount mutation -> REJECT
    res_tamper = await client.call_tool(
        "request_recovery_action",
        {
            "case_id": dc_0.case_id,
            "proposed_policy": "P_CREATE_LINK_DELAYED",
            "proposed_amount": dc_0.amount + 5000,
            "proposed_currency": dc_0.currency,
        },
    )
    assert res_tamper["authorized"] is False
    assert res_tamper["decision"] == "REJECT"
    assert res_tamper["reason_code"] == "AMOUNT_MUTATION_FORBIDDEN"


# =============================================================================
# 5. End-to-End Offline LLM & MCP Integration Pipeline Test
# =============================================================================


@pytest.mark.asyncio
async def test_end_to_end_offline_llm_mcp_pipeline():
    """Verify full end-to-end agentic triage flow over MCP and LLM boundaries."""
    clear_eval_contexts()
    cases = load_evaluation_dataset()
    case = cases[0]
    dc = case.get_decision_context()
    register_eval_context(dc)

    # 1. Create client and mock LLM
    mock_llm_response = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": json.dumps({
                                "case_id": dc.case_id,
                                "failure_category": "C1",
                                "proposed_policy_id": "P_CREATE_LINK_DELAYED",
                                "reasoning": "Gateway transient issue; recommend delayed recovery.",
                                "confidence_score": 0.94,
                                "proposed_amount": dc.amount,
                                "proposed_currency": dc.currency,
                            })
                        }
                    ]
                }
            }
        ]
    }

    def transport(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=mock_llm_response, request=request)

    mock_client = httpx.Client(transport=httpx.MockTransport(transport))
    provider = LLMAgentDecisionProvider(api_key="valid_key", http_client=mock_client)

    # 2. Agent queries MCP read tools
    mcp_client = RecoveryAgentClient(server=eval_mcp_server)
    p_context = await mcp_client.call_tool(
        "get_payment_context", {"payment_id": dc.failed_payment_id}
    )
    assert p_context["payment_id"] == dc.failed_payment_id

    # 3. LLM reasons from DecisionContext
    decision = provider.decide(dc)
    assert decision.proposed_policy_id == RecoveryPolicy.P_CREATE_LINK_DELAYED

    # 4. Agent submits proposal to MCP action tool
    mcp_res = await mcp_client.call_tool(
        "request_recovery_action",
        {
            "case_id": dc.case_id,
            "proposed_policy": decision.proposed_policy_id.value,
            "proposed_amount": decision.proposed_amount,
            "proposed_currency": decision.proposed_currency,
            "explanation": decision.reasoning,
        },
    )

    # 5. Deterministic guardrail authorization verified
    assert mcp_res["authorized"] is True
    assert mcp_res["decision"] == "APPROVE"
    assert mcp_res["effective_policy"] == "P_CREATE_LINK_DELAYED"
