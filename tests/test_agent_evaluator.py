"""Comprehensive unit and regression tests for Layer 5C Agent Evaluator & Safety Guardrails."""

import pytest
from pydantic import ValidationError

from paymentflow.domain.enums import FailureCategory, RecoveryPolicy
from paymentflow.eval.agent_evaluator import (
    AgentDecisionProvider,
    AgentEvaluator,
    EvaluationSafetyValidator,
    MockAgentDecisionProvider,
)
from paymentflow.eval.dataset import load_evaluation_dataset
from paymentflow.eval.models import (
    AgentDecision,
    AgentEvaluationResult,
    DecisionContext,
)
from paymentflow.eval.simulator import CustomerResponseSimulator

# =============================================================================
# 1. Agent Contract & Schema Validation Tests
# =============================================================================


def test_agent_decision_contract_valid():
    """Verify valid AgentDecision instantiation and field constraints."""
    decision = AgentDecision(
        case_id="case_001",
        failure_category=FailureCategory.C2,
        proposed_policy_id=RecoveryPolicy.P_CREATE_LINK_IMMEDIATE,
        reasoning="User friction observed; recommending immediate link.",
        confidence_score=0.95,
        proposed_amount=499900,
        proposed_currency="INR",
    )
    assert decision.case_id == "case_001"
    assert decision.failure_category == FailureCategory.C2
    assert decision.proposed_policy_id == RecoveryPolicy.P_CREATE_LINK_IMMEDIATE
    assert decision.confidence_score == 0.95


def test_agent_decision_contract_rejects_unknown_policy():
    """Verify AgentDecision rejects unknown or unallowed recovery policies."""
    with pytest.raises(ValidationError):
        AgentDecision(
            case_id="case_001",
            failure_category=FailureCategory.C1,
            proposed_policy_id="P_UNKNOWN_INVALID_POLICY",  # type: ignore
            reasoning="Invalid policy test.",
            confidence_score=0.9,
        )


def test_agent_decision_contract_rejects_extra_fields():
    """Verify AgentDecision rejects unexpected extra fields (strict schema)."""
    with pytest.raises(ValidationError):
        AgentDecision(
            case_id="case_001",
            failure_category=FailureCategory.C1,
            proposed_policy_id=RecoveryPolicy.P_CREATE_LINK_DELAYED,
            reasoning="Extra field test.",
            confidence_score=0.9,
            unauthorized_field="malicious_payload",  # type: ignore
        )


def test_agent_decision_contract_confidence_bounds():
    """Verify confidence score must be between 0.0 and 1.0."""
    with pytest.raises(ValidationError):
        AgentDecision(
            case_id="case_001",
            failure_category=FailureCategory.C1,
            proposed_policy_id=RecoveryPolicy.P_CREATE_LINK_DELAYED,
            reasoning="Out of bounds test.",
            confidence_score=1.5,
        )


# =============================================================================
# 2. Mock Agent Decision Provider Tests
# =============================================================================


def test_mock_provider_deterministic_decisions():
    """Verify MockAgentDecisionProvider produces identical outputs for identical context."""
    provider = MockAgentDecisionProvider()
    cases = load_evaluation_dataset()
    case = cases[0]
    dc = case.get_decision_context()

    dec1 = provider.decide(dc)
    dec2 = provider.decide(dc)

    assert dec1.case_id == dec2.case_id
    assert dec1.proposed_policy_id == dec2.proposed_policy_id
    assert dec1.failure_category == dec2.failure_category
    assert dec1.confidence_score == dec2.confidence_score
    assert dec1.reasoning == dec2.reasoning


def test_mock_provider_strictly_no_ground_truth_leakage():
    """Verify mock agent decision is invariant to underlying SimulationGroundTruth."""
    provider = MockAgentDecisionProvider()
    cases = load_evaluation_dataset()
    case = cases[0]

    # Mutate simulation ground truth
    mutated_case = case.model_copy(deep=True)
    mutated_case.ground_truth.p_recovery_immediate_link = 0.0
    mutated_case.ground_truth.p_recovery_delayed_link = 0.0
    mutated_case.ground_truth.p_recovery_no_action = 1.0

    dec1 = provider.decide(case.get_decision_context())
    dec2 = provider.decide(mutated_case.get_decision_context())

    assert dec1 == dec2


# =============================================================================
# 3. Deterministic Safety Boundary & Guardrail Tests
# =============================================================================


def test_safety_validator_approves_safe_proposal():
    """Verify valid, eligible proposal is approved."""
    cases = load_evaluation_dataset()
    # Case 0 is standard C1 INR payment <= ₹50,000
    case = cases[0]
    dc = case.get_decision_context()

    proposal = AgentDecision(
        case_id=dc.case_id,
        failure_category=dc.failure_category,
        proposed_policy_id=RecoveryPolicy.P_CREATE_LINK_DELAYED,
        reasoning="Valid delayed link proposal.",
        proposed_amount=dc.amount,
        proposed_currency=dc.currency,
    )

    record = EvaluationSafetyValidator.validate_proposal(dc, proposal)
    assert record.is_approved is True
    assert record.authorized_policy == RecoveryPolicy.P_CREATE_LINK_DELAYED
    assert record.validation_status == "APPROVE"
    assert record.fallback_applied is False


def test_safety_validator_blocks_high_value_link_proposal():
    """Verify proposing Payment Link for high-value case (> ₹50,000) escalates."""
    cases = load_evaluation_dataset()
    # Find a high-value case (> ₹50,000)
    hv_case = next(c for c in cases if c.decision_context.amount > 5_000_000)
    dc = hv_case.get_decision_context()

    # Agent improperly proposes automated immediate link
    unsafe_proposal = AgentDecision(
        case_id=dc.case_id,
        failure_category=dc.failure_category,
        proposed_policy_id=RecoveryPolicy.P_CREATE_LINK_IMMEDIATE,
        reasoning="Unsafe high-value link proposal.",
        proposed_amount=dc.amount,
        proposed_currency=dc.currency,
    )

    record = EvaluationSafetyValidator.validate_proposal(dc, unsafe_proposal)
    assert record.is_approved is False
    assert record.authorized_policy == RecoveryPolicy.P_ESCALATE_ONLY
    assert record.validation_status == "ESCALATE"
    assert record.reason_code == "HIGH_VALUE_THRESHOLD"
    assert record.fallback_applied is True


def test_safety_validator_blocks_unsupported_c4_link_proposal():
    """Verify proposing Payment Link for C4 Risk failure downgrades to escalation."""
    cases = load_evaluation_dataset()
    c4_case = next(
        c
        for c in cases
        if c.decision_context.failure_category == FailureCategory.C4
        and c.decision_context.amount <= 5_000_000
    )
    dc = c4_case.get_decision_context()

    unsafe_proposal = AgentDecision(
        case_id=dc.case_id,
        failure_category=dc.failure_category,
        proposed_policy_id=RecoveryPolicy.P_CREATE_LINK_IMMEDIATE,
        reasoning="Unsafe C4 link proposal.",
        proposed_amount=dc.amount,
        proposed_currency=dc.currency,
    )

    record = EvaluationSafetyValidator.validate_proposal(dc, unsafe_proposal)
    assert record.is_approved is False
    assert record.authorized_policy == RecoveryPolicy.P_ESCALATE_ONLY
    assert record.validation_status == "DOWNGRADE"
    assert record.fallback_applied is True


def test_safety_validator_blocks_unsupported_c5_link_proposal():
    """Verify proposing Payment Link for C5 Technical failure downgrades to no action."""
    cases = load_evaluation_dataset()
    c5_case = next(c for c in cases if c.decision_context.failure_category == FailureCategory.C5)
    dc = c5_case.get_decision_context()

    unsafe_proposal = AgentDecision(
        case_id=dc.case_id,
        failure_category=dc.failure_category,
        proposed_policy_id=RecoveryPolicy.P_CREATE_LINK_IMMEDIATE,
        reasoning="Unsafe C5 link proposal.",
        proposed_amount=dc.amount,
        proposed_currency=dc.currency,
    )

    record = EvaluationSafetyValidator.validate_proposal(dc, unsafe_proposal)
    assert record.is_approved is False
    assert record.authorized_policy == RecoveryPolicy.P_NO_ACTION
    assert record.validation_status == "DOWNGRADE"
    assert record.fallback_applied is True


def test_safety_validator_blocks_currency_mutation_attempt():
    """Verify proposed currency mutation is rejected and falls back safely."""
    cases = load_evaluation_dataset()
    case = cases[0]
    dc = case.get_decision_context()

    mutated_currency_proposal = AgentDecision(
        case_id=dc.case_id,
        failure_category=dc.failure_category,
        proposed_policy_id=RecoveryPolicy.P_CREATE_LINK_DELAYED,
        reasoning="Currency tampering attempt.",
        proposed_amount=dc.amount,
        proposed_currency="USD",  # Original is INR
    )

    record = EvaluationSafetyValidator.validate_proposal(dc, mutated_currency_proposal)
    assert record.is_approved is False
    assert record.authorized_policy == RecoveryPolicy.P_NO_ACTION
    assert record.validation_status == "REJECT"
    assert record.reason_code == "CURRENCY_MUTATION_FORBIDDEN"


def test_safety_validator_blocks_amount_mutation_attempt():
    """Verify proposed amount mutation is rejected and falls back safely."""
    cases = load_evaluation_dataset()
    case = cases[0]
    dc = case.get_decision_context()

    mutated_amount_proposal = AgentDecision(
        case_id=dc.case_id,
        failure_category=dc.failure_category,
        proposed_policy_id=RecoveryPolicy.P_CREATE_LINK_DELAYED,
        reasoning="Amount tampering attempt.",
        proposed_amount=dc.amount + 1000,  # Mutated amount
        proposed_currency=dc.currency,
    )

    record = EvaluationSafetyValidator.validate_proposal(dc, mutated_amount_proposal)
    assert record.is_approved is False
    assert record.authorized_policy == RecoveryPolicy.P_NO_ACTION
    assert record.validation_status == "REJECT"
    assert record.reason_code == "AMOUNT_MUTATION_FORBIDDEN"


def test_safety_validator_handles_malformed_proposal():
    """Verify malformed or invalid proposal structure fails closed to P_NO_ACTION."""
    cases = load_evaluation_dataset()
    dc = cases[0].get_decision_context()

    record = EvaluationSafetyValidator.validate_proposal(dc, "non_agent_decision_object")  # type: ignore
    assert record.is_approved is False
    assert record.authorized_policy == RecoveryPolicy.P_NO_ACTION
    assert record.validation_status == "MALFORMED_FALLBACK"
    assert record.fallback_applied is True


# =============================================================================
# 4. Evaluator & CRN Compatibility Tests
# =============================================================================


def test_agent_evaluator_draw_counts_and_structure():
    """Verify agent evaluator executes exactly 75 cases x 50 draws = 3,750 simulations."""
    evaluator = AgentEvaluator()
    result = evaluator.evaluate(draws_per_case=50)

    assert isinstance(result, AgentEvaluationResult)
    assert result.summary.total_cases == 75
    assert len(result.decision_records) == 75
    assert len(result.case_aggregates) == 75
    assert len(result.draw_results) == 3750
    assert result.summary.total_draws == 3750


def test_agent_evaluator_reproducibility():
    """Verify two complete agent evaluator runs yield identical results."""
    evaluator1 = AgentEvaluator()
    result1 = evaluator1.evaluate(draws_per_case=50)

    evaluator2 = AgentEvaluator()
    result2 = evaluator2.evaluate(draws_per_case=50)

    assert result1.summary.total_cases == result2.summary.total_cases
    assert result1.summary.recovered_draws == result2.summary.recovered_draws
    assert result1.summary.overall_recovery_rate == result2.summary.overall_recovery_rate
    assert (
        result1.summary.expected_recovered_revenue_paise
        == result2.summary.expected_recovered_revenue_paise
    )

    for d1, d2 in zip(result1.draw_results, result2.draw_results, strict=True):
        assert d1.case_id == d2.case_id
        assert d1.draw_index == d2.draw_index
        assert d1.authorized_policy == d2.authorized_policy
        assert d1.recovered == d2.recovered
        assert d1.recovered_amount == d2.recovered_amount


def test_crn_seed_convention_alignment_with_simulator():
    """Verify agent evaluation seed conventions match CustomerResponseSimulator directly."""
    cases = load_evaluation_dataset()
    case = cases[0]

    # Run direct simulator call on draw 5 with P_CREATE_LINK_DELAYED
    direct_outcome = CustomerResponseSimulator.simulate(
        case=case, policy=RecoveryPolicy.P_CREATE_LINK_DELAYED, seed=5
    )

    # Run evaluator on single case
    evaluator = AgentEvaluator(cases=[case])
    eval_result = evaluator.evaluate(draws_per_case=50)
    draw_5_result = eval_result.draw_results[5]

    assert draw_5_result.seed == 5
    assert draw_5_result.recovered == direct_outcome.recovered
    assert draw_5_result.recovered_amount == direct_outcome.recovered_amount


def test_agent_aggregation_consistency():
    """Verify that case and summary aggregates mathematically reconcile with underlying draws."""
    evaluator = AgentEvaluator()
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

    # 3. Overall expected recovered revenue equals sum of case expected revenues (within 75 paise)
    sum_case_expected_paise = sum(c.expected_recovered_revenue for c in case_aggregates)
    assert abs(summary.expected_recovered_revenue_paise - sum_case_expected_paise) <= 75


def test_agent_custom_provider_injection():
    """Verify custom AgentDecisionProvider can be injected into AgentEvaluator cleanly."""

    class StaticImmediateLinkProvider(AgentDecisionProvider):
        def decide(self, context: DecisionContext) -> AgentDecision:
            return AgentDecision(
                case_id=context.case_id,
                failure_category=context.failure_category,
                proposed_policy_id=RecoveryPolicy.P_CREATE_LINK_IMMEDIATE,
                reasoning="Static immediate link for testing.",
                proposed_amount=context.amount,
                proposed_currency=context.currency,
            )

    evaluator = AgentEvaluator(provider=StaticImmediateLinkProvider())
    result = evaluator.evaluate(draws_per_case=10)

    assert result.metadata["provider"] == "StaticImmediateLinkProvider"
    assert result.summary.total_draws == 750
    # Guardrails should still block high-value, C4, C5, non-INR, etc.
    assert result.summary.fallback_count > 0


def test_agent_file_artifact_generation_and_loading(tmp_path):
    """Verify mock agent results and markdown reports are generated, saved, and loaded cleanly."""
    from paymentflow.eval.models import AgentEvaluationResult

    evaluator = AgentEvaluator()
    result = evaluator.evaluate(draws_per_case=50)

    json_file = tmp_path / "test_agent_results.json"
    report_file = tmp_path / "TEST_MOCK_AGENT_REPORT.md"

    saved_json = evaluator.save_results(result, file_path=json_file)
    assert saved_json.exists()

    saved_report = evaluator.generate_report(result, report_path=report_file)
    assert saved_report.exists()

    # Verify JSON content is parseable and valid AgentEvaluationResult
    with open(saved_json, encoding="utf-8") as f:
        data = f.read()
    loaded_result = AgentEvaluationResult.model_validate_json(data)
    assert loaded_result.summary.total_cases == 75
    assert loaded_result.summary.total_draws == 3750

    # Verify Report content contains key sections
    with open(saved_report, encoding="utf-8") as f:
        report_text = f.read()
    assert "# Mock Agent Evaluation Report (Layer 5C)" in report_text
    assert "Policy Proposals vs. Authorized Actions" in report_text
    assert "Failure Category Breakdown" in report_text


def test_run_agent_evaluation_function():
    """Verify run_agent_evaluation executes and produces standard artifacts."""
    from paymentflow.eval.agent_evaluator import run_agent_evaluation

    res = run_agent_evaluation()
    assert res.summary.total_cases == 75
    assert res.summary.total_draws == 3750
    assert len(res.decision_records) == 75
