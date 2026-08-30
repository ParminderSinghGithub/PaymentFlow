"""Comprehensive integration tests for the Production Recovery Orchestration Workflow."""

import json
from datetime import timedelta
from typing import Any

import httpx
import pytest
from httpx import AsyncClient

from paymentflow.adapters.llm_adapter import LLMClient
from paymentflow.adapters.razorpay_adapter import RazorpayAdapter
from paymentflow.config import Settings
from paymentflow.db.models import AuditEventModel, RecoveryCaseModel, utc_now
from paymentflow.db.session import get_sessionmaker
from paymentflow.domain.enums import CaseState, FailureCategory, RecoveryPolicy
from paymentflow.mcp.client import RecoveryAgentClient
from paymentflow.services.recovery_executor import RecoveryExecutor
from paymentflow.services.recovery_orchestrator import RecoveryOrchestrator
from paymentflow.services.webhook_service import WebhookService


@pytest.fixture
def mock_gemini_immediate():
    """Mock Gemini transport returning P_CREATE_LINK_IMMEDIATE."""
    def handler(request: httpx.Request) -> httpx.Response:
        resp = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": json.dumps({
                                    "failure_category": "C1",
                                    "policy_id": "P_CREATE_LINK_IMMEDIATE",
                                    "template_id": "TPL_RECOVERY_STANDARD",
                                    "explanation": "Transient OTP error; immediate link.",
                                })
                            }
                        ]
                    }
                }
            ]
        }
        return httpx.Response(200, json=resp, request=request)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.fixture
def mock_gemini_delayed():
    """Mock Gemini transport returning P_CREATE_LINK_DELAYED."""
    def handler(request: httpx.Request) -> httpx.Response:
        resp = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": json.dumps({
                                    "failure_category": "C1",
                                    "policy_id": "P_CREATE_LINK_DELAYED",
                                    "template_id": "TPL_RECOVERY_STANDARD",
                                    "explanation": "Gateway timeout; delayed link recommended.",
                                })
                            }
                        ]
                    }
                }
            ]
        }
        return httpx.Response(200, json=resp, request=request)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.fixture
def mock_razorpay_adapter(test_settings: Settings):
    """Mock Razorpay adapter for test execution."""
    adapter = RazorpayAdapter(settings=test_settings)

    async def mock_get_payment(payment_id: str) -> dict[str, Any]:
        amt = 80_000_00 if "high" in payment_id else 250000
        error_source = "risk" if "c4" in payment_id else "customer"
        error_code = "BUSINESS_RULE_ERROR" if "c4" in payment_id else "BAD_REQUEST_ERROR"
        error_reason = "high_risk_flag" if "c4" in payment_id else "payment_failed"
        return {
            "id": payment_id,
            "entity": "payment",
            "amount": amt,
            "currency": "INR",
            "status": "failed",
            "method": "card",
            "order_id": "order_test_001",
            "customer_id": "cust_test_001",
            "error_code": error_code,
            "error_description": "Payment authorization failed",
            "error_source": error_source,
            "error_step": "payment_authentication",
            "error_reason": error_reason,
            "created_at": 1700000000,
        }

    async def mock_get_order(order_id: str) -> dict[str, Any]:
        return {
            "id": order_id,
            "entity": "order",
            "amount": 250000,
            "currency": "INR",
            "status": "created",
        }

    async def mock_create_payment_link(
        amount: int,
        currency: str,
        description: str | None = None,
        reference_id: str | None = None,
        notes: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "id": f"plink_{reference_id}",
            "entity": "payment_link",
            "amount": amount,
            "currency": currency,
            "status": "created",
            "short_url": f"https://rzp.io/i/test_{reference_id}",
            "reference_id": reference_id,
        }

    adapter.get_payment = mock_get_payment  # type: ignore
    adapter.get_order = mock_get_order  # type: ignore
    adapter.create_payment_link = mock_create_payment_link  # type: ignore
    return adapter


@pytest.mark.asyncio
async def test_end_to_end_immediate_recovery_pipeline(
    test_settings: Settings,
    mock_gemini_immediate: httpx.AsyncClient,
    mock_razorpay_adapter: RazorpayAdapter,
):
    """Verify complete pipeline: Ingest -> L2 -> MCP Agent -> Guardrails -> Link -> Paid."""
    settings = test_settings.model_copy(update={"llm_api_key": "valid_test_key"})
    sessionmaker = get_sessionmaker()
    case_id = "case_prod_imm_001"

    # 1. Webhook Ingestion: Create case in FAILED_INGESTED
    async with sessionmaker() as session:
        case = RecoveryCaseModel(
            case_id=case_id,
            failed_payment_id="pay_prod_imm_001",
            order_id="order_prod_001",
            customer_id="cust_prod_001",
            amount=250000,
            currency="INR",
            payment_method="card",
            failure_code="BAD_REQUEST_ERROR",
            failure_description="Authentication failed",
            state=CaseState.FAILED_INGESTED.value,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(case)
        await session.commit()

    # 2. Setup Orchestrator with MCP Client and Mock LLM
    llm_client = LLMClient(settings=settings, http_client=mock_gemini_immediate)
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

    # 3. Execute End-to-End Orchestration
    result = await orchestrator.orchestrate_recovery(case_id=case_id)

    assert result["success"] is True
    assert result["state"] == CaseState.ACTION_EXECUTED.value
    assert result["policy"] == RecoveryPolicy.P_CREATE_LINK_IMMEDIATE.value
    assert result["payment_link_id"] == f"plink_{case_id}"
    assert result["payment_link_url"] == f"https://rzp.io/i/test_{case_id}"

    # 4. Verify DB State & Audit Trail
    async with sessionmaker() as session:
        reloaded = await session.get(RecoveryCaseModel, case_id)
        assert reloaded is not None
        assert reloaded.state == CaseState.ACTION_EXECUTED.value
        assert reloaded.payment_link_id == f"plink_{case_id}"
        assert reloaded.validated_policy_id == RecoveryPolicy.P_CREATE_LINK_IMMEDIATE.value

        audits = await orchestrator.get_case_audit_trail(case_id)
        event_types = [a["event_type"] for a in audits]
        assert "CONTEXT_ENRICHED" in event_types
        assert "FAILURE_CLASSIFIED" in event_types
        assert "ELIGIBILITY_EVALUATED" in event_types
        assert "POLICY_GUARDRAIL_VALIDATED" in event_types
        assert "RAZORPAY_PAYMENT_LINK_CREATED" in event_types

    # 5. Customer Outcome: Payment Link Paid Webhook
    async with sessionmaker() as session:
        async def mock_captured_payment(pid: str) -> dict[str, Any]:
            return {
                "id": pid,
                "status": "captured",
                "amount": 250000,
                "currency": "INR",
                "order_id": "order_prod_001",
            }

        mock_razorpay_adapter.get_payment = mock_captured_payment  # type: ignore
        webhook_service = WebhookService(session, razorpay_adapter=mock_razorpay_adapter)
        paid_payload = {
            "entity": "event",
            "event": "payment_link.paid",
            "payload": {
                "payment_link": {
                    "entity": {
                        "id": f"plink_{case_id}",
                        "reference_id": case_id,
                        "amount": 250000,
                        "currency": "INR",
                        "status": "paid",
                    }
                },
                "payment": {
                    "entity": {
                        "id": "pay_recovered_imm_001",
                        "amount": 250000,
                        "currency": "INR",
                        "status": "captured",
                    }
                },
            },
        }
        res_paid = await webhook_service.process_webhook(
            raw_body=json.dumps(paid_payload).encode(),
            payload=paid_payload,
            signature_verified=True,
        )
        assert res_paid.status == "ok"
        assert res_paid.state == CaseState.RECOVERED.value

    # 6. Verify Final RECOVERED State and Revenue Attribution
    async with sessionmaker() as session:
        final_case = await session.get(RecoveryCaseModel, case_id)
        assert final_case.state == CaseState.RECOVERED.value
        assert final_case.recovered_amount == 250000
        assert final_case.recovered_payment_id == "pay_recovered_imm_001"


@pytest.mark.asyncio
async def test_end_to_end_delayed_recovery_pipeline(
    test_settings: Settings,
    mock_gemini_delayed: httpx.AsyncClient,
    mock_razorpay_adapter: RazorpayAdapter,
):
    """Verify delayed policy scheduling and restart-safe batch processing."""
    settings = test_settings.model_copy(update={"llm_api_key": "valid_test_key"})
    sessionmaker = get_sessionmaker()
    case_id = "case_prod_del_001"

    # 1. Ingest case
    async with sessionmaker() as session:
        case = RecoveryCaseModel(
            case_id=case_id,
            failed_payment_id="pay_prod_del_001",
            amount=150000,
            currency="INR",
            payment_method="card",
            failure_code="BAD_REQUEST_ERROR",
            failure_description="Timeout",
            state=CaseState.FAILED_INGESTED.value,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(case)
        await session.commit()

    llm_client = LLMClient(settings=settings, http_client=mock_gemini_delayed)
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

    # 2. Execute Orchestration -> Schedules Delayed
    result = await orchestrator.orchestrate_recovery(case_id=case_id)
    assert result["success"] is True
    assert result["stage"] == "SCHEDULED_DELAYED"
    assert result["policy"] == RecoveryPolicy.P_CREATE_LINK_DELAYED.value
    assert result["action_executed"] is False

    # Verify DB case is ACTION_APPROVED with scheduled_at in future
    async with sessionmaker() as session:
        scheduled_case = await session.get(RecoveryCaseModel, case_id)
        assert scheduled_case.state == CaseState.ACTION_APPROVED.value
        assert scheduled_case.action_status == "SCHEDULED_DELAYED"
        assert scheduled_case.scheduled_at is not None
        assert scheduled_case.payment_link_id is None

    # 3. Simulate Restart & Due Background Execution
    # Run due processor simulating future time (now + 20 mins)
    future_time = utc_now() + timedelta(minutes=20)
    executed_results = await orchestrator.process_due_delayed_cases(now=future_time)

    assert len(executed_results) >= 1
    target_exec = next((r for r in executed_results if r.case_id == case_id), None)
    assert target_exec is not None
    assert target_exec.success is True
    assert target_exec.state == CaseState.ACTION_EXECUTED
    assert target_exec.payment_link_id == f"plink_{case_id}"

    # Verify DB updated
    async with sessionmaker() as session:
        reloaded = await session.get(RecoveryCaseModel, case_id)
        assert reloaded.state == CaseState.ACTION_EXECUTED.value
        assert reloaded.payment_link_id == f"plink_{case_id}"


@pytest.mark.asyncio
async def test_high_value_escalation_guardrail_override(
    test_settings: Settings,
    mock_gemini_immediate: httpx.AsyncClient,
    mock_razorpay_adapter: RazorpayAdapter,
):
    """Verify transaction > ₹50,000 is intercepted by guardrails and escalated."""
    settings = test_settings.model_copy(update={"llm_api_key": "valid_test_key"})
    sessionmaker = get_sessionmaker()
    case_id = "case_prod_high_001"

    async with sessionmaker() as session:
        case = RecoveryCaseModel(
            case_id=case_id,
            failed_payment_id="pay_prod_high_001",
            amount=80_000_00,  # ₹80,000
            currency="INR",
            payment_method="card",
            failure_code="BAD_REQUEST_ERROR",
            failure_description="Auth failure",
            state=CaseState.FAILED_INGESTED.value,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(case)
        await session.commit()

    llm_client = LLMClient(settings=settings, http_client=mock_gemini_immediate)
    agent_client = RecoveryAgentClient(settings=settings, llm_client=llm_client)
    orchestrator = RecoveryOrchestrator(
        sessionmaker=sessionmaker,
        razorpay_adapter=mock_razorpay_adapter,
        agent_client=agent_client,
        settings=settings,
    )

    result = await orchestrator.orchestrate_recovery(case_id=case_id)

    assert result["success"] is True
    assert result["state"] == CaseState.ESCALATED.value
    assert result["action_executed"] is False

    async with sessionmaker() as session:
        reloaded = await session.get(RecoveryCaseModel, case_id)
        assert reloaded.state == CaseState.ESCALATED.value
        assert reloaded.payment_link_id is None


@pytest.mark.asyncio
async def test_llm_timeout_fail_closed_safe_fallback(
    test_settings: Settings,
    mock_razorpay_adapter: RazorpayAdapter,
):
    """Verify LLM timeout cleanly fails closed to P_NO_ACTION without crashes."""
    settings = test_settings.model_copy(update={"llm_api_key": "valid_test_key"})
    sessionmaker = get_sessionmaker()
    case_id = "case_prod_timeout_001"

    async with sessionmaker() as session:
        case = RecoveryCaseModel(
            case_id=case_id,
            failed_payment_id="pay_prod_timeout_001",
            amount=100000,
            currency="INR",
            payment_method="card",
            failure_code="BAD_REQUEST_ERROR",
            failure_description="Declined",
            state=CaseState.FAILED_INGESTED.value,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(case)
        await session.commit()

    def timeout_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("Gemini Timeout")

    async with httpx.AsyncClient(transport=httpx.MockTransport(timeout_handler)) as timeout_client:
        llm_client = LLMClient(settings=settings, http_client=timeout_client)
        agent_client = RecoveryAgentClient(settings=settings, llm_client=llm_client)
        orchestrator = RecoveryOrchestrator(
            sessionmaker=sessionmaker,
            razorpay_adapter=mock_razorpay_adapter,
            agent_client=agent_client,
            settings=settings,
        )

        result = await orchestrator.orchestrate_recovery(case_id=case_id)

        assert result["success"] is True
        assert result["state"] == CaseState.TERMINAL_NO_ACTION.value
        assert result["policy"] == RecoveryPolicy.P_NO_ACTION.value
        assert result["action_executed"] is False


@pytest.mark.asyncio
async def test_api_case_endpoints_and_metrics(
    client: AsyncClient,
    test_settings: Settings,
):
    """Verify API status, case query, and metric summary endpoints."""
    sessionmaker = get_sessionmaker()
    case_id = "case_api_test_001"

    async with sessionmaker() as session:
        case = RecoveryCaseModel(
            case_id=case_id,
            failed_payment_id="pay_api_test_001",
            order_id="order_api_001",
            customer_id="cust_api_001",
            amount=500000,  # ₹5,000
            currency="INR",
            payment_method="card",
            failure_category=FailureCategory.C1.value,
            state=CaseState.RECOVERED.value,
            recovered_amount=500000,
            recovered_payment_id="pay_rec_001",
            validated_policy_id="P_CREATE_LINK_IMMEDIATE",
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        audit = AuditEventModel(
            case_id=case_id,
            event_type="TEST_EVENT",
            actor="system",
            decision="SUCCESS",
            timestamp=utc_now(),
        )
        session.add_all([case, audit])
        await session.commit()

    # 1. Test GET /cases
    resp_list = await client.get("/cases")
    assert resp_list.status_code == 200
    cases_data = resp_list.json()
    assert any(c["case_id"] == case_id for c in cases_data)

    # 2. Test GET /cases/{case_id}
    resp_detail = await client.get(f"/cases/{case_id}")
    assert resp_detail.status_code == 200
    detail = resp_detail.json()
    assert detail["case"]["case_id"] == case_id
    assert detail["case"]["state"] == "RECOVERED"
    assert len(detail["audit_trail"]) >= 1

    # 3. Test GET /cases/metrics/summary
    resp_metrics = await client.get("/cases/metrics/summary")
    assert resp_metrics.status_code == 200
    metrics = resp_metrics.json()
    assert metrics["total_cases"] >= 1
    assert metrics["recovered_cases"] >= 1
    assert metrics["total_recovered_amount_inr"] >= 5000.0

    # 4. Test POST /cases/delayed/process
    resp_proc = await client.post("/cases/delayed/process")
    assert resp_proc.status_code == 200
    assert "processed_count" in resp_proc.json()

    # 5. Test GET non-existent case -> 404
    resp_404 = await client.get("/cases/non_existent_case_123")
    assert resp_404.status_code == 404

    # 6. Test POST /cases/{case_id}/triage
    resp_triage = await client.post(f"/cases/{case_id}/triage")
    assert resp_triage.status_code == 200


@pytest.mark.asyncio
async def test_malformed_llm_output_fail_closed_safe_fallback(
    test_settings: Settings,
    mock_razorpay_adapter: RazorpayAdapter,
):
    """Verify malformed JSON from LLM is handled safely via fail-closed fallback."""
    settings = test_settings.model_copy(update={"llm_api_key": "valid_test_key"})
    sessionmaker = get_sessionmaker()
    case_id = "case_prod_malformed_001"

    async with sessionmaker() as session:
        case = RecoveryCaseModel(
            case_id=case_id,
            failed_payment_id="pay_prod_malformed_001",
            amount=120000,
            currency="INR",
            payment_method="card",
            failure_code="BAD_REQUEST_ERROR",
            state=CaseState.FAILED_INGESTED.value,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(case)
        await session.commit()

    def malformed_handler(request: httpx.Request) -> httpx.Response:
        resp = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": "This is non-JSON raw plain text from model."
                            }
                        ]
                    }
                }
            ]
        }
        return httpx.Response(200, json=resp, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(malformed_handler)) as bad_client:
        llm_client = LLMClient(settings=settings, http_client=bad_client)
        agent_client = RecoveryAgentClient(settings=settings, llm_client=llm_client)
        orchestrator = RecoveryOrchestrator(
            sessionmaker=sessionmaker,
            razorpay_adapter=mock_razorpay_adapter,
            agent_client=agent_client,
            settings=settings,
        )

        result = await orchestrator.orchestrate_recovery(case_id=case_id)
        assert result["success"] is True
        assert result["state"] == CaseState.TERMINAL_NO_ACTION.value
        assert result["policy"] == RecoveryPolicy.P_NO_ACTION.value
        assert result["action_executed"] is False


@pytest.mark.asyncio
async def test_c4_business_risk_escalates_without_link(
    test_settings: Settings,
    mock_gemini_immediate: httpx.AsyncClient,
    mock_razorpay_adapter: RazorpayAdapter,
):
    """Verify C4 risk failure is guarded and escalated to P_ESCALATE_ONLY."""
    settings = test_settings.model_copy(update={"llm_api_key": "valid_test_key"})
    sessionmaker = get_sessionmaker()
    case_id = "case_prod_c4_001"

    async with sessionmaker() as session:
        case = RecoveryCaseModel(
            case_id=case_id,
            failed_payment_id="pay_prod_c4_001",
            amount=150000,
            currency="INR",
            payment_method="card",
            failure_code="RISK_CHECK_FAILED",
            failure_description="Transaction flagged by risk engine",
            failure_context={"error_source": "risk", "error_reason": "high_risk_flag"},
            state=CaseState.FAILED_INGESTED.value,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(case)
        await session.commit()

    llm_client = LLMClient(settings=settings, http_client=mock_gemini_immediate)
    agent_client = RecoveryAgentClient(settings=settings, llm_client=llm_client)
    orchestrator = RecoveryOrchestrator(
        sessionmaker=sessionmaker,
        razorpay_adapter=mock_razorpay_adapter,
        agent_client=agent_client,
        settings=settings,
    )

    result = await orchestrator.orchestrate_recovery(case_id=case_id)
    assert result["success"] is True
    assert result["state"] in (CaseState.ESCALATED.value, CaseState.TERMINAL_NO_ACTION.value)
    assert result["action_executed"] is False

    async with sessionmaker() as session:
        reloaded = await session.get(RecoveryCaseModel, case_id)
        assert reloaded.payment_link_id is None


@pytest.mark.asyncio
async def test_delayed_execution_state_freshness_recheck(
    test_settings: Settings,
    mock_razorpay_adapter: RazorpayAdapter,
):
    """Verify delayed case already recovered in interim is aborted before link creation."""
    settings = test_settings.model_copy(update={"llm_api_key": "valid_test_key"})
    sessionmaker = get_sessionmaker()
    case_id = "case_prod_freshness_001"

    # Case was approved for delayed link, but customer paid on another channel
    # and state moved to RECOVERED in the interim.
    async with sessionmaker() as session:
        case = RecoveryCaseModel(
            case_id=case_id,
            failed_payment_id="pay_prod_freshness_001",
            amount=200000,
            currency="INR",
            payment_method="card",
            validated_policy_id=RecoveryPolicy.P_CREATE_LINK_DELAYED.value,
            state=CaseState.RECOVERED.value,  # Already recovered!
            scheduled_at=utc_now() - timedelta(minutes=5),  # Due now
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(case)
        await session.commit()

    executor = RecoveryExecutor(
        sessionmaker=sessionmaker,
        razorpay_adapter=mock_razorpay_adapter,
        settings=settings,
    )
    orchestrator = RecoveryOrchestrator(
        sessionmaker=sessionmaker,
        razorpay_adapter=mock_razorpay_adapter,
        executor=executor,
        settings=settings,
    )

    # Process due cases
    results = await orchestrator.process_due_delayed_cases()
    # Case was in state RECOVERED (not ACTION_APPROVED), so it should not execute any new link
    assert len(results) == 0

    async with sessionmaker() as session:
        reloaded = await session.get(RecoveryCaseModel, case_id)
        assert reloaded.state == CaseState.RECOVERED.value
        assert reloaded.payment_link_id is None
