"""Agent policy evaluation contract, deterministic mock provider, and evaluation harness."""

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from paymentflow.domain.enums import (
    FailureCategory,
    PolicyDecision,
    RecoveryPolicy,
)
from paymentflow.domain.models import PaymentContext, PaymentFailureDetails
from paymentflow.domain.policy_engine import PolicyGuardrailEngine
from paymentflow.eval.dataset import load_evaluation_dataset
from paymentflow.eval.models import (
    AgentCaseAggregate,
    AgentCategoryAggregate,
    AgentDecision,
    AgentDecisionValidationRecord,
    AgentDrawResult,
    AgentEvaluationResult,
    AgentOverallAggregate,
    DecisionContext,
    EvaluationCase,
)
from paymentflow.eval.simulator import CustomerResponseSimulator

logger = logging.getLogger(__name__)

DEFAULT_MOCK_AGENT_RESULTS_PATH = Path(__file__).parent / "data" / "mock_agent_results.json"
DEFAULT_AGENT_REPORT_PATH = (
    Path(__file__).resolve().parents[3] / "docs" / "MOCK_AGENT_EVALUATION_REPORT.md"
)


class AgentDecisionProvider(ABC):
    """Abstract interface for recovery policy decision providers (LLM or mock)."""

    @abstractmethod
    def decide(self, context: DecisionContext) -> AgentDecision:
        """Produce a structured recovery policy proposal solely from decision context."""
        ...


class MockAgentDecisionProvider(AgentDecisionProvider):
    """Deterministic mock provider for validating the evaluation contract and harness.

    IMPORTANT ARCHITECTURAL NOTICE:
    This is an offline evaluation scaffold for validating the agent contract and guardrail
    boundaries. It is NOT an AI model and does NOT represent LLM intelligence.
    It has ZERO access to latent customer intent or simulation ground-truth parameters.
    """

    def decide(self, context: DecisionContext) -> AgentDecision:
        """Determine proposed recovery policy deterministically from context features."""
        # High value (> ₹50,000) proposal
        if context.amount > 5_000_000:
            return AgentDecision(
                case_id=context.case_id,
                failure_category=context.failure_category,
                proposed_policy_id=RecoveryPolicy.P_ESCALATE_ONLY,
                reasoning="High-value payment failure exceeding automated threshold; "
                "proposing escalation for manual merchant handling.",
                confidence_score=0.98,
                proposed_amount=context.amount,
                proposed_currency=context.currency,
            )

        match context.failure_category:
            case FailureCategory.C1:
                return AgentDecision(
                    case_id=context.case_id,
                    failure_category=context.failure_category,
                    proposed_policy_id=RecoveryPolicy.P_CREATE_LINK_DELAYED,
                    reasoning="Temporary gateway/issuer outage detected; proposing delayed "
                    "recovery link to allow upstream settlement.",
                    confidence_score=0.92,
                    proposed_amount=context.amount,
                    proposed_currency=context.currency,
                )
            case FailureCategory.C2:
                return AgentDecision(
                    case_id=context.case_id,
                    failure_category=context.failure_category,
                    proposed_policy_id=RecoveryPolicy.P_CREATE_LINK_IMMEDIATE,
                    reasoning="Soft friction / OTP dropoff detected; proposing immediate "
                    "link while customer purchase intent is active.",
                    confidence_score=0.95,
                    proposed_amount=context.amount,
                    proposed_currency=context.currency,
                )
            case FailureCategory.C3:
                return AgentDecision(
                    case_id=context.case_id,
                    failure_category=context.failure_category,
                    proposed_policy_id=RecoveryPolicy.P_CREATE_LINK_DELAYED,
                    reasoning="Hard instrument / balance limit failure; proposing delayed "
                    "link to allow account replenishment.",
                    confidence_score=0.88,
                    proposed_amount=context.amount,
                    proposed_currency=context.currency,
                )
            case FailureCategory.C4:
                return AgentDecision(
                    case_id=context.case_id,
                    failure_category=context.failure_category,
                    proposed_policy_id=RecoveryPolicy.P_ESCALATE_ONLY,
                    reasoning="Business risk / AML rejection detected; automated link forbidden, "
                    "proposing manual risk compliance review.",
                    confidence_score=0.90,
                    proposed_amount=context.amount,
                    proposed_currency=context.currency,
                )
            case FailureCategory.C5:
                return AgentDecision(
                    case_id=context.case_id,
                    failure_category=context.failure_category,
                    proposed_policy_id=RecoveryPolicy.P_NO_ACTION,
                    reasoning="Technical integration error / invalid parameters; "
                    "non-recoverable, proposing no action.",
                    confidence_score=0.99,
                    proposed_amount=context.amount,
                    proposed_currency=context.currency,
                )


class EvaluationSafetyValidator:
    """Authoritative deterministic guardrail validation boundary for agent proposals."""

    @classmethod
    def validate_proposal(
        cls,
        context: DecisionContext,
        proposal: AgentDecision | Any,
    ) -> AgentDecisionValidationRecord:
        """Validate agent proposal against deterministic production guardrails."""
        # 1. Structural / Contract Validation
        if not isinstance(proposal, AgentDecision):
            logger.warning(
                f"Validation FAIL: Malformed proposal for case {context.case_id}. "
                "Applying safe fallback P_NO_ACTION."
            )
            return AgentDecisionValidationRecord(
                case_id=context.case_id,
                agent_proposal=AgentDecision(
                    case_id=context.case_id,
                    failure_category=context.failure_category,
                    proposed_policy_id=RecoveryPolicy.P_NO_ACTION,
                    reasoning="Malformed proposal fallback.",
                    confidence_score=0.0,
                ),
                authorized_policy=RecoveryPolicy.P_NO_ACTION,
                is_approved=False,
                validation_status="MALFORMED_FALLBACK",
                reason_code="INVALID_PROPOSAL_PAYLOAD",
                reasons=["Agent output did not conform to AgentDecision contract."],
                guardrails_checked=["SCHEMA_VALIDATION"],
                fallback_applied=True,
            )

        # 2. Convert DecisionContext to PaymentContext for domain policy engine
        payment_ctx = PaymentContext(
            payment_id=context.failed_payment_id,
            order_id=context.order_id,
            customer_id=context.customer_id,
            amount=context.amount,
            currency=context.currency,
            status="failed",
            method=context.payment_method,
            failure=PaymentFailureDetails(
                code=context.failure_code,
                description=context.failure_description,
                source=context.failure_source,
                step=context.failure_step,
                reason=context.failure_reason,
            ),
            created_at=int(context.created_at.timestamp()) if context.created_at else None,
        )

        has_existing_link = context.last_attempt_at is not None

        # 3. Authoritative Policy & Guardrail Verification
        validation_result = PolicyGuardrailEngine.validate(
            context=payment_ctx,
            requested_policy=proposal.proposed_policy_id,
            failure_category=proposal.failure_category,
            proposed_amount=proposal.proposed_amount,
            proposed_currency=proposal.proposed_currency,
            has_existing_recovery_link=has_existing_link,
            customer_attempts_today=context.prior_failed_count_24h,
        )

        status_str = validation_result.decision.value
        fallback_applied = validation_result.decision != PolicyDecision.APPROVE

        return AgentDecisionValidationRecord(
            case_id=context.case_id,
            agent_proposal=proposal,
            authorized_policy=validation_result.effective_policy,
            is_approved=validation_result.is_approved,
            validation_status=status_str,
            reason_code=validation_result.reason_code,
            reasons=validation_result.reasons,
            guardrails_checked=validation_result.guardrails_checked,
            fallback_applied=fallback_applied,
        )


class AgentEvaluator:
    """Offline deterministic evaluator for agent-based recovery policies."""

    def __init__(
        self,
        provider: AgentDecisionProvider | None = None,
        cases: list[EvaluationCase] | None = None,
    ) -> None:
        self.provider = provider or MockAgentDecisionProvider()
        self.cases = cases or load_evaluation_dataset()

    def evaluate(self, draws_per_case: int = 50) -> AgentEvaluationResult:
        """Run 50 Monte Carlo draws per case using Common Random Numbers (CRN)."""
        logger.info(
            f"Starting agent evaluation across {len(self.cases)} cases with "
            f"{draws_per_case} draws/case"
        )

        decision_records: list[AgentDecisionValidationRecord] = []
        draw_results: list[AgentDrawResult] = []
        case_aggregates: list[AgentCaseAggregate] = []

        total_cases = len(self.cases)
        total_opportunity_revenue_paise = 0
        total_recovered_draw_paise = 0
        total_recovered_draws = 0

        proposal_counts: dict[str, int] = {}
        authorized_counts: dict[str, int] = {}
        fallback_count = 0
        validation_rejection_count = 0

        category_data: dict[FailureCategory, dict[str, Any]] = {
            cat: {
                "case_count": 0,
                "proposed_policy_counts": {},
                "authorized_policy_counts": {},
                "total_draws": 0,
                "recovered_draws": 0,
                "total_opp_paise": 0,
                "total_rec_paise": 0,
            }
            for cat in FailureCategory
        }

        for case in self.cases:
            # 1. Decision Provider receives only DecisionContext (Strict No Leakage)
            dc = case.get_decision_context()
            proposal = self.provider.decide(dc)

            # 2. Authoritative Deterministic Guardrail Validation
            val_record = EvaluationSafetyValidator.validate_proposal(dc, proposal)
            decision_records.append(val_record)

            prop_pol = proposal.proposed_policy_id.value
            auth_pol = val_record.authorized_policy.value

            proposal_counts[prop_pol] = proposal_counts.get(prop_pol, 0) + 1
            authorized_counts[auth_pol] = authorized_counts.get(auth_pol, 0) + 1

            if val_record.fallback_applied:
                fallback_count += 1
            if not val_record.is_approved:
                validation_rejection_count += 1

            total_opportunity_revenue_paise += dc.amount

            # Update category records
            cdata = category_data[dc.failure_category]
            cdata["case_count"] += 1
            cdata["total_opp_paise"] += dc.amount
            cdata["proposed_policy_counts"][prop_pol] = (
                cdata["proposed_policy_counts"].get(prop_pol, 0) + 1
            )
            cdata["authorized_policy_counts"][auth_pol] = (
                cdata["authorized_policy_counts"].get(auth_pol, 0) + 1
            )

            # 3. Run Monte Carlo draws using exact Common Random Numbers (CRN)
            case_draw_results: list[AgentDrawResult] = []
            for draw_index in range(draws_per_case):
                # Using draw_index directly ensures identical random draws across baseline & agent
                outcome = CustomerResponseSimulator.simulate(
                    case=case,
                    policy=val_record.authorized_policy,
                    seed=draw_index,
                )

                draw_res = AgentDrawResult(
                    case_id=dc.case_id,
                    draw_index=draw_index,
                    proposed_policy_id=proposal.proposed_policy_id,
                    authorized_policy=val_record.authorized_policy,
                    is_approved=val_record.is_approved,
                    recovered=outcome.recovered,
                    recovered_amount=outcome.recovered_amount,
                    currency=dc.currency,
                    failure_category=dc.failure_category,
                    time_to_recovery_seconds=outcome.time_to_recovery_seconds,
                    seed=draw_index,
                )
                draw_results.append(draw_res)
                case_draw_results.append(draw_res)

                if outcome.recovered:
                    total_recovered_draws += 1
                    total_recovered_draw_paise += outcome.recovered_amount
                    cdata["recovered_draws"] += 1
                    cdata["total_rec_paise"] += outcome.recovered_amount

                cdata["total_draws"] += 1

            # 4. Compute per-case aggregate
            case_rec_count = sum(1 for d in case_draw_results if d.recovered)
            case_total_rec_paise = sum(d.recovered_amount for d in case_draw_results)
            case_expected_paise = case_total_rec_paise // draws_per_case

            # Theoretical probability diagnostic for authorized policy
            match val_record.authorized_policy:
                case RecoveryPolicy.P_NO_ACTION:
                    theo_p = case.ground_truth.p_recovery_no_action
                case RecoveryPolicy.P_CREATE_LINK_IMMEDIATE:
                    theo_p = case.ground_truth.p_recovery_immediate_link
                case RecoveryPolicy.P_CREATE_LINK_DELAYED:
                    theo_p = case.ground_truth.p_recovery_delayed_link
                case RecoveryPolicy.P_ESCALATE_ONLY:
                    theo_p = case.ground_truth.p_recovery_escalate
                case _:
                    theo_p = None

            case_aggregates.append(
                AgentCaseAggregate(
                    case_id=dc.case_id,
                    failure_category=dc.failure_category,
                    amount=dc.amount,
                    currency=dc.currency,
                    proposed_policy_id=proposal.proposed_policy_id,
                    authorized_policy=val_record.authorized_policy,
                    is_approved=val_record.is_approved,
                    validation_status=val_record.validation_status,
                    draw_count=draws_per_case,
                    recovery_count=case_rec_count,
                    recovery_rate=case_rec_count / draws_per_case,
                    total_recovered_paise=case_total_rec_paise,
                    expected_recovered_revenue=case_expected_paise,
                    theoretical_p_recovery=theo_p,
                )
            )

        # 5. Compute category aggregates
        categories_summary: dict[str, AgentCategoryAggregate] = {}
        for cat, data in category_data.items():
            tot_draws = data["total_draws"]
            rec_draws = data["recovered_draws"]
            rec_rate = rec_draws / tot_draws if tot_draws > 0 else 0.0
            exp_rev = data["total_rec_paise"] // draws_per_case if draws_per_case > 0 else 0

            categories_summary[cat.value] = AgentCategoryAggregate(
                category=cat,
                case_count=data["case_count"],
                proposed_policy_counts=data["proposed_policy_counts"],
                authorized_policy_counts=data["authorized_policy_counts"],
                total_draws=tot_draws,
                recovered_draws=rec_draws,
                recovery_rate=rec_rate,
                total_opportunity_revenue_paise=data["total_opp_paise"],
                expected_recovered_revenue_paise=exp_rev,
            )

        # 6. Overall summary aggregate
        total_draws = total_cases * draws_per_case
        overall_rec_rate = total_recovered_draws / total_draws if total_draws > 0 else 0.0
        expected_recovered_revenue_paise = (
            total_recovered_draw_paise // draws_per_case if draws_per_case > 0 else 0
        )

        summary = AgentOverallAggregate(
            total_cases=total_cases,
            total_draws=total_draws,
            recovered_draws=total_recovered_draws,
            overall_recovery_rate=overall_rec_rate,
            total_opportunity_revenue_paise=total_opportunity_revenue_paise,
            expected_recovered_revenue_paise=expected_recovered_revenue_paise,
            proposal_counts=proposal_counts,
            authorized_policy_counts=authorized_counts,
            fallback_count=fallback_count,
            validation_rejection_count=validation_rejection_count,
            categories=categories_summary,
        )

        provider_name = self.provider.__class__.__name__
        return AgentEvaluationResult(
            metadata={
                "evaluated_at": datetime.now(timezone.utc).isoformat(),
                "dataset_cases": total_cases,
                "draws_per_case": draws_per_case,
                "total_draws": total_draws,
                "seed_convention": "draw_index (0..49) per case_id",
                "simulator": "CustomerResponseSimulator",
                "provider": provider_name,
                "evaluation_layer": "Layer 5C — Mock Agent Evaluation Scaffold",
            },
            summary=summary,
            decision_records=decision_records,
            case_aggregates=case_aggregates,
            draw_results=draw_results,
        )

    def save_results(
        self,
        result: AgentEvaluationResult,
        file_path: Path | str | None = None,
    ) -> Path:
        """Persist evaluation results as a formatted JSON artifact."""
        target_path = Path(file_path) if file_path else DEFAULT_MOCK_AGENT_RESULTS_PATH
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(result.model_dump_json(indent=2))
        logger.info(f"Saved agent evaluation results artifact to {target_path}")
        return target_path

    def generate_report(
        self,
        result: AgentEvaluationResult,
        report_path: Path | str | None = None,
    ) -> Path:
        """Generate a structured Markdown report of the mock agent evaluation."""
        target_path = Path(report_path) if report_path else DEFAULT_AGENT_REPORT_PATH
        target_path.parent.mkdir(parents=True, exist_ok=True)

        summary = result.summary
        opp_inr = summary.total_opportunity_revenue_paise / 100
        rec_inr = summary.expected_recovered_revenue_paise / 100
        overall_rate_pct = summary.overall_recovery_rate * 100
        rec_share_pct = (rec_inr / opp_inr * 100) if opp_inr > 0 else 0.0

        lines: list[str] = [
            "# Mock Agent Evaluation Report (Layer 5C)",
            "",
            "> **IMPORTANT NOTICE**: This evaluation uses a deterministic mock provider "
            "as an architectural scaffold to validate the Agent Decision Contract, "
            "Common Random Numbers (CRN), and deterministic guardrail boundaries. "
            "It does **NOT** represent LLM benchmark results.",
            "",
            "## 1. Executive Summary",
            f"- **Provider**: `{result.metadata['provider']}`",
            f"- **Dataset Size**: {summary.total_cases} synthetic failed payment cases",
            f"- **Monte Carlo Draws**: {summary.total_draws:,} total simulations "
            f"({result.metadata['draws_per_case']} draws/case)",
            f"- **Overall Recovery Rate**: {overall_rate_pct:.2f}% "
            f"({summary.recovered_draws:,} / {summary.total_draws:,} draws recovered)",
            f"- **Total Opportunity Value**: ₹{opp_inr:,.2f}",
            f"- **Expected Recovered Revenue**: ₹{rec_inr:,.2f} "
            f"({rec_share_pct:.2f}% of opportunity)",
            "",
            "---",
            "",
            "## 2. Policy Proposals vs. Authorized Actions",
            "| Policy | Proposed by Agent | Authorized by Guardrails | Rejections / Downgrades |",
            "| :--- | :--- | :--- | :--- |",
        ]

        all_policies = [
            RecoveryPolicy.P_CREATE_LINK_IMMEDIATE.value,
            RecoveryPolicy.P_CREATE_LINK_DELAYED.value,
            RecoveryPolicy.P_ESCALATE_ONLY.value,
            RecoveryPolicy.P_NO_ACTION.value,
        ]

        for p_key in all_policies:
            prop_n = summary.proposal_counts.get(p_key, 0)
            auth_n = summary.authorized_policy_counts.get(p_key, 0)
            diff = prop_n - auth_n
            diff_str = f"{diff:+d}" if diff != 0 else "0"
            lines.append(f"| `{p_key}` | {prop_n} | {auth_n} | {diff_str} |")

        lines.extend(
            [
                "",
                f"- **Total Guardrail Fallbacks / Downgrades**: {summary.fallback_count}",
                f"- **Total Rejections**: {summary.validation_rejection_count}",
                "",
                "---",
                "",
                "## 3. Failure Category Breakdown",
                "| Category | Cases | Proposed | Authorized | Opportunity (₹) | "
                "Expected Recovered (₹) | Recovery Rate |",
                "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
            ]
        )

        for cat_key in ["C1", "C2", "C3", "C4", "C5"]:
            cat_agg = summary.categories[cat_key]
            c_opp = cat_agg.total_opportunity_revenue_paise / 100
            c_rec = cat_agg.expected_recovered_revenue_paise / 100
            c_rate = cat_agg.recovery_rate * 100
            prop_str = ", ".join(
                f"{k.split('_')[-1]}:{v}" for k, v in cat_agg.proposed_policy_counts.items()
            )
            auth_str = ", ".join(
                f"{k.split('_')[-1]}:{v}" for k, v in cat_agg.authorized_policy_counts.items()
            )
            lines.append(
                f"| **{cat_key}** | {cat_agg.case_count} | {prop_str} | {auth_str} | "
                f"₹{c_opp:,.2f} | ₹{c_rec:,.2f} | {c_rate:.2f}% |"
            )

        lines.extend(
            [
                "",
                "---",
                "",
                "## 4. Evaluation Methodology & Verification",
                "- **Simulator**: `CustomerResponseSimulator` (L5A hardened with SHA-256)",
                "- **CRN Alignment**: Uses identical `seed = draw_index` ($0 \\dots 49$) "
                "per `case_id` to hold the stochastic customer response constant.",
                "- **Guardrail Enforcement**: Agent proposals cannot bypass eligibility, "
                "cooldowns, or high-value constraints.",
                "- **Economic Integrity**: Failed recovery yields ₹0; successful recovery yields "
                "exact case amount.",
            ]
        )

        with open(target_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

        logger.info(f"Generated agent evaluation report to {target_path}")
        return target_path


def run_agent_evaluation(
    provider: AgentDecisionProvider | None = None,
) -> AgentEvaluationResult:
    """Execute standard mock agent evaluation run, persist results and report."""
    evaluator = AgentEvaluator(provider=provider)
    result = evaluator.evaluate(draws_per_case=50)
    evaluator.save_results(result)
    evaluator.generate_report(result)
    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    res = run_agent_evaluation()
    print(f"Evaluated {res.summary.total_cases} cases ({res.summary.total_draws} draws).")
    print(f"Overall Recovery Rate: {res.summary.overall_recovery_rate * 100:.2f}%")
    rec_inr = res.summary.expected_recovered_revenue_paise / 100
    opp_inr = res.summary.total_opportunity_revenue_paise / 100
    print(f"Expected Recovered Revenue: INR {rec_inr:,.2f} / INR {opp_inr:,.2f}")
