"""Evaluation module for PaymentFlow Recovery Agent."""

from paymentflow.eval.agent_evaluator import (
    AgentDecisionProvider,
    AgentEvaluator,
    EvaluationSafetyValidator,
    MockAgentDecisionProvider,
    run_agent_evaluation,
)
from paymentflow.eval.baseline import (
    BaselineEvaluator,
    BaselinePolicy,
    evaluate_baseline_eligibility,
    run_baseline_evaluation,
)
from paymentflow.eval.dataset import load_evaluation_dataset, validate_dataset
from paymentflow.eval.llm_provider import (
    LLMAgentDecisionProvider,
    LLMTelemetry,
)
from paymentflow.eval.models import (
    AgentCaseAggregate,
    AgentCategoryAggregate,
    AgentDecision,
    AgentDecisionValidationRecord,
    AgentDrawResult,
    AgentEvaluationResult,
    AgentOverallAggregate,
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
    "AgentCaseAggregate",
    "AgentCategoryAggregate",
    "AgentDecision",
    "AgentDecisionProvider",
    "AgentDecisionValidationRecord",
    "AgentDrawResult",
    "AgentEvaluationResult",
    "AgentEvaluator",
    "AgentOverallAggregate",
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
    "EvaluationSafetyValidator",
    "LLMAgentDecisionProvider",
    "LLMTelemetry",
    "MockAgentDecisionProvider",
    "SimulatedOutcome",
    "SimulationGroundTruth",
    "evaluate_baseline_eligibility",
    "load_evaluation_dataset",
    "run_agent_evaluation",
    "run_baseline_evaluation",
    "validate_dataset",
]
