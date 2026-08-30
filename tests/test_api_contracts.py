"""Comprehensive API contract tests for frontend/backend service boundary."""

from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from paymentflow.db.models import AuditEventModel, RecoveryCaseModel, utc_now
from paymentflow.db.session import get_sessionmaker
from paymentflow.domain.enums import CaseState, FailureCategory, RecoveryPolicy


@pytest.mark.asyncio
async def test_health_endpoint_healthy(client: AsyncClient):
    """Verify GET /health returns standard 200 OK schema when DB is connected."""
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("ok", "degraded")
    assert "environment" in data
    assert "database" in data
    assert "version" in data


@pytest.mark.asyncio
async def test_health_endpoint_degraded_when_db_fails(client: AsyncClient):
    """Verify GET /health returns degraded status cleanly without 500 crashes if DB fails."""
    with patch("paymentflow.api.health.ping_db", new_callable=AsyncMock) as mock_ping:
        mock_ping.return_value = False
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "degraded"
        assert data["database"] == "disconnected"


@pytest.mark.asyncio
async def test_cors_headers_present(client: AsyncClient):
    """Verify CORS middleware returns allow-origin headers for external frontend requests."""
    headers = {"Origin": "http://localhost:3000"}
    resp = await client.get("/health", headers=headers)
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") in ("*", "http://localhost:3000")


@pytest.mark.asyncio
async def test_list_cases_schema_and_filtering(client: AsyncClient):
    """Verify GET /cases response contract with state filtering and pagination."""
    sessionmaker = get_sessionmaker()
    case_id_1 = "case_contract_list_001"
    case_id_2 = "case_contract_list_002"

    async with sessionmaker() as session:
        c1 = RecoveryCaseModel(
            case_id=case_id_1,
            failed_payment_id="pay_contract_001",
            order_id="order_contract_001",
            customer_id="cust_contract_001",
            amount=250000,
            currency="INR",
            payment_method="card",
            failure_category=FailureCategory.C1.value,
            state=CaseState.ACTION_EXECUTED.value,
            validated_policy_id=RecoveryPolicy.P_CREATE_LINK_IMMEDIATE.value,
            payment_link_id="plink_contract_001",
            payment_link_short_url="https://rzp.io/i/test_contract",
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        c2 = RecoveryCaseModel(
            case_id=case_id_2,
            failed_payment_id="pay_contract_002",
            amount=150000,
            currency="INR",
            payment_method="upi",
            failure_category=FailureCategory.C2.value,
            state=CaseState.RECOVERED.value,
            recovered_amount=150000,
            recovered_payment_id="pay_rec_contract_002",
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add_all([c1, c2])
        await session.commit()

    # 1. Unfiltered query
    resp = await client.get("/cases?limit=50&offset=0")
    assert resp.status_code == 200
    items: list[dict[str, Any]] = resp.json()
    assert isinstance(items, list)
    target = next((item for item in items if item["case_id"] == case_id_1), None)
    assert target is not None
    assert target["amount_paise"] == 250000
    assert target["amount_inr"] == 2500.0
    assert target["currency"] == "INR"
    assert target["state"] == CaseState.ACTION_EXECUTED.value
    assert target["validated_policy_id"] == RecoveryPolicy.P_CREATE_LINK_IMMEDIATE.value
    assert target["payment_link_id"] == "plink_contract_001"

    # 2. Filtered by state=RECOVERED
    resp_filtered = await client.get(f"/cases?state={CaseState.RECOVERED.value}")
    assert resp_filtered.status_code == 200
    filtered_items: list[dict[str, Any]] = resp_filtered.json()
    assert all(item["state"] == CaseState.RECOVERED.value for item in filtered_items)
    assert any(item["case_id"] == case_id_2 for item in filtered_items)
    assert not any(item["case_id"] == case_id_1 for item in filtered_items)


@pytest.mark.asyncio
async def test_get_case_detail_observability_and_audit(client: AsyncClient):
    """Verify GET /cases/{case_id} returns full explainability context and audit events."""
    sessionmaker = get_sessionmaker()
    case_id = "case_contract_detail_001"

    async with sessionmaker() as session:
        c = RecoveryCaseModel(
            case_id=case_id,
            failed_payment_id="pay_detail_001",
            order_id="order_detail_001",
            customer_id="cust_detail_001",
            amount=500000,
            currency="INR",
            payment_method="card",
            failure_category=FailureCategory.C1.value,
            failure_code="BAD_REQUEST_ERROR",
            failure_description="Card authentication timed out",
            failure_context={"error_source": "customer", "error_step": "payment_authentication"},
            classification_evidence={"rule": "CUSTOMER_AUTH_FAILURE"},
            eligibility_status="ELIGIBLE",
            eligibility_reason="RULES_PASSED",
            ai_policy_id="P_CREATE_LINK_IMMEDIATE",
            ai_explanation="Customer action failure with high recovery likelihood.",
            validated_policy_id="P_CREATE_LINK_IMMEDIATE",
            action_status="LINK_CREATED",
            payment_link_id=f"plink_{case_id}",
            payment_link_reference_id=case_id,
            payment_link_short_url=f"https://rzp.io/i/test_{case_id}",
            payment_link_status="created",
            state=CaseState.ACTION_EXECUTED.value,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        audit_1 = AuditEventModel(
            case_id=case_id,
            event_type="CONTEXT_ENRICHED",
            actor="recovery_service",
            decision="SUCCESS",
            timestamp=utc_now() - timedelta(seconds=10),
            details={"source": "gateway_api"},
        )
        audit_2 = AuditEventModel(
            case_id=case_id,
            event_type="POLICY_GUARDRAIL_VALIDATED",
            actor="policy_guardrail_engine",
            decision="APPROVE",
            policy="P_CREATE_LINK_IMMEDIATE",
            guardrail_result={"authorized": True, "effective_policy": "P_CREATE_LINK_IMMEDIATE"},
            timestamp=utc_now() - timedelta(seconds=5),
        )
        session.add_all([c, audit_1, audit_2])
        await session.commit()

    resp = await client.get(f"/cases/{case_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert "case" in data
    assert "audit_trail" in data

    case_data = data["case"]
    assert case_data["case_id"] == case_id
    assert case_data["amount_paise"] == 500000
    assert case_data["amount_inr"] == 5000.0
    assert case_data["failure_context"]["error_source"] == "customer"
    assert case_data["classification_evidence"]["rule"] == "CUSTOMER_AUTH_FAILURE"
    assert case_data["ai_policy_id"] == "P_CREATE_LINK_IMMEDIATE"
    assert case_data["validated_policy_id"] == "P_CREATE_LINK_IMMEDIATE"
    assert case_data["payment_link_id"] == f"plink_{case_id}"

    audit_trail = data["audit_trail"]
    assert len(audit_trail) == 2
    assert audit_trail[0]["event_type"] == "CONTEXT_ENRICHED"
    assert audit_trail[1]["event_type"] == "POLICY_GUARDRAIL_VALIDATED"


@pytest.mark.asyncio
async def test_get_case_detail_not_found(client: AsyncClient):
    """Verify GET /cases/{case_id} returns structured 404 error when case does not exist."""
    resp = await client.get("/cases/non_existent_case_9999")
    assert resp.status_code == 404
    error_data = resp.json()
    assert "detail" in error_data
    assert "not found" in error_data["detail"].lower()


@pytest.mark.asyncio
async def test_metrics_summary_contract(client: AsyncClient):
    """Verify GET /cases/metrics/summary returns comprehensive aggregated metrics."""
    resp = await client.get("/cases/metrics/summary")
    assert resp.status_code == 200
    metrics = resp.json()
    required_fields = [
        "total_cases",
        "recovered_cases",
        "total_recovered_amount_inr",
        "recovery_rate_pct",
        "active_recovery_links",
        "escalated_cases",
        "terminal_no_action_cases",
        "category_breakdown",
        "policy_breakdown",
    ]
    for field in required_fields:
        assert field in metrics
    assert isinstance(metrics["category_breakdown"], dict)
    assert isinstance(metrics["policy_breakdown"], dict)


@pytest.mark.asyncio
async def test_trigger_case_triage_not_found(client: AsyncClient):
    """Verify POST /cases/{case_id}/triage returns 404 if case does not exist."""
    resp = await client.post("/cases/non_existent_case_8888/triage")
    assert resp.status_code == 404
    error_data = resp.json()
    assert "detail" in error_data
    assert "not found" in error_data["detail"].lower()


@pytest.mark.asyncio
async def test_delayed_process_endpoint_contract(client: AsyncClient):
    """Verify POST /cases/delayed/process returns batch execution summary."""
    resp = await client.post("/cases/delayed/process")
    assert resp.status_code == 200
    data = resp.json()
    assert "processed_count" in data
    assert "results" in data
    assert isinstance(data["results"], list)


@pytest.mark.asyncio
async def test_query_validation_error_handling(client: AsyncClient):
    """Verify API returns structured 422 Unprocessable Entity on schema validation error."""
    # limit must be between 1 and 200
    resp_invalid_limit = await client.get("/cases?limit=500")
    assert resp_invalid_limit.status_code == 422
    data = resp_invalid_limit.json()
    assert "detail" in data
    assert any(err["loc"][-1] == "limit" for err in data["detail"])
