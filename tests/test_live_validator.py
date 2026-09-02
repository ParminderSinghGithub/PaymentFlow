"""Unit and integration tests for Layer 5E Live LLM Validator and MCP Traversal."""

import json

import httpx
import pytest

from paymentflow.config import Settings
from paymentflow.eval.dataset import load_evaluation_dataset
from paymentflow.eval.live_validator import LiveLLMValidator
from paymentflow.eval.llm_provider import LLMAgentDecisionProvider


@pytest.mark.asyncio
async def test_live_validator_mcp_triage_flow_with_mock_llm():
    """Verify LiveLLMValidator executes MCP protocol traversal and guardrail authorization."""
    cases = load_evaluation_dataset()
    case = cases[0]
    dc = case.get_decision_context()

    mock_response = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": json.dumps(
                                {
                                    "case_id": dc.case_id,
                                    "failure_category": "C1",
                                    "proposed_policy_id": "P_CREATE_LINK_DELAYED",
                                    "reasoning": (
                                        "Gateway transient issue; recommend delayed recovery."
                                    ),
                                    "confidence_score": 0.94,
                                    "proposed_amount": dc.amount,
                                    "proposed_currency": dc.currency,
                                }
                            )
                        }
                    ]
                }
            }
        ]
    }

    def transport(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=mock_response, request=request)

    mock_client = httpx.Client(transport=httpx.MockTransport(transport))
    provider = LLMAgentDecisionProvider(api_key="valid_test_key", http_client=mock_client)
    validator = LiveLLMValidator(provider=provider)

    res = await validator.run_mcp_agent_triage_flow(case)

    assert res["case_id"] == dc.case_id
    assert res["llm_category"] == "C1"
    assert res["proposed_policy"] == "P_CREATE_LINK_DELAYED"
    assert res["authorized_policy"] == "P_CREATE_LINK_DELAYED"
    assert res["guardrail_changed"] is False
    assert res["mcp_tools_discovered"] == 5
    assert res["payment_ctx_retrieved"] is True
    assert res["case_info_retrieved"] is True
    assert res["status_retrieved"] is True


@pytest.mark.asyncio
async def test_live_validator_smoke_test_with_mock_llm():
    """Verify smoke test executes across representative C1-C5 cases."""
    cases = load_evaluation_dataset()

    def mock_handler(request: httpx.Request) -> httpx.Response:
        # Determine failure category from request body if possible
        body_str = request.content.decode()
        if "eval_case_019" in body_str:
            cat = "C2"
            pol = "P_CREATE_LINK_IMMEDIATE"
        elif "eval_case_039" in body_str:
            cat = "C3"
            pol = "P_CREATE_LINK_DELAYED"
        elif "eval_case_055" in body_str:
            cat = "C4"
            pol = "P_ESCALATE_ONLY"
        elif "eval_case_066" in body_str:
            cat = "C5"
            pol = "P_NO_ACTION"
        else:
            cat = "C1"
            pol = "P_CREATE_LINK_DELAYED"

        resp_data = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": json.dumps(
                                    {
                                        "case_id": "case_test",
                                        "failure_category": cat,
                                        "proposed_policy_id": pol,
                                        "reasoning": f"Triage decision for {cat}.",
                                        "confidence_score": 0.95,
                                    }
                                )
                            }
                        ]
                    }
                }
            ]
        }
        return httpx.Response(200, json=resp_data, request=request)

    mock_client = httpx.Client(transport=httpx.MockTransport(mock_handler))
    provider = LLMAgentDecisionProvider(api_key="valid_test_key", http_client=mock_client)
    validator = LiveLLMValidator(provider=provider)

    results = await validator.run_smoke_test(cases=cases)
    assert len(results) == 5
    categories_tested = {r["ground_truth_category"] for r in results}
    assert categories_tested == {"C1", "C2", "C3", "C4", "C5"}


@pytest.mark.asyncio
async def test_live_validator_controlled_evaluation_and_report_generation(tmp_path):
    """Verify controlled evaluation runs and generates formatted report."""

    def mock_handler(request: httpx.Request) -> httpx.Response:
        resp_data = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": json.dumps(
                                    {
                                        "case_id": "test_case",
                                        "failure_category": "C1",
                                        "proposed_policy_id": "P_CREATE_LINK_DELAYED",
                                        "reasoning": "Standard delayed recovery.",
                                        "confidence_score": 0.90,
                                    }
                                )
                            }
                        ]
                    }
                }
            ]
        }
        return httpx.Response(200, json=resp_data, request=request)

    mock_client = httpx.Client(transport=httpx.MockTransport(mock_handler))
    provider = LLMAgentDecisionProvider(api_key="valid_test_key", http_client=mock_client)
    validator = LiveLLMValidator(provider=provider)

    controlled_res = await validator.run_controlled_evaluation(sample_size=5)
    assert controlled_res["sample_size"] == 15
    assert controlled_res["valid_schema_rate"] == 1.0

    report_file = tmp_path / "TEST_REAL_LLM_REPORT.md"
    saved_path = validator.generate_validation_report(
        smoke_results=controlled_res["case_results"][:5],
        controlled_results=controlled_res,
        full_evaluation_decision="FULL EVALUATION JUSTIFIED",
        decision_reason="Testing mock justification reason.",
        report_path=report_file,
    )

    assert saved_path.exists()
    with open(saved_path, encoding="utf-8") as f:
        content = f.read()
    assert "# Real LLM Validation & Evaluation Integration Report" in content
    assert "Real MCP Protocol Boundary Verification" in content


def test_credential_availability_check():
    """Verify is_credential_available accurately detects valid vs placeholder keys."""
    v_placeholder = LiveLLMValidator(settings=Settings(llm_api_key="placeholder_llm_api_key"))
    assert v_placeholder.is_credential_available() is False

    v_empty = LiveLLMValidator(settings=Settings(llm_api_key=""))
    assert v_empty.is_credential_available() is False

    dummy_valid_key = "dummy_valid_api_key_for_testing_12345"
    v_valid = LiveLLMValidator(settings=Settings(llm_api_key=dummy_valid_key))
    assert v_valid.is_credential_available() is True
