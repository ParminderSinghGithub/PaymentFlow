"""Evaluation module for PaymentFlow Recovery Agent."""

from paymentflow.eval.baseline import (
    BaselineEvaluator,
    BaselinePolicy,
    evaluate_baseline_eligibility,
    run_baseline_evaluation,
)
from paymentflow.eval.dataset import load_evaluation_dataset, validate_dataset
from paymentflow.eval.models import (
    BaselineCaseAggregate,
    BaselineDrawResult,
    BaselineEvaluationResult,
    BaselineSummaryAggregate,
    CategoryAggregate,
    DecisionContext,
    EvaluationCase,
    SimulatedOutcome,
    SimulationGroundTruth,
)
from paymentflow.eval.simulator import CustomerResponseSimulator

__all__ = [
    "BaselineCaseAggregate",
    "BaselineDrawResult",
    "BaselineEvaluationResult",
    "BaselineEvaluator",
    "BaselinePolicy",
    "BaselineSummaryAggregate",
    "CategoryAggregate",
    "CustomerResponseSimulator",
    "DecisionContext",
    "EvaluationCase",
    "SimulatedOutcome",
    "SimulationGroundTruth",
    "evaluate_baseline_eligibility",
    "load_evaluation_dataset",
    "run_baseline_evaluation",
    "validate_dataset",
]
