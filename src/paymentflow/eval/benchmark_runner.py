"""Canonical Recovery Workflow Benchmark Execution Engine.

Executes the authentic PaymentFlow recovery decision and guardrail layers
against controlled revenue-at-risk benchmark scenarios, records evaluation
recovery outcomes, and computes run-scoped metrics.
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from paymentflow.db.models import AuditEventModel, EvaluationRunModel, RecoveryCaseModel
from paymentflow.domain.enums import (
    ActorType,
    CaseState,
    FailureCategory,
    PolicyDecision,
    RecoveryPolicy,
)
from paymentflow.domain.models import PaymentContext, PolicyValidationResult
from paymentflow.domain.policy_engine import PolicyGuardrailEngine
from paymentflow.eval.canonical_scenarios import CANONICAL_BENCHMARK_SCENARIOS
from paymentflow.services.recovery_service import RecoveryTriageService

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(timezone.utc)


class EvaluationRecoveryExecutor:
    """Safe, external-side-effect-free recovery executor for benchmark evaluations.

    Implements the same recovery action contract as production execution without
    calling Razorpay APIs or consuming live merchant account Payment Link quotas.
    """

    @classmethod
    async def execute(
        cls,
        session: AsyncSession,
        case: RecoveryCaseModel,
        scenario: dict[str, Any],
        guardrail_result: PolicyValidationResult,
        eval_run_id: str,
    ) -> None:
        """Apply bounded recovery action and record evaluation outcome."""
        effective_policy = guardrail_result.effective_policy
        sc_id = scenario["scenario_id"].lower()
        now = utc_now()

        if guardrail_result.is_approved and effective_policy in {
            RecoveryPolicy.P_CREATE_LINK_IMMEDIATE,
            RecoveryPolicy.P_CREATE_LINK_DELAYED,
        }:
            # Recovery action: Payment Link Generation
            link_id = f"eval_link_{eval_run_id}_{sc_id}"
            short_url = f"https://pay.paymentflow.internal/eval/{eval_run_id}/{sc_id}"

            case.action_status = "EXECUTED"
            case.payment_link_id = link_id
            case.payment_link_status = "issued"
            case.payment_link_short_url = short_url
            case.payment_link_reference_id = f"FP-{case.failed_payment_id}"
            case.state = CaseState.ACTION_EXECUTED.value

            if effective_policy == RecoveryPolicy.P_CREATE_LINK_DELAYED:
                case.scheduled_at = now + timedelta(hours=4)

            # Audit event for action execution
            audit_action = AuditEventModel(
                case_id=case.case_id,
                eval_run_id=eval_run_id,
                event_type="RECOVERY_ACTION_EXECUTED",
                actor=ActorType.SYSTEM.value,
                decision=effective_policy.value,
                policy=effective_policy.value,
                action="CREATE_EVALUATION_PAYMENT_LINK",
                outcome="SUCCESS",
                correlation_id=case.failed_payment_id,
                timestamp=now,
                details={
                    "action_type": "PAYMENT_LINK",
                    "action_status": "EXECUTED",
                    "payment_link_id": link_id,
                    "is_delayed": scenario["is_delayed"],
                    "advisory_provider": "DETERMINISTIC_EVALUATION",
                },
            )
            session.add(audit_action)

            # Evaluation Outcome Resolution
            if scenario.get("evaluation_outcome") == "RECOVERED":
                case.state = CaseState.RECOVERED.value
                case.recovered_amount = case.amount
                case.recovered_payment_id = f"eval_rec_{eval_run_id}_{sc_id}"

                audit_rec = AuditEventModel(
                    case_id=case.case_id,
                    eval_run_id=eval_run_id,
                    event_type="EVALUATION_RECOVERY_CREDITED",
                    actor="evaluation_resolver",
                    decision="RECOVERED",
                    policy=effective_policy.value,
                    action="CREDIT_EVALUATION_RECOVERY",
                    outcome="SUCCESS",
                    correlation_id=case.failed_payment_id,
                    timestamp=now + timedelta(minutes=2),
                    details={
                        "evaluation_outcome": "RECOVERED",
                        "evaluation_recovered_amount": case.amount,
                        "evaluation_recovered_payment_id": case.recovered_payment_id,
                        "reason": "Eligible recovery action executed under benchmark outcome model",
                    },
                )
                session.add(audit_rec)
            else:
                # Eligible opportunity that is not recovered (e.g. CS12 in-flight unpaid)
                case.state = CaseState.ACTION_EXECUTED.value
                audit_unrec = AuditEventModel(
                    case_id=case.case_id,
                    eval_run_id=eval_run_id,
                    event_type="EVALUATION_OUTCOME_RECORDED",
                    actor="evaluation_resolver",
                    decision="NOT_RECOVERED",
                    policy=effective_policy.value,
                    action="AWAIT_RECOVERY_PAYMENT",
                    outcome="IN_FLIGHT",
                    correlation_id=case.failed_payment_id,
                    timestamp=now + timedelta(minutes=2),
                    details={
                        "evaluation_outcome": "NOT_RECOVERED",
                        "reason": "Recovery action validated and scheduled; payment not completed during evaluation window",
                    },
                )
                session.add(audit_unrec)

        elif effective_policy == RecoveryPolicy.P_ESCALATE_ONLY:
            case.action_status = "EXECUTED"
            case.state = CaseState.ESCALATED.value
            audit_esc = AuditEventModel(
                case_id=case.case_id,
                eval_run_id=eval_run_id,
                event_type="ESCALATED",
                actor=ActorType.POLICY_ENGINE.value,
                decision=PolicyDecision.ESCALATE.value,
                policy=effective_policy.value,
                action="ESCALATE_TO_COMPLIANCE",
                outcome="SUCCESS",
                correlation_id=case.failed_payment_id,
                timestamp=now,
                details={
                    "action_type": "ESCALATE",
                    "action_status": "EXECUTED",
                    "evaluation_outcome": "ESCALATED",
                    "reasons": guardrail_result.reasons,
                },
            )
            session.add(audit_esc)

        else:
            # Policy P_NO_ACTION (Rejected by guardrails or classified as terminal)
            case.action_status = "BLOCKED"
            case.state = CaseState.TERMINAL_NO_ACTION.value
            audit_stop = AuditEventModel(
                case_id=case.case_id,
                eval_run_id=eval_run_id,
                event_type="TERMINAL_STOP",
                actor=ActorType.POLICY_ENGINE.value,
                decision=guardrail_result.decision.value,
                policy=effective_policy.value,
                action="STOP_RECOVERY_PIPELINE",
                outcome="BLOCKED",
                correlation_id=case.failed_payment_id,
                timestamp=now,
                details={
                    "action_type": "NONE",
                    "action_status": "BLOCKED",
                    "evaluation_outcome": "NOT_RECOVERED",
                    "reasons": guardrail_result.reasons,
                },
            )
            session.add(audit_stop)

        case.updated_at = now


class BenchmarkRunner:
    """Orchestrates benchmark runs, invoking production decision layers."""

    @classmethod
    async def run_benchmark(
        cls,
        session: AsyncSession,
        eval_run_id: str | None = None,
    ) -> dict[str, Any]:
        """Execute all 15 benchmark scenarios through diagnosis, eligibility, and guardrails."""
        now = utc_now()
        run_id = eval_run_id or f"eval_run_{now.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"

        logger.info(f"Starting benchmark evaluation run: {run_id}")

        # Setup Customer Cooldown State for CS09 in DB
        # Seed 3 prior recovery cases with payment links in last 24h for cust_eval_cs09_frequent
        cooldown_cust = "cust_eval_cs09_frequent"
        for i in range(1, 4):
            prior_case = RecoveryCaseModel(
                case_id=f"eval_setup_{run_id}_prior_{i}",
                failed_payment_id=f"eval_setup_{run_id}_pay_{i}",
                customer_id=cooldown_cust,
                amount=100000,
                currency="INR",
                failure_category="C1",
                payment_link_id=f"eval_setup_{run_id}_link_{i}",
                payment_link_status="issued",
                state=CaseState.ACTION_EXECUTED.value,
                case_source="CANONICAL_EVALUATION",
                eval_run_id=run_id,
                created_at=now - timedelta(hours=i * 2),
                updated_at=now - timedelta(hours=i * 2),
            )
            session.add(prior_case)
        await session.flush()

        executed_cases: list[dict[str, Any]] = []

        for sc in CANONICAL_BENCHMARK_SCENARIOS:
            sc_id = sc["scenario_id"].lower()
            case_id = f"eval_case_{run_id}_{sc_id}"
            failed_pay_id = f"eval_opp_{run_id}_{sc_id}"
            order_id = sc.get("order_id", f"eval_ord_{run_id}_{sc_id}")

            # 1. Controlled Ingestion: Create Case in FAILED_INGESTED
            case = RecoveryCaseModel(
                case_id=case_id,
                failed_payment_id=failed_pay_id,
                order_id=order_id,
                customer_id=sc["customer_id"],
                amount=sc["amount_paise"],
                currency=sc["currency"],
                failure_code=sc["failure_code"],
                failure_description=sc["failure_description"],
                failure_context=sc["failure_context"],
                case_source="CANONICAL_EVALUATION",
                eval_run_id=run_id,
                state=CaseState.FAILED_INGESTED.value,
                created_at=now,
                updated_at=now,
            )
            session.add(case)
            await session.flush()

            # Audit event for ingestion
            audit_ingest = AuditEventModel(
                case_id=case_id,
                eval_run_id=run_id,
                event_type="EVALUATION_EVENT_INGESTED",
                actor=ActorType.SYSTEM.value,
                decision="INGESTED",
                action="INGEST_BENCHMARK_EVENT",
                outcome="SUCCESS",
                correlation_id=failed_pay_id,
                timestamp=now,
                details={
                    "scenario_id": sc["scenario_id"],
                    "scenario_title": sc["title"],
                    "amount_paise": sc["amount_paise"],
                    "currency": sc["currency"],
                },
            )
            session.add(audit_ingest)

            # Setup prior link for CS13 replay check
            if sc.get("setup_has_existing_link"):
                case.payment_link_id = f"eval_link_{run_id}_{sc_id}_prior"
                case.payment_link_status = "issued"

            # 2. Layer 2: Context Enrichment, Failure Classification, and Deterministic Eligibility
            triage_service = RecoveryTriageService(db_session=session)
            await triage_service.enrich_context(case_id=case_id, fetch_from_gateway=False)
            await triage_service.classify_case(case_id=case_id)
            case, eligibility = await triage_service.evaluate_eligibility(case_id=case_id)

            # 3. Advisory Step: Deterministic Evaluation Advisory
            case.ai_policy_id = sc["advisory_policy"]
            case.ai_explanation = sc["advisory_explanation"]

            # Count customer attempts in last 24h
            count_q = select(func.count(RecoveryCaseModel.case_id)).where(
                RecoveryCaseModel.customer_id == case.customer_id,
                RecoveryCaseModel.case_id != case.case_id,
                RecoveryCaseModel.created_at >= (now - timedelta(hours=24)),
                RecoveryCaseModel.payment_link_id.isnot(None),
            )
            cust_attempts_res = await session.execute(count_q)
            customer_attempts_today = cust_attempts_res.scalar() or 0

            # 4. Layer 3: Policy Guardrail Engine Validation
            context = PaymentContext(
                payment_id=case.failed_payment_id,
                order_id=case.order_id,
                customer_id=case.customer_id,
                amount=case.amount,
                currency=case.currency,
                status="paid" if sc.get("setup_order_already_paid") else "failed",
            )

            guardrail_res = PolicyGuardrailEngine.validate(
                context=context,
                requested_policy=sc["advisory_policy"],
                failure_category=FailureCategory(case.failure_category),
                has_existing_recovery_link=bool(case.payment_link_id),
                customer_attempts_today=customer_attempts_today,
                proposed_amount=sc["proposed_amount_paise"],
                proposed_currency=sc["proposed_currency"],
                current_time_utc=now,
            )

            # Reconcile final eligibility with guardrail enforcement
            if guardrail_res.decision == PolicyDecision.REJECT:
                case.eligibility_status = "INELIGIBLE"
                case.eligibility_reason = guardrail_res.reason_code
            elif guardrail_res.decision in {PolicyDecision.ESCALATE, PolicyDecision.DOWNGRADE}:
                if guardrail_res.effective_policy == RecoveryPolicy.P_ESCALATE_ONLY:
                    case.eligibility_status = "REQUIRES_ESCALATION"
                    case.eligibility_reason = guardrail_res.reason_code
            elif sc.get("setup_order_already_paid"):
                case.eligibility_status = "INELIGIBLE"
                case.eligibility_reason = "ORDER_ALREADY_PAID"

            case.validated_policy_id = guardrail_res.effective_policy.value

            # Audit guardrail validation
            audit_guard = AuditEventModel(
                case_id=case_id,
                eval_run_id=run_id,
                event_type="POLICY_GUARDRAIL_VALIDATED",
                actor=ActorType.POLICY_ENGINE.value,
                decision=guardrail_res.decision.value,
                policy=guardrail_res.effective_policy.value,
                guardrail_result=guardrail_res.model_dump(),
                action="VALIDATE_GUARDRAILS",
                outcome="SUCCESS" if guardrail_res.is_approved else "RESTRICTED",
                correlation_id=failed_pay_id,
                timestamp=now,
                details={
                    "guardrails_checked": guardrail_res.guardrails_checked,
                    "reasons": guardrail_res.reasons,
                    "advisory_provider": "DETERMINISTIC_EVALUATION",
                },
            )
            session.add(audit_guard)

            # 5. Layer 4: Bounded Recovery Action Execution
            await EvaluationRecoveryExecutor.execute(
                session=session,
                case=case,
                scenario=sc,
                guardrail_result=guardrail_res,
                eval_run_id=run_id,
            )
            await session.flush()

            executed_cases.append(
                {
                    "case_id": case.case_id,
                    "scenario_id": sc["scenario_id"],
                    "title": sc["title"],
                    "amount_inr": case.amount / 100.0,
                    "category": case.failure_category,
                    "eligibility": case.eligibility_status,
                    "policy_decision": guardrail_res.decision.value,
                    "validated_policy": case.validated_policy_id,
                    "action_status": case.action_status,
                    "final_state": case.state,
                    "evaluation_recovered_amount_inr": (
                        (case.recovered_amount / 100.0) if case.recovered_amount else 0.0
                    ),
                }
            )

        # 6. Compute Run-Scoped Benchmark Metrics across the 15 evaluation cases
        # Filter strictly by this eval_run_id and exclude the setup cases
        cases_q = select(RecoveryCaseModel).where(
            RecoveryCaseModel.eval_run_id == run_id,
            RecoveryCaseModel.case_id.like(f"eval_case_{run_id}_%"),
        )
        cases_res = await session.execute(cases_q)
        all_cases = cases_res.scalars().all()

        total_cases = len(all_cases)
        total_at_risk_amount = sum(c.amount for c in all_cases)

        eligible_cases_list = [c for c in all_cases if c.eligibility_status == "ELIGIBLE"]
        eligible_cases = len(eligible_cases_list)
        eligible_opportunity_amount = sum(c.amount for c in eligible_cases_list)

        recovery_actions_executed = sum(1 for c in all_cases if c.action_status == "EXECUTED")
        recovery_actions_blocked = sum(1 for c in all_cases if c.action_status == "BLOCKED")

        recovered_cases_list = [c for c in all_cases if c.state == CaseState.RECOVERED.value]
        evaluation_recovered_cases = len(recovered_cases_list)
        evaluation_recovered_amount = sum(c.recovered_amount or 0 for c in recovered_cases_list)

        escalated_cases_list = [c for c in all_cases if c.state == CaseState.ESCALATED.value]
        escalated_cases = len(escalated_cases_list)
        escalated_amount = sum(c.amount for c in escalated_cases_list)

        terminal_cases_list = [
            c for c in all_cases if c.state == CaseState.TERMINAL_NO_ACTION.value
        ]
        terminal_cases = len(terminal_cases_list)
        terminal_amount = sum(c.amount for c in terminal_cases_list)

        # Rates (zero-safe)
        overall_case_recovery_rate_pct = (
            round((evaluation_recovered_cases / total_cases) * 100.0, 2) if total_cases > 0 else 0.0
        )
        eligible_case_recovery_rate_pct = (
            round((evaluation_recovered_cases / eligible_cases) * 100.0, 2)
            if eligible_cases > 0
            else 0.0
        )
        portfolio_revenue_recovery_rate_pct = (
            round((evaluation_recovered_amount / total_at_risk_amount) * 100.0, 2)
            if total_at_risk_amount > 0
            else 0.0
        )
        eligible_opportunity_recovery_rate_pct = (
            round((evaluation_recovered_amount / eligible_opportunity_amount) * 100.0, 2)
            if eligible_opportunity_amount > 0
            else 0.0
        )

        # 7. Persist EvaluationRunModel
        eval_run = EvaluationRunModel(
            eval_run_id=run_id,
            created_at=now,
            status="COMPLETED",
            total_cases=total_cases,
            total_at_risk_amount=total_at_risk_amount,
            eligible_cases=eligible_cases,
            eligible_opportunity_amount=eligible_opportunity_amount,
            recovery_actions_executed=recovery_actions_executed,
            recovery_actions_blocked=recovery_actions_blocked,
            evaluation_recovered_cases=evaluation_recovered_cases,
            evaluation_recovered_amount=evaluation_recovered_amount,
            escalated_cases=escalated_cases,
            escalated_amount=escalated_amount,
            terminal_cases=terminal_cases,
            terminal_amount=terminal_amount,
            overall_case_recovery_rate_pct=overall_case_recovery_rate_pct,
            eligible_case_recovery_rate_pct=eligible_case_recovery_rate_pct,
            portfolio_revenue_recovery_rate_pct=portfolio_revenue_recovery_rate_pct,
            eligible_opportunity_recovery_rate_pct=eligible_opportunity_recovery_rate_pct,
            summary_metadata={
                "advisory_provider": "DETERMINISTIC_EVALUATION",
                "case_source": "CANONICAL_EVALUATION",
                "cohort_size": total_cases,
            },
        )
        session.add(eval_run)
        await session.commit()

        logger.info(
            f"Benchmark run {run_id} completed: "
            f"{evaluation_recovered_cases}/{total_cases} recovered "
            f"(₹{evaluation_recovered_amount / 100.0:.2f} / ₹{total_at_risk_amount / 100.0:.2f})."
        )

        return {
            "eval_run_id": run_id,
            "case_source": "CANONICAL_EVALUATION",
            "status": "COMPLETED",
            "total_cases": total_cases,
            "total_at_risk_amount_inr": total_at_risk_amount / 100.0,
            "eligible_cases": eligible_cases,
            "eligible_opportunity_amount_inr": eligible_opportunity_amount / 100.0,
            "recovery_actions_executed": recovery_actions_executed,
            "recovery_actions_blocked": recovery_actions_blocked,
            "evaluation_recovered_cases": evaluation_recovered_cases,
            "evaluation_recovered_amount_inr": evaluation_recovered_amount / 100.0,
            "escalated_cases": escalated_cases,
            "escalated_amount_inr": escalated_amount / 100.0,
            "terminal_cases": terminal_cases,
            "terminal_amount_inr": terminal_amount / 100.0,
            "overall_case_recovery_rate_pct": overall_case_recovery_rate_pct,
            "eligible_case_recovery_rate_pct": eligible_case_recovery_rate_pct,
            "portfolio_revenue_recovery_rate_pct": portfolio_revenue_recovery_rate_pct,
            "eligible_opportunity_recovery_rate_pct": eligible_opportunity_recovery_rate_pct,
            "cases": executed_cases,
        }
