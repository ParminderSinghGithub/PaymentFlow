"""Tests for Canonical Recovery Workflow Benchmark Execution Engine (Phase C2)."""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from paymentflow.db.models import AuditEventModel, EvaluationRunModel, RecoveryCaseModel
from paymentflow.db.session import get_sessionmaker
from paymentflow.domain.enums import CaseState
from paymentflow.eval.benchmark_runner import BenchmarkRunner
from paymentflow.eval.canonical_scenarios import CANONICAL_BENCHMARK_SCENARIOS
from paymentflow.main import app


def test_all_15_canonical_amounts_are_distinct():
    """Requirement: All 15 canonical benchmark scenarios must have distinct INR amounts."""
    assert len(CANONICAL_BENCHMARK_SCENARIOS) == 15
    amounts = [s["amount_paise"] for s in CANONICAL_BENCHMARK_SCENARIOS]
    assert len(amounts) == len(set(amounts)), "Duplicate amounts found across canonical scenarios!"


def test_no_razorpay_looking_synthetic_ids_in_scenarios():
    """Requirement: Benchmark scenarios must not use pay_demo_* or fake Razorpay identifiers."""
    for s in CANONICAL_BENCHMARK_SCENARIOS:
        # Check scenario IDs and payment identifiers
        assert not s["scenario_id"].startswith("pay_")
        assert "pay_demo" not in str(s)


@pytest.mark.asyncio
async def test_benchmark_execution_engine_workflow():
    """Verify end-to-end benchmark workflow execution through decision and guardrail layers."""
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        result = await BenchmarkRunner.run_benchmark(session=session)

        assert result["status"] == "COMPLETED"
        assert result["case_source"] == "CANONICAL_EVALUATION"
        assert result["total_cases"] == 15

        eval_run_id = result["eval_run_id"]
        assert eval_run_id.startswith("eval_run_")

        # 1. Check distinct amounts in executed cases
        case_amounts = [c["amount_inr"] for c in result["cases"]]
        assert len(case_amounts) == 15
        assert len(case_amounts) == len(set(case_amounts))

        # 2. Check no fake Razorpay IDs
        for c in result["cases"]:
            assert not c["case_id"].startswith("pay_")

        # 3. Check CS07 amount mutation guardrail rejection
        cs07_case = next(c for c in result["cases"] if c["scenario_id"] == "CS07")
        assert cs07_case["policy_decision"] == "REJECT"
        assert cs07_case["final_state"] == CaseState.TERMINAL_NO_ACTION.value
        assert cs07_case["evaluation_recovered_amount_inr"] == 0.0

        # 4. Check CS08 currency mutation guardrail rejection
        cs08_case = next(c for c in result["cases"] if c["scenario_id"] == "CS08")
        assert cs08_case["policy_decision"] == "REJECT"
        assert cs08_case["final_state"] == CaseState.TERMINAL_NO_ACTION.value

        # 5. Check CS04 high-value escalation (>₹50,000 threshold)
        cs04_case = next(c for c in result["cases"] if c["scenario_id"] == "CS04")
        assert cs04_case["amount_inr"] == 65000.0
        assert cs04_case["policy_decision"] == "ESCALATE"
        assert cs04_case["final_state"] == CaseState.ESCALATED.value

        # 6. Check CS05 risk filter rejection (C4 category)
        cs05_case = next(c for c in result["cases"] if c["scenario_id"] == "CS05")
        assert cs05_case["policy_decision"] == "DOWNGRADE"
        assert cs05_case["validated_policy"] == "P_ESCALATE_ONLY"
        assert cs05_case["final_state"] == CaseState.ESCALATED.value

        # 7. Check CS06 acquiring gateway internal failure (C5 category)
        cs06_case = next(c for c in result["cases"] if c["scenario_id"] == "CS06")
        assert cs06_case["final_state"] == CaseState.TERMINAL_NO_ACTION.value

        # 8. Check CS09 customer cooldown stop (MAX_ATTEMPTS_EXCEEDED)
        cs09_case = next(c for c in result["cases"] if c["scenario_id"] == "CS09")
        assert cs09_case["final_state"] == CaseState.TERMINAL_NO_ACTION.value

        # 9. Check CS10 already-paid order stop
        cs10_case = next(c for c in result["cases"] if c["scenario_id"] == "CS10")
        assert cs10_case["final_state"] == CaseState.TERMINAL_NO_ACTION.value

        # 10. Check CS12: Eligible Opportunity that is NOT RECOVERED
        cs12_case = next(c for c in result["cases"] if c["scenario_id"] == "CS12")
        assert cs12_case["eligibility"] == "ELIGIBLE"
        assert cs12_case["action_status"] == "EXECUTED"
        assert cs12_case["final_state"] == CaseState.ACTION_EXECUTED.value
        assert cs12_case["evaluation_recovered_amount_inr"] == 0.0

        # 11. Check recovered cases count
        recovered_cases = [c for c in result["cases"] if c["final_state"] == "RECOVERED"]
        assert len(recovered_cases) == 6

        # 12. Check audit events provenance
        audits = (
            await session.scalars(
                select(AuditEventModel).where(AuditEventModel.eval_run_id == eval_run_id)
            )
        ).all()
        assert len(audits) >= 45  # Ingest + Classify + Guardrail + Action + Outcome per case

        # Ensure no fake PAYMENT_CAPTURED audit events exist for evaluation
        assert not any(a.event_type == "PAYMENT_CAPTURED" for a in audits)
        assert not any(a.event_type == "payment.captured" for a in audits)
        assert any(a.event_type == "EVALUATION_RECOVERY_CREDITED" for a in audits)


@pytest.mark.asyncio
async def test_repeated_benchmark_runs_are_independent():
    """Verify that multiple benchmark runs create distinct runs without accumulating cases."""
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        # Run 1
        res1 = await BenchmarkRunner.run_benchmark(session=session)
        run1_id = res1["eval_run_id"]

        # Run 2
        res2 = await BenchmarkRunner.run_benchmark(session=session)
        run2_id = res2["eval_run_id"]

        assert run1_id != run2_id

        # Verify both evaluation_runs rows exist
        runs = (await session.scalars(select(EvaluationRunModel))).all()
        assert len(runs) >= 2

        # Verify run 1 cases and run 2 cases are isolated by eval_run_id
        run1_cases = (
            await session.scalars(
                select(RecoveryCaseModel).where(
                    RecoveryCaseModel.eval_run_id == run1_id,
                    RecoveryCaseModel.case_id.like(f"eval_case_{run1_id}_%"),
                )
            )
        ).all()
        run2_cases = (
            await session.scalars(
                select(RecoveryCaseModel).where(
                    RecoveryCaseModel.eval_run_id == run2_id,
                    RecoveryCaseModel.case_id.like(f"eval_case_{run2_id}_%"),
                )
            )
        ).all()

        assert len(run1_cases) == 15
        assert len(run2_cases) == 15


@pytest.mark.asyncio
async def test_api_benchmark_run_and_latest_endpoints():
    """Verify POST /cases/benchmark/run and GET /cases/benchmark/latest HTTP endpoints."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Trigger benchmark run
        res = await client.post("/cases/benchmark/run")
        assert res.status_code == 200
        data = res.json()

        assert data["status"] == "COMPLETED"
        assert data["case_source"] == "CANONICAL_EVALUATION"
        assert data["total_cases"] == 15
        assert data["eligible_cases"] == 7
        assert data["evaluation_recovered_cases"] == 6
        assert data["escalated_cases"] == 2
        assert data["terminal_cases"] == 6

        eval_run_id = data["eval_run_id"]

        # Check exact metric rates
        assert data["overall_case_recovery_rate_pct"] == 40.0  # 6 / 15
        assert data["eligible_case_recovery_rate_pct"] == 85.71  # 6 / 7
        assert data["portfolio_revenue_recovery_rate_pct"] == round(
            (data["evaluation_recovered_amount_inr"] / data["total_at_risk_amount_inr"]) * 100.0, 2
        )
        assert data["eligible_opportunity_recovery_rate_pct"] == round(
            (data["evaluation_recovered_amount_inr"] / data["eligible_opportunity_amount_inr"])
            * 100.0,
            2,
        )

        # 2. Get latest benchmark metrics
        res_latest = await client.get("/cases/benchmark/latest")
        assert res_latest.status_code == 200
        latest = res_latest.json()
        assert latest["eval_run_id"] == eval_run_id
        assert latest["total_cases"] == 15
        assert latest["recovered_cases"] == 6
        assert latest["case_source"] == "CANONICAL_EVALUATION"

        # 3. Test GET /cases with eval_run_id filter
        res_cases = await client.get(f"/cases?eval_run_id={eval_run_id}")
        assert res_cases.status_code == 200
        cases_list = res_cases.json()
        # 15 scenario cases + 3 setup cooldown cases
        assert len(cases_list) == 18
        for c in cases_list:
            assert c["eval_run_id"] == eval_run_id
            assert c["case_source"] == "CANONICAL_EVALUATION"


@pytest.mark.asyncio
async def test_canonical_and_live_metric_isolation():
    """Verify that live/interactive checkout cases do not alter canonical benchmark metrics."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Run benchmark first
        res_b = await client.post("/cases/benchmark/run")
        assert res_b.status_code == 200
        b_data = res_b.json()
        eval_run_id = b_data["eval_run_id"]

        # Fetch canonical metrics
        res_m_before = await client.get("/cases/benchmark/latest")
        m_before = res_m_before.json()
        assert m_before["total_cases"] == 15
        assert m_before["recovered_cases"] == 6

        # Launch an interactive case in the database
        sessionmaker = get_sessionmaker()
        async with sessionmaker() as session:
            live_case = RecoveryCaseModel(
                case_id="case_pay_live_checkout_test",
                failed_payment_id="pay_live_checkout_test",
                amount=99900,
                currency="INR",
                case_source="LIVE_CHECKOUT",
                state=CaseState.RECOVERED.value,
                recovered_amount=99900,
            )
            session.add(live_case)
            await session.commit()

        # Query benchmark metrics again - must remain strictly isolated!
        res_m_after = await client.get(f"/cases/metrics/summary?eval_run_id={eval_run_id}")
        m_after = res_m_after.json()
        assert m_after["total_cases"] == 15
        assert m_after["recovered_cases"] == 6
        assert m_after["total_recovered_amount_inr"] == m_before["total_recovered_amount_inr"]

        # Query live checkout metrics explicitly
        res_live = await client.get("/cases/metrics/summary?case_source=LIVE_CHECKOUT")
        m_live = res_live.json()
        assert m_live["total_cases"] == 1
        assert m_live["recovered_cases"] == 1
        assert m_live["total_recovered_amount_inr"] == 999.0
