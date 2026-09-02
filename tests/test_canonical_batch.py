"""Tests for Canonical 15-Case Demonstration Batch."""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from paymentflow.db.models import AuditEventModel, RecoveryCaseModel
from paymentflow.db.session import get_sessionmaker
from paymentflow.domain.enums import CaseState
from paymentflow.eval.canonical_batch import (
    CANONICAL_BATCH_SCENARIOS,
    seed_canonical_demonstration_batch,
)
from paymentflow.main import app


@pytest.mark.asyncio
async def test_canonical_batch_scenarios_definition():
    """Verify the definition and integrity of the 15 canonical scenarios."""
    assert len(CANONICAL_BATCH_SCENARIOS) == 15

    # Check scenario IDs
    scenario_ids = [s["id"] for s in CANONICAL_BATCH_SCENARIOS]
    expected_ids = [f"CS{i:02d}" for i in range(1, 16)]
    assert scenario_ids == expected_ids

    # Check total revenue at risk
    total_risk = sum(s["amount"] for s in CANONICAL_BATCH_SCENARIOS)
    assert total_risk == 13400000  # ₹134,000.00

    # Check total recovered amount
    total_rec = sum(s["recovered_amount"] or 0 for s in CANONICAL_BATCH_SCENARIOS)
    assert total_rec == 3070000  # ₹30,700.00

    # Check state distribution
    states = [s["state"] for s in CANONICAL_BATCH_SCENARIOS]
    assert states.count(CaseState.RECOVERED.value) == 6
    assert states.count(CaseState.ESCALATED.value) == 2
    assert states.count(CaseState.TERMINAL_NO_ACTION.value) == 6
    assert states.count(CaseState.ACTION_EXECUTED.value) == 1


@pytest.mark.asyncio
async def test_seed_canonical_demonstration_batch():
    """Test seeding canonical batch into PostgreSQL directly via sessionmaker."""
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        res = await seed_canonical_demonstration_batch(session=session, reset_first=True)
        assert res["status"] == "success"
        assert res["seeded_cases_count"] == 15
        assert res["total_revenue_at_risk_inr"] == 134000.0
        assert res["total_recovered_inr"] == 30700.0
        assert res["recovery_rate_pct"] == 22.91

        # Verify DB records
        demo_cases = (
            await session.scalars(
                select(RecoveryCaseModel).where(RecoveryCaseModel.case_id.like("case_demo_%"))
            )
        ).all()
        assert len(demo_cases) == 15

        # Check high value case CS04
        cs04 = next(c for c in demo_cases if c.case_id == "case_demo_cs04_high_value")
        assert cs04.amount == 7500000
        assert cs04.state == CaseState.ESCALATED.value
        assert cs04.validated_policy_id == "P_ESCALATE_ONLY"

        # Check audit trail count
        audit_events = (
            await session.scalars(
                select(AuditEventModel).where(AuditEventModel.case_id.like("case_demo_%"))
            )
        ).all()
        assert len(audit_events) >= 90  # Average >6 events per case


@pytest.mark.asyncio
async def test_api_demo_seed_endpoint():
    """Test POST /cases/demo/seed endpoint via FastAPI TestClient."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Seed batch
        res = await client.post("/cases/demo/seed?reset_first=true")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"
        assert data["seeded_cases_count"] == 15
        assert data["total_recovered_inr"] == 30700.0

        # Query metrics
        res_m = await client.get("/cases/metrics/summary")
        assert res_m.status_code == 200
        m = res_m.json()
        assert m["total_cases"] >= 15
        assert m["recovered_cases"] >= 6
        assert m["total_recovered_amount_inr"] >= 30700.0

        # Query individual case
        res_c = await client.get("/cases/case_demo_cs01_otp_dropoff")
        assert res_c.status_code == 200
        detail = res_c.json()
        assert detail["case"]["case_id"] == "case_demo_cs01_otp_dropoff"
        assert detail["case"]["state"] == "RECOVERED"
        assert len(detail["audit_trail"]) == 9


@pytest.mark.asyncio
async def test_repeated_seed_idempotency():
    """Verify that repeated seed execution does not create duplicate records."""
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        # Seed twice
        await seed_canonical_demonstration_batch(session=session, reset_first=True)
        res2 = await seed_canonical_demonstration_batch(session=session, reset_first=True)
        assert res2["seeded_cases_count"] == 15

        count = await session.scalar(
            select(func.count(RecoveryCaseModel.case_id)).where(
                RecoveryCaseModel.case_id.like("case_demo_%")
            )
        )
        assert count == 15
