"""Unit tests for LLM adapter, structured output enforcement, and fallback behavior."""

import json

import httpx
import pytest

from paymentflow.adapters.llm_adapter import LLMClient
from paymentflow.config import Settings
from paymentflow.domain.enums import (
    FailureCategory,
    RecoveryPolicy,
    TemplateId,
)
from paymentflow.domain.models import PaymentContext, PaymentFailureDetails


def make_test_context() -> PaymentContext:
    """Helper to create valid PaymentContext."""
    return PaymentContext(
        payment_id="pay_llm_test_01",
        amount=199900,
        currency="INR",
        status="failed",
        customer_id="cust_01",
        method="upi",
        failure=PaymentFailureDetails(
            code="PAYMENT_AUTHENTICATION_ERROR",
            description="UPI PIN timed out",
            source="customer",
        ),
    )


@pytest.mark.asyncio
async def test_llm_adapter_success_proposal():
    """Verify LLMClient parses valid Gemini structured JSON response into RecoveryProposal."""
    mock_payload = {
        "failure_category": "C1",
        "policy_id": "P_CREATE_LINK_IMMEDIATE",
        "template_id": "TPL_RECOVERY_STANDARD",
        "explanation": "Customer UPI PIN timed out; immediate link recommended.",
    }
    gemini_response = {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": json.dumps(mock_payload)}],
                    "role": "model",
                }
            }
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert "generativelanguage.googleapis.com" in request.url.host
        return httpx.Response(200, json=gemini_response)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        llm = LLMClient(
            settings=Settings(llm_api_key="real_test_key", llm_model="gemini-1.5-flash"),
            http_client=client,
        )
        proposal, metadata = await llm.generate_proposal(make_test_context())

        assert proposal.failure_category == FailureCategory.C1
        assert proposal.policy_id == RecoveryPolicy.P_CREATE_LINK_IMMEDIATE
        assert proposal.template_id == TemplateId.TPL_RECOVERY_STANDARD
        assert "Customer UPI PIN" in proposal.explanation
        assert metadata["is_fallback"] is False
        assert metadata["error"] is None
        assert metadata["latency_ms"] >= 0


@pytest.mark.asyncio
async def test_llm_adapter_timeout_fallback():
    """Verify network timeout returns deterministic safe fallback."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("Request timed out")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        llm = LLMClient(
            settings=Settings(llm_api_key="real_test_key"),
            http_client=client,
        )
        proposal, metadata = await llm.generate_proposal(make_test_context())

        assert proposal.policy_id == RecoveryPolicy.P_NO_ACTION
        assert metadata["is_fallback"] is True
        assert "timeout" in metadata["error"].lower() or "network" in metadata["error"].lower()


@pytest.mark.asyncio
async def test_llm_adapter_http_error_fallback():
    """Verify provider 500 error returns safe fallback."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="Internal Server Error")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        llm = LLMClient(
            settings=Settings(llm_api_key="real_test_key"),
            http_client=client,
        )
        proposal, metadata = await llm.generate_proposal(make_test_context())

        assert proposal.policy_id == RecoveryPolicy.P_NO_ACTION
        assert metadata["is_fallback"] is True
        assert "500" in metadata["error"]


@pytest.mark.asyncio
async def test_llm_adapter_malformed_json_fallback():
    """Verify malformed JSON from model triggers safe fallback."""
    gemini_response = {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": "not valid json {{"}],
                    "role": "model",
                }
            }
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=gemini_response)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        llm = LLMClient(
            settings=Settings(llm_api_key="real_test_key"),
            http_client=client,
        )
        proposal, metadata = await llm.generate_proposal(make_test_context())

        assert proposal.policy_id == RecoveryPolicy.P_NO_ACTION
        assert metadata["is_fallback"] is True
        assert "validation" in metadata["error"].lower() or "json" in metadata["error"].lower()


@pytest.mark.asyncio
async def test_llm_adapter_invalid_policy_schema_fallback():
    """Verify invalid policy ID in model output triggers safe fallback."""
    mock_payload = {
        "failure_category": "C1",
        "policy_id": "P_UNRESTRICTED_HACK",  # Illegal policy ID
        "explanation": "Do whatever.",
    }
    gemini_response = {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": json.dumps(mock_payload)}],
                    "role": "model",
                }
            }
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=gemini_response)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        llm = LLMClient(
            settings=Settings(llm_api_key="real_test_key"),
            http_client=client,
        )
        proposal, metadata = await llm.generate_proposal(make_test_context())

        assert proposal.policy_id == RecoveryPolicy.P_NO_ACTION
        assert metadata["is_fallback"] is True


@pytest.mark.asyncio
async def test_llm_adapter_placeholder_key_fallback():
    """Verify placeholder key skips external network call and returns fallback."""
    llm = LLMClient(settings=Settings(llm_api_key="placeholder_llm_api_key"))
    proposal, metadata = await llm.generate_proposal(make_test_context())

    assert proposal.policy_id == RecoveryPolicy.P_NO_ACTION
    assert metadata["is_fallback"] is True


@pytest.mark.asyncio
async def test_llm_adapter_transient_retry_success():
    """Verify LLMClient recovers from transient 503 via retry loop."""
    attempts = 0
    mock_payload = {
        "failure_category": "C1",
        "policy_id": "P_CREATE_LINK_IMMEDIATE",
        "template_id": "TPL_RECOVERY_STANDARD",
        "explanation": "Recovered after retry.",
    }
    gemini_response = {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": json.dumps(mock_payload)}],
                    "role": "model",
                }
            }
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(503, text="Service Unavailable")
        return httpx.Response(200, json=gemini_response)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        llm = LLMClient(
            settings=Settings(llm_api_key="real_test_key"),
            http_client=client,
        )
        proposal, metadata = await llm.generate_proposal(make_test_context())

        assert attempts == 2
        assert proposal.policy_id == RecoveryPolicy.P_CREATE_LINK_IMMEDIATE
        assert metadata["is_fallback"] is False
