"""Deterministic naive baseline recovery policy and Monte Carlo evaluator."""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from paymentflow.domain.eligibility import EligibilityEngine
from paymentflow.domain.enums import (
    EligibilityReasonCode,
    FailureCategory,
    RecoveryPolicy,
)
from paymentflow.domain.models import EligibilityDecision, PaymentContext, PaymentFailureDetails
from paymentflow.eval.dataset import load_evaluation_dataset
from paymentflow.eval.models import (
    BaselineCaseAggregate,
    BaselineDrawResult,
    BaselineEvaluationResult,
    BaselineSummaryAggregate,
    CategoryAggregate,
    DecisionContext,
    EvaluationCase,
)
from paymentflow.eval.simulator import CustomerResponseSimulator

logger = logging.getLogger(__name__)

DEFAULT_BASELINE_RESULTS_PATH = (
    Path(__file__).parent / "data" / "baseline_results.json"
)
DEFAULT_BASELINE_REPORT_PATH = (
    Path(__file__).resolve().parents[3] / "docs" / "BASELINE_EVALUATION_REPORT.md"
)


def evaluate_baseline_eligibility(dc: DecisionContext) -> EligibilityDecision:
    """Evaluate recovery eligibility for a DecisionContext using authoritative domain logic."""
    payment_ctx = PaymentContext(
        payment_id=dc.failed_payment_id,
        order_id=dc.order_id,
        customer_id=dc.customer_id,
        amount=dc.amount,
        currency=dc.currency,
        status="failed",
        method=dc.payment_method,
        failure=PaymentFailureDetails(
            code=dc.failure_code,
            description=dc.failure_description,
            source=dc.failure_source,
            step=dc.failure_step,
            reason=dc.failure_reason,
        ),
        created_at=int(dc.created_at.timestamp()) if dc.created_at else None,
    )

    has_existing_link = dc.last_attempt_at is not None

    return EligibilityEngine.evaluate(
        context=payment_ctx,
        failure_category=dc.failure_category,
        has_existing_recovery_link=has_existing_link,
        customer_attempts_today=dc.prior_failed_count_24h,
    )


class BaselinePolicy:
    """Deterministic naive recovery policy.

    Rule:
    - If case is eligible: P_CREATE_LINK_IMMEDIATE
    - If case is ineligible: P_NO_ACTION
    """

    @classmethod
    def decide(
        cls, context: DecisionContext
    ) -> tuple[RecoveryPolicy, EligibilityDecision]:
        """Determine recovery policy solely based on decision context features."""
        decision = evaluate_baseline_eligibility(context)
        if decision.eligible:
            return RecoveryPolicy.P_CREATE_LINK_IMMEDIATE, decision
        return RecoveryPolicy.P_NO_ACTION, decision


class BaselineEvaluator:
    """Offline deterministic evaluator for the naive baseline recovery policy."""

    def __init__(self, cases: list[EvaluationCase] | None = None) -> None:
        self.cases = cases or load_evaluation_dataset()

    def evaluate(self, draws_per_case: int = 50) -> BaselineEvaluationResult:
        """Run 50 Monte Carlo draws per case using Common Random Numbers (CRN)."""
        logger.info(
            f"Starting baseline evaluation across {len(self.cases)} cases with "
            f"{draws_per_case} draws/case"
        )

        draw_results: list[BaselineDrawResult] = []
        case_aggregates: list[BaselineCaseAggregate] = []

        total_cases = len(self.cases)
        eligible_cases = 0
        ineligible_cases = 0
        immediate_link_cases = 0
        no_action_cases = 0
        ineligibility_reasons: dict[str, int] = {}

        category_data: dict[FailureCategory, dict[str, Any]] = {
            cat: {
                "case_count": 0,
                "eligible_case_count": 0,
                "immediate_link_count": 0,
                "no_action_count": 0,
                "total_draws": 0,
                "recovered_draws": 0,
                "total_opp_paise": 0,
                "total_rec_paise": 0,
            }
            for cat in FailureCategory
        }

        total_opportunity_revenue_paise = 0
        total_recovered_draw_paise = 0
        total_recovered_draws = 0

        for case in self.cases:
            # 1. Baseline decides solely from DecisionContext (Strict No Leakage)
            dc = case.get_decision_context()
            policy, eligibility_dec = BaselinePolicy.decide(dc)

            if eligibility_dec.eligible:
                eligible_cases += 1
                immediate_link_cases += 1
            else:
                ineligible_cases += 1
                no_action_cases += 1
                reason = eligibility_dec.reason_code.value
                ineligibility_reasons[reason] = ineligibility_reasons.get(reason, 0) + 1

            total_opportunity_revenue_paise += dc.amount

            # Update category counts
            cdata = category_data[dc.failure_category]
            cdata["case_count"] += 1
            cdata["total_opp_paise"] += dc.amount
            if eligibility_dec.eligible:
                cdata["eligible_case_count"] += 1
                cdata["immediate_link_count"] += 1
            else:
                cdata["no_action_count"] += 1

            # 2. Run Monte Carlo draws for this case
            case_draw_results: list[BaselineDrawResult] = []
            for draw_index in range(draws_per_case):
                # Using draw_index directly as seed guarantees identical Common Random Numbers (CRN)
                outcome = CustomerResponseSimulator.simulate(
                    case=case, policy=policy, seed=draw_index
                )

                draw_res = BaselineDrawResult(
                    case_id=dc.case_id,
                    draw_index=draw_index,
                    eligible=eligibility_dec.eligible,
                    eligibility_reason_code=eligibility_dec.reason_code.value,
                    policy_id=policy,
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

            # 3. Compute per-case aggregate
            case_rec_count = sum(1 for d in case_draw_results if d.recovered)
            case_total_rec_paise = sum(d.recovered_amount for d in case_draw_results)
            case_expected_paise = case_total_rec_paise // draws_per_case

            # Theoretical probability diagnostic
            match policy:
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
                BaselineCaseAggregate(
                    case_id=dc.case_id,
                    eligible=eligibility_dec.eligible,
                    eligibility_reason_code=eligibility_dec.reason_code.value,
                    policy_id=policy,
                    failure_category=dc.failure_category,
                    amount=dc.amount,
                    currency=dc.currency,
                    draw_count=draws_per_case,
                    recovery_count=case_rec_count,
                    recovery_rate=case_rec_count / draws_per_case,
                    total_recovered_paise=case_total_rec_paise,
                    expected_recovered_revenue=case_expected_paise,
                    theoretical_p_recovery=theo_p,
                )
            )

        # 4. Compute category aggregates
        categories_summary: dict[str, CategoryAggregate] = {}
        for cat, data in category_data.items():
            tot_draws = data["total_draws"]
            rec_draws = data["recovered_draws"]
            rec_rate = rec_draws / tot_draws if tot_draws > 0 else 0.0
            exp_rev = data["total_rec_paise"] // draws_per_case if draws_per_case > 0 else 0

            categories_summary[cat.value] = CategoryAggregate(
                category=cat,
                case_count=data["case_count"],
                eligible_case_count=data["eligible_case_count"],
                immediate_link_count=data["immediate_link_count"],
                no_action_count=data["no_action_count"],
                total_draws=tot_draws,
                recovered_draws=rec_draws,
                recovery_rate=rec_rate,
                total_opportunity_revenue_paise=data["total_opp_paise"],
                expected_recovered_revenue_paise=exp_rev,
            )

        # 5. Compute overall summary aggregate
        total_draws = total_cases * draws_per_case
        overall_rec_rate = (
            total_recovered_draws / total_draws if total_draws > 0 else 0.0
        )
        expected_recovered_revenue_paise = (
            total_recovered_draw_paise // draws_per_case if draws_per_case > 0 else 0
        )

        summary = BaselineSummaryAggregate(
            total_cases=total_cases,
            eligible_cases=eligible_cases,
            ineligible_cases=ineligible_cases,
            immediate_link_cases=immediate_link_cases,
            no_action_cases=no_action_cases,
            total_draws=total_draws,
            recovered_draws=total_recovered_draws,
            overall_recovery_rate=overall_rec_rate,
            total_opportunity_revenue_paise=total_opportunity_revenue_paise,
            expected_recovered_revenue_paise=expected_recovered_revenue_paise,
            categories=categories_summary,
            ineligibility_reasons=ineligibility_reasons,
        )

        return BaselineEvaluationResult(
            metadata={
                "evaluated_at": datetime.now(timezone.utc).isoformat(),
                "dataset_cases": total_cases,
                "draws_per_case": draws_per_case,
                "total_draws": total_draws,
                "seed_convention": "draw_index (0..49) per case_id",
                "simulator": "CustomerResponseSimulator",
                "policy": "Deterministic Naive Baseline",
            },
            summary=summary,
            case_aggregates=case_aggregates,
            draw_results=draw_results,
        )

    def save_results(
        self,
        result: BaselineEvaluationResult,
        file_path: Path | str | None = None,
    ) -> Path:
        """Persist evaluation results as a formatted JSON artifact."""
        target_path = Path(file_path) if file_path else DEFAULT_BASELINE_RESULTS_PATH
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(result.model_dump_json(indent=2))
        logger.info(f"Saved baseline results artifact to {target_path}")
        return target_path

    def generate_report(
        self,
        result: BaselineEvaluationResult,
        report_path: Path | str | None = None,
    ) -> Path:
        """Generate a structured Markdown report of the baseline evaluation."""
        target_path = Path(report_path) if report_path else DEFAULT_BASELINE_REPORT_PATH
        target_path.parent.mkdir(parents=True, exist_ok=True)

        summary = result.summary
        opp_inr = summary.total_opportunity_revenue_paise / 100
        rec_inr = summary.expected_recovered_revenue_paise / 100
        overall_rate_pct = summary.overall_recovery_rate * 100
        rec_share_pct = (rec_inr / opp_inr * 100) if opp_inr > 0 else 0.0

        lines: list[str] = [
            "# Baseline Evaluation Report (Layer 5B)",
            "",
            "## 1. Executive Summary",
            "- **Policy**: Deterministic Naive Baseline "
            "(`if eligible -> P_CREATE_LINK_IMMEDIATE, else -> P_NO_ACTION`)",
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
            "## 2. Policy & Eligibility Distribution",
            "| Metric | Count | Share | Policy Applied |",
            "| :--- | :--- | :--- | :--- |",
            f"| **Eligible Cases** | {summary.eligible_cases} | "
            f"{summary.eligible_cases / summary.total_cases * 100:.1f}% | "
            "`P_CREATE_LINK_IMMEDIATE` |",
            f"| **Ineligible Cases** | {summary.ineligible_cases} | "
            f"{summary.ineligible_cases / summary.total_cases * 100:.1f}% | `P_NO_ACTION` |",
            f"| **Total Cases** | {summary.total_cases} | 100.0% | — |",
            "",
            "### Ineligibility Breakdown",
            "| Reason Code | Count | Explanation |",
            "| :--- | :--- | :--- |",
        ]

        reason_descriptions = {
            EligibilityReasonCode.INELIGIBLE_HIGH_VALUE.value: (
                "Amount > ₹50,000 threshold (requires human escalation)"
            ),
            EligibilityReasonCode.INELIGIBLE_CURRENCY.value: (
                "Unsupported non-INR currency (e.g. USD, EUR)"
            ),
            EligibilityReasonCode.INELIGIBLE_ALREADY_ATTEMPTED.value: (
                "Recovery link previously attempted / active cooldown"
            ),
            EligibilityReasonCode.INELIGIBLE_UNSUPPORTED_FAILURE.value: (
                "C4 Risk / C5 Technical failures ineligible for automated link"
            ),
            EligibilityReasonCode.INELIGIBLE_COOLDOWN.value: (
                "Customer reached maximum daily recovery attempt limit"
            ),
        }

        for reason, count in summary.ineligibility_reasons.items():
            desc = reason_descriptions.get(reason, "Deterministic safety constraint")
            lines.append(f"| `{reason}` | {count} | {desc} |")

        lines.extend([
            "",
            "---",
            "",
            "## 3. Failure Category Breakdown",
            "| Category | Cases | Eligible | Action | Opportunity (₹) | "
            "Expected Recovered (₹) | Recovery Rate |",
            "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
        ])

        for cat_key in ["C1", "C2", "C3", "C4", "C5"]:
            cat_agg = summary.categories[cat_key]
            c_opp = cat_agg.total_opportunity_revenue_paise / 100
            c_rec = cat_agg.expected_recovered_revenue_paise / 100
            c_rate = cat_agg.recovery_rate * 100
            action_desc = f"{cat_agg.immediate_link_count} Link / {cat_agg.no_action_count} None"
            lines.append(
                f"| **{cat_key}** | {cat_agg.case_count} | {cat_agg.eligible_case_count} | "
                f"{action_desc} | ₹{c_opp:,.2f} | ₹{c_rec:,.2f} | {c_rate:.2f}% |"
            )

        lines.extend([
            "",
            "---",
            "",
            "## 4. Evaluation Methodology & Reproducibility",
            "- **Simulator**: `CustomerResponseSimulator` (L5A hardened with SHA-256)",
            "- **Common Random Numbers (CRN)**: Draw seeds are indexed `0..49` for each "
            "`case_id`, allowing future agent evaluations to use identical stochastic draws.",
            "- **Ground-Truth Isolation**: Baseline decision logic had zero access to "
            "`SimulationGroundTruth` (latent customer intent or recovery probabilities).",
            "- **Economic Integrity**: Failed recovery yields ₹0; successful recovery yields "
            "exact case amount.",
        ])

        with open(target_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

        logger.info(f"Generated baseline evaluation report to {target_path}")
        return target_path


def run_baseline_evaluation() -> BaselineEvaluationResult:
    """Execute standard baseline evaluation run, persist results and report."""
    evaluator = BaselineEvaluator()
    result = evaluator.evaluate(draws_per_case=50)
    evaluator.save_results(result)
    evaluator.generate_report(result)
    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    res = run_baseline_evaluation()
    print(f"Evaluated {res.summary.total_cases} cases ({res.summary.total_draws} draws).")
    print(f"Overall Recovery Rate: {res.summary.overall_recovery_rate * 100:.2f}%")
    rec_inr = res.summary.expected_recovered_revenue_paise / 100
    opp_inr = res.summary.total_opportunity_revenue_paise / 100
    print(f"Expected Recovered Revenue: INR {rec_inr:,.2f} / INR {opp_inr:,.2f}")
