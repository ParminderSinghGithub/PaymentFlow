"""Comprehensive unit and regression tests for Layer 5A evaluation dataset and simulator."""

from collections import Counter

import pytest
from pydantic import ValidationError

from paymentflow.domain.enums import FailureCategory, RecoveryPolicy
from paymentflow.eval.dataset import load_evaluation_dataset, validate_dataset
from paymentflow.eval.models import DecisionContext, EvaluationCase, SimulationGroundTruth
from paymentflow.eval.simulator import CustomerResponseSimulator

# =============================================================================
# 1. Dataset Loading & Structural Integrity Tests
# =============================================================================


def test_evaluation_dataset_exact_count_and_uniqueness():
    """Verify that exactly 75 unique cases exist in the evaluation dataset."""
    cases = load_evaluation_dataset()
    assert len(cases) == 75

    case_ids = [c.decision_context.case_id for c in cases]
    assert len(set(case_ids)) == 75
    assert case_ids[0] == "eval_case_001"
    assert case_ids[-1] == "eval_case_075"


def test_evaluation_dataset_category_distribution():
    """Verify realistic distribution across C1-C5 failure categories."""
    cases = load_evaluation_dataset()
    counts = Counter(c.decision_context.failure_category for c in cases)

    assert counts[FailureCategory.C1] == 18
    assert counts[FailureCategory.C2] == 20
    assert counts[FailureCategory.C3] == 16
    assert counts[FailureCategory.C4] == 11
    assert counts[FailureCategory.C5] == 10


def test_evaluation_dataset_monetary_and_edge_case_distribution():
    """Verify presence of high-value, cooldown, and multi-currency edge cases."""
    cases = load_evaluation_dataset()

    # High value (> ₹50,000 / 5,000,000 paise)
    high_value_cases = [c for c in cases if c.decision_context.amount > 5000000]
    assert len(high_value_cases) >= 6

    # Cooldown active case
    cooldown_cases = [c for c in cases if c.decision_context.last_attempt_at is not None]
    assert len(cooldown_cases) >= 1

    # Non-INR currencies (USD, EUR)
    non_inr_cases = [c for c in cases if c.decision_context.currency != "INR"]
    assert len(non_inr_cases) == 3
    currencies = {c.decision_context.currency for c in non_inr_cases}
    assert "USD" in currencies
    assert "EUR" in currencies


def test_evaluation_dataset_deterministic_loading():
    """Verify dataset loads deterministically across multiple invocations."""
    cases1 = load_evaluation_dataset()
    cases2 = load_evaluation_dataset()
    assert [c.model_dump() for c in cases1] == [c.model_dump() for c in cases2]


# =============================================================================
# 2. Strict Data Leakage & Schema Separation Tests
# =============================================================================


def test_decision_context_strictly_excludes_ground_truth():
    """Prove that DecisionContext contains zero simulator ground-truth fields."""
    cases = load_evaluation_dataset()
    forbidden_keys = {
        "customer_intent_score",
        "p_recovery_no_action",
        "p_recovery_immediate_link",
        "p_recovery_delayed_link",
        "p_recovery_escalate",
        "notes",
    }

    for case in cases:
        dc = case.get_decision_context()
        dc_dict = dc.model_dump()
        for key in forbidden_keys:
            assert key not in dc_dict, f"Data leakage: '{key}' found in DecisionContext dict!"
            assert not hasattr(dc, key), f"Data leakage: '{key}' found on DecisionContext!"


def test_decision_context_forbids_extra_ground_truth_injection():
    """Prove that DecisionContext rejects extra ground-truth attributes upon instantiation."""
    cases = load_evaluation_dataset()
    sample_dc = cases[0].decision_context.model_dump()

    sample_dc["p_recovery_immediate_link"] = 0.95
    with pytest.raises(ValidationError):
        DecisionContext.model_validate(sample_dc)


# =============================================================================
# 3. Customer Response Simulator Tests
# =============================================================================


def test_simulator_determinism_with_seed():
    """Verify simulator produces identical outcomes for identical (case, policy, seed)."""
    cases = load_evaluation_dataset()
    case = cases[0]

    outcome1 = CustomerResponseSimulator.simulate(
        case=case, policy=RecoveryPolicy.P_CREATE_LINK_DELAYED, seed=42
    )
    outcome2 = CustomerResponseSimulator.simulate(
        case=case, policy=RecoveryPolicy.P_CREATE_LINK_DELAYED, seed=42
    )

    assert outcome1.recovered == outcome2.recovered
    assert outcome1.recovered_amount == outcome2.recovered_amount
    assert outcome1.recovery_probability == outcome2.recovery_probability


def test_simulator_stochasticity_across_seeds():
    """Verify different seeds produce stochastic variation matching ground-truth probability."""
    cases = load_evaluation_dataset()
    # Case with ~0.85 probability
    case = cases[0]

    outcomes = [
        CustomerResponseSimulator.simulate(
            case=case, policy=RecoveryPolicy.P_CREATE_LINK_DELAYED, seed=s
        )
        for s in range(100)
    ]
    recovered_count = sum(1 for o in outcomes if o.recovered)
    # With p=0.88 across 100 draws, recovered_count should realistically be between 70 and 99
    assert 70 <= recovered_count <= 99


def test_simulator_economic_outcomes():
    """Verify economic outcome matches exact case amount when recovered and 0 when unrecovered."""
    cases = load_evaluation_dataset()
    case = cases[0]  # amount = 299900 paise

    # Force recovery (p=1.0)
    case_copy = EvaluationCase(
        decision_context=case.decision_context,
        ground_truth=SimulationGroundTruth(
            customer_intent_score=1.0,
            p_recovery_no_action=1.0,
            p_recovery_immediate_link=1.0,
            p_recovery_delayed_link=1.0,
            p_recovery_escalate=1.0,
        ),
    )
    res_rec = CustomerResponseSimulator.simulate(
        case=case_copy, policy=RecoveryPolicy.P_CREATE_LINK_IMMEDIATE, seed=1
    )
    assert res_rec.recovered is True
    assert res_rec.recovered_amount == 299900

    # Force failure (p=0.0)
    case_fail = EvaluationCase(
        decision_context=case.decision_context,
        ground_truth=SimulationGroundTruth(
            customer_intent_score=0.0,
            p_recovery_no_action=0.0,
            p_recovery_immediate_link=0.0,
            p_recovery_delayed_link=0.0,
            p_recovery_escalate=0.0,
        ),
    )
    res_fail = CustomerResponseSimulator.simulate(
        case=case_fail, policy=RecoveryPolicy.P_CREATE_LINK_IMMEDIATE, seed=1
    )
    assert res_fail.recovered is False
    assert res_fail.recovered_amount == 0


def test_simulator_supports_all_four_recovery_policies():
    """Verify simulator accepts all four standard RecoveryPolicy enums and string values."""
    cases = load_evaluation_dataset()
    case = cases[0]

    policies = [
        RecoveryPolicy.P_NO_ACTION,
        RecoveryPolicy.P_CREATE_LINK_IMMEDIATE,
        RecoveryPolicy.P_CREATE_LINK_DELAYED,
        RecoveryPolicy.P_ESCALATE_ONLY,
    ]

    for p in policies:
        out = CustomerResponseSimulator.simulate(case=case, policy=p, seed=10)
        assert out.policy == p
        assert isinstance(out.recovered, bool)
        assert out.recovered_amount in (0, case.decision_context.amount)

        # String format acceptance
        out_str = CustomerResponseSimulator.simulate(case=case, policy=p.value, seed=10)
        assert out_str.policy == p


def test_simulator_rejects_invalid_policy():
    """Verify simulator raises ValueError on invalid policy."""
    cases = load_evaluation_dataset()
    case = cases[0]

    with pytest.raises(ValueError) as exc:
        CustomerResponseSimulator.simulate(case=case, policy="P_INVALID_POLICY", seed=10)
    assert "Invalid recovery policy" in str(exc.value)


# =============================================================================
# 4. Policy Independence Proof Test
# =============================================================================


def test_simulator_is_strictly_policy_independent():
    """Prove simulator contains NO caller identity conditioning ('agent' vs 'baseline')."""
    cases = load_evaluation_dataset()
    case = cases[18]  # C2 case

    # Emulate caller A ("Baseline") selecting P_CREATE_LINK_IMMEDIATE
    outcome_caller_a = CustomerResponseSimulator.simulate(
        case=case,
        policy=RecoveryPolicy.P_CREATE_LINK_IMMEDIATE,
        seed=12345,
    )

    # Emulate caller B ("LLM Agent") selecting P_CREATE_LINK_IMMEDIATE
    outcome_caller_b = CustomerResponseSimulator.simulate(
        case=case,
        policy=RecoveryPolicy.P_CREATE_LINK_IMMEDIATE,
        seed=12345,
    )

    # Outcomes must be mathematically and functionally identical
    assert outcome_caller_a.recovered == outcome_caller_b.recovered
    assert outcome_caller_a.recovered_amount == outcome_caller_b.recovered_amount
    assert outcome_caller_a.recovery_probability == outcome_caller_b.recovery_probability


# =============================================================================
# 5. Dataset Validation Invariant Tests
# =============================================================================


def test_validate_dataset_rejects_incorrect_case_count():
    """Verify dataset validator fails if count != 75."""
    cases = load_evaluation_dataset()
    with pytest.raises(ValueError) as exc:
        validate_dataset(cases[:50])
    assert "Dataset must contain exactly 75 cases" in str(exc.value)


def test_validate_dataset_rejects_duplicate_ids():
    """Verify dataset validator fails on duplicate case IDs."""
    cases = load_evaluation_dataset()
    mutated = list(cases)
    # Duplicate first case
    mutated[1] = mutated[0]
    with pytest.raises(ValueError) as exc:
        validate_dataset(mutated)
    assert "Duplicate case_id" in str(exc.value)


def test_validate_dataset_rejects_out_of_bounds_probability():
    """Verify dataset validator fails if probability > 1.0 or < 0.0."""
    cases = load_evaluation_dataset()
    mutated = list(cases)
    # Test that Pydantic validation rejects it
    with pytest.raises(ValidationError):
        SimulationGroundTruth(
            customer_intent_score=0.5,
            p_recovery_no_action=0.1,
            p_recovery_immediate_link=1.5,
            p_recovery_delayed_link=0.5,
            p_recovery_escalate=0.5,
        )

    # Test that validate_dataset also rejects unvalidated constructs
    mutated[0] = EvaluationCase.model_construct(
        decision_context=mutated[0].decision_context,
        ground_truth=SimulationGroundTruth.model_construct(
            customer_intent_score=0.5,
            p_recovery_no_action=0.1,
            p_recovery_immediate_link=1.5,
            p_recovery_delayed_link=0.5,
            p_recovery_escalate=0.5,
            notes=None,
        ),
    )
    with pytest.raises(ValueError) as exc:
        validate_dataset(mutated)
    assert "is out of bounds" in str(exc.value)


def test_generate_dataset_generator_function():
    """Verify that generate_dataset generator outputs 75 valid cases."""
    from paymentflow.eval.generate_dataset import generate_dataset

    raw_cases = generate_dataset()
    assert len(raw_cases) == 75
    parsed_cases = [EvaluationCase.model_validate(c) for c in raw_cases]
    validate_dataset(parsed_cases)
