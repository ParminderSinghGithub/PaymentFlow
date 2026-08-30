"""Comprehensive unit and regression tests for Layer 5B Baseline Evaluator."""

from paymentflow.domain.enums import RecoveryPolicy
from paymentflow.eval.baseline import (
    BaselineEvaluator,
    BaselinePolicy,
)
from paymentflow.eval.dataset import load_evaluation_dataset
from paymentflow.eval.models import BaselineEvaluationResult, DecisionContext


def test_baseline_policy_decision_rules():
    """Verify baseline policy assigns P_CREATE_LINK_IMMEDIATE to eligible and P_NO_ACTION."""
    cases = load_evaluation_dataset()

    for case in cases:
        dc = case.get_decision_context()
        policy, decision = BaselinePolicy.decide(dc)

        if decision.eligible:
            assert policy == RecoveryPolicy.P_CREATE_LINK_IMMEDIATE
            assert decision.status.value == "ELIGIBLE"
        else:
            assert policy == RecoveryPolicy.P_NO_ACTION
            assert decision.status.value in {"INELIGIBLE", "REQUIRES_ESCALATION"}


def test_baseline_policy_strictly_no_ground_truth_leakage():
    """Verify baseline policy decision relies purely on DecisionContext without ground truth."""
    cases = load_evaluation_dataset()
    case = cases[0]
    dc = case.get_decision_context()

    # Verify input type is strictly DecisionContext
    assert isinstance(dc, DecisionContext)
    policy1, dec1 = BaselinePolicy.decide(dc)

    # Mutate ground truth in the container case
    mutated_case = case.model_copy(deep=True)
    mutated_case.ground_truth.p_recovery_immediate_link = 0.0
    mutated_case.ground_truth.p_recovery_no_action = 1.0

    # Policy decision must be identical because it only sees DecisionContext
    policy2, dec2 = BaselinePolicy.decide(mutated_case.get_decision_context())
    assert policy1 == policy2
    assert dec1.eligible == dec2.eligible
    assert dec1.reason_code == dec2.reason_code


def test_baseline_evaluation_draw_counts_and_structure():
    """Verify baseline evaluation executes exactly 75 cases x 50 draws = 3,750 draws."""
    evaluator = BaselineEvaluator()
    result = evaluator.evaluate(draws_per_case=50)

    assert isinstance(result, BaselineEvaluationResult)
    assert result.summary.total_cases == 75
    assert len(result.case_aggregates) == 75
    assert len(result.draw_results) == 3750
    assert result.summary.total_draws == 3750


def test_baseline_evaluation_reproducibility():
    """Verify two complete baseline evaluator runs yield identical results."""
    evaluator1 = BaselineEvaluator()
    result1 = evaluator1.evaluate(draws_per_case=50)

    evaluator2 = BaselineEvaluator()
    result2 = evaluator2.evaluate(draws_per_case=50)

    # Summary metrics must match exactly
    assert result1.summary.total_cases == result2.summary.total_cases
    assert result1.summary.eligible_cases == result2.summary.eligible_cases
    assert result1.summary.recovered_draws == result2.summary.recovered_draws
    assert result1.summary.overall_recovery_rate == result2.summary.overall_recovery_rate
    assert (
        result1.summary.expected_recovered_revenue_paise
        == result2.summary.expected_recovered_revenue_paise
    )

    # Every individual draw result must match exactly
    for d1, d2 in zip(result1.draw_results, result2.draw_results, strict=True):
        assert d1.case_id == d2.case_id
        assert d1.draw_index == d2.draw_index
        assert d1.policy_id == d2.policy_id
        assert d1.recovered == d2.recovered
        assert d1.recovered_amount == d2.recovered_amount


def test_baseline_crn_seed_convention_compatibility():
    """Verify seed convention uses draw_index (0..49) consistently across cases."""
    evaluator = BaselineEvaluator()
    result = evaluator.evaluate(draws_per_case=50)

    for i, draw in enumerate(result.draw_results):
        expected_draw_idx = i % 50
        assert draw.draw_index == expected_draw_idx
        assert draw.seed == expected_draw_idx


def test_baseline_economic_integrity_per_draw():
    """Verify economic invariant: recovered amount equals case amount on success, 0 on failure."""
    cases = load_evaluation_dataset()
    case_map = {c.decision_context.case_id: c.decision_context for c in cases}

    evaluator = BaselineEvaluator()
    result = evaluator.evaluate(draws_per_case=50)

    for draw in result.draw_results:
        dc = case_map[draw.case_id]
        if draw.recovered:
            assert draw.recovered_amount == dc.amount
            assert draw.recovered_amount > 0
        else:
            assert draw.recovered_amount == 0


def test_baseline_aggregation_mathematical_consistency():
    """Verify that case and summary aggregates mathematically reconcile with underlying draws."""
    evaluator = BaselineEvaluator()
    result = evaluator.evaluate(draws_per_case=50)

    summary = result.summary
    case_aggregates = result.case_aggregates
    draw_results = result.draw_results

    # 1. Total recovered draws matches sum of case recoveries
    sum_case_recoveries = sum(c.recovery_count for c in case_aggregates)
    assert sum_case_recoveries == summary.recovered_draws
    assert sum_case_recoveries == sum(1 for d in draw_results if d.recovered)

    # 2. Total opportunity matches sum of case amounts
    assert summary.total_opportunity_revenue_paise == sum(c.amount for c in case_aggregates)

    # 3. Overall expected recovered revenue equals sum of case expected revenues
    sum_case_expected_paise = sum(c.expected_recovered_revenue for c in case_aggregates)
    diff = abs(summary.expected_recovered_revenue_paise - sum_case_expected_paise)
    assert diff <= 75

    # 4. Category breakdown cases sum to total cases
    cat_case_sum = sum(cat.case_count for cat in summary.categories.values())
    assert cat_case_sum == summary.total_cases

    # 5. Category breakdown draws sum to total draws
    cat_draws_sum = sum(cat.total_draws for cat in summary.categories.values())
    assert cat_draws_sum == summary.total_draws


def test_baseline_ineligible_reasons_breakdown():
    """Verify expected ineligibility reasons on the 75-case dataset."""
    evaluator = BaselineEvaluator()
    result = evaluator.evaluate(draws_per_case=50)

    reasons = result.summary.ineligibility_reasons
    assert result.summary.eligible_cases == 46
    assert result.summary.ineligible_cases == 29

    # 8 High value (> ₹50,000)
    assert reasons.get("INELIGIBLE_HIGH_VALUE") == 8
    # 3 Multi-currency (USD, EUR)
    assert reasons.get("INELIGIBLE_CURRENCY") == 3
    # 1 Already attempted
    assert reasons.get("INELIGIBLE_ALREADY_ATTEMPTED") == 1
    # 2 Cooldown limits
    assert reasons.get("INELIGIBLE_COOLDOWN") == 2
    # 15 Unsupported failure categories (C4 Risk & C5 Technical)
    assert reasons.get("INELIGIBLE_UNSUPPORTED_FAILURE") == 15


def test_baseline_file_artifact_generation_and_loading(tmp_path):
    """Verify that results and reports are saved and valid."""
    evaluator = BaselineEvaluator()
    result = evaluator.evaluate(draws_per_case=50)

    json_file = tmp_path / "test_baseline_results.json"
    report_file = tmp_path / "TEST_BASELINE_REPORT.md"

    saved_json = evaluator.save_results(result, file_path=json_file)
    assert saved_json.exists()

    saved_report = evaluator.generate_report(result, report_path=report_file)
    assert saved_report.exists()

    # Verify JSON content is parseable and valid BaselineEvaluationResult
    with open(saved_json, encoding="utf-8") as f:
        data = f.read()
    loaded_result = BaselineEvaluationResult.model_validate_json(data)
    assert loaded_result.summary.total_cases == 75
    assert loaded_result.summary.total_draws == 3750

    # Verify Report content contains key sections
    with open(saved_report, encoding="utf-8") as f:
        report_text = f.read()
    assert "# Baseline Evaluation Report (Layer 5B)" in report_text
    assert "Overall Recovery Rate" in report_text
    assert "Failure Category Breakdown" in report_text
