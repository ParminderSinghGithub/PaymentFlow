"""Evaluation domain models and ground-truth separation schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from paymentflow.domain.enums import FailureCategory, RecoveryPolicy


class DecisionContext(BaseModel):
    """Features legitimately visible to an agent or policy at decision time.

    STRICT GUARANTEE: Does NOT contain any simulator ground truth, response probabilities,
    or latent customer intent variables.
    """

    model_config = ConfigDict(extra="forbid")

    case_id: str
    failed_payment_id: str
    order_id: str | None = None
    customer_id: str | None = None
    amount: int  # in paise
    currency: str = "INR"
    payment_method: str | None = None
    failure_code: str | None = None
    failure_description: str | None = None
    failure_source: str | None = None
    failure_step: str | None = None
    failure_reason: str | None = None
    failure_category: FailureCategory
    customer_tenure_months: int = 0
    prior_failed_count_24h: int = 0
    prior_recovered_count_24h: int = 0
    created_at: datetime
    last_attempt_at: datetime | None = None


class SimulationGroundTruth(BaseModel):
    """Ground truth simulation parameters for evaluation only.

    STRICT GUARANTEE: Kept strictly isolated from agent and baseline decision contexts.
    """

    model_config = ConfigDict(extra="forbid")

    customer_intent_score: float = Field(
        ge=0.0, le=1.0, description="Latent propensity of customer to complete payment"
    )
    p_recovery_no_action: float = Field(
        ge=0.0, le=1.0, description="Natural recovery probability without merchant intervention"
    )
    p_recovery_immediate_link: float = Field(
        ge=0.0, le=1.0, description="Recovery probability if immediate Payment Link is sent"
    )
    p_recovery_delayed_link: float = Field(
        ge=0.0, le=1.0, description="Recovery probability if delayed Payment Link is sent"
    )
    p_recovery_escalate: float = Field(
        ge=0.0, le=1.0, description="Recovery probability if escalated for manual handling"
    )
    notes: str | None = None


class EvaluationCase(BaseModel):
    """Synthetic failed payment case with separated decision context and simulation ground truth."""

    model_config = ConfigDict(extra="forbid")

    decision_context: DecisionContext
    ground_truth: SimulationGroundTruth

    def get_decision_context(self) -> DecisionContext:
        """Return the decision context, strictly excluding all ground truth fields."""
        return self.decision_context


class SimulatedOutcome(BaseModel):
    """Deterministic result of a simulated customer response to an applied recovery policy."""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    policy: RecoveryPolicy
    recovered: bool
    recovered_amount: int  # in paise (0 or case.decision_context.amount)
    recovery_probability: float
    time_to_recovery_seconds: int | None = None
    seed: int | None = None


class BaselineDrawResult(BaseModel):
    """Result of a single Monte Carlo draw for a case under the baseline policy."""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    draw_index: int
    eligible: bool
    eligibility_reason_code: str
    policy_id: RecoveryPolicy
    recovered: bool
    recovered_amount: int  # in paise
    currency: str
    failure_category: FailureCategory
    time_to_recovery_seconds: int | None = None
    seed: int


class BaselineCaseAggregate(BaseModel):
    """Aggregated Monte Carlo evaluation results for a single case under the baseline policy."""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    eligible: bool
    eligibility_reason_code: str
    policy_id: RecoveryPolicy
    failure_category: FailureCategory
    amount: int  # in paise
    currency: str
    draw_count: int
    recovery_count: int
    recovery_rate: float
    total_recovered_paise: int
    expected_recovered_revenue: int  # in paise (mean recovered amount across draws)
    theoretical_p_recovery: float | None = None


class CategoryAggregate(BaseModel):
    """Aggregated evaluation metrics grouped by C1-C5 failure category."""

    model_config = ConfigDict(extra="forbid")

    category: FailureCategory
    case_count: int
    eligible_case_count: int
    immediate_link_count: int
    no_action_count: int
    total_draws: int
    recovered_draws: int
    recovery_rate: float
    total_opportunity_revenue_paise: int
    expected_recovered_revenue_paise: int


class BaselineSummaryAggregate(BaseModel):
    """Overall summary aggregate for the baseline evaluation run."""

    model_config = ConfigDict(extra="forbid")

    total_cases: int
    eligible_cases: int
    ineligible_cases: int
    immediate_link_cases: int
    no_action_cases: int
    total_draws: int
    recovered_draws: int
    overall_recovery_rate: float
    total_opportunity_revenue_paise: int
    expected_recovered_revenue_paise: int
    categories: dict[str, CategoryAggregate]
    ineligibility_reasons: dict[str, int]


class BaselineEvaluationResult(BaseModel):
    """Complete, self-contained baseline evaluation artifact."""

    model_config = ConfigDict(extra="forbid")

    metadata: dict[str, str | int]
    summary: BaselineSummaryAggregate
    case_aggregates: list[BaselineCaseAggregate]
    draw_results: list[BaselineDrawResult]


# =============================================================================
# Agent Evaluation Models (Layer 5C)
# =============================================================================


class AgentDecision(BaseModel):
    """Structured recovery policy proposal produced by an agent."""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    failure_category: FailureCategory
    proposed_policy_id: RecoveryPolicy
    reasoning: str
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0)
    proposed_amount: int | None = None  # in paise
    proposed_currency: str | None = None


class AgentDecisionValidationRecord(BaseModel):
    """Deterministic validation audit record for an agent proposal."""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    agent_proposal: AgentDecision
    authorized_policy: RecoveryPolicy
    is_approved: bool
    validation_status: str  # e.g. APPROVE, DOWNGRADE, ESCALATE, REJECT, FALLBACK
    reason_code: str
    reasons: list[str]
    guardrails_checked: list[str]
    fallback_applied: bool


class AgentDrawResult(BaseModel):
    """Result of a single Monte Carlo draw for an agent-evaluated case."""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    draw_index: int
    proposed_policy_id: RecoveryPolicy
    authorized_policy: RecoveryPolicy
    is_approved: bool
    recovered: bool
    recovered_amount: int  # in paise
    currency: str
    failure_category: FailureCategory
    time_to_recovery_seconds: int | None = None
    seed: int


class AgentCaseAggregate(BaseModel):
    """Aggregated Monte Carlo evaluation results for a case under agent policy."""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    failure_category: FailureCategory
    amount: int  # in paise
    currency: str
    proposed_policy_id: RecoveryPolicy
    authorized_policy: RecoveryPolicy
    is_approved: bool
    validation_status: str
    draw_count: int
    recovery_count: int
    recovery_rate: float
    total_recovered_paise: int
    expected_recovered_revenue: int  # in paise (mean recovered amount across draws)
    theoretical_p_recovery: float | None = None


class AgentCategoryAggregate(BaseModel):
    """Aggregated evaluation metrics for agent grouped by C1-C5 failure category."""

    model_config = ConfigDict(extra="forbid")

    category: FailureCategory
    case_count: int
    proposed_policy_counts: dict[str, int]
    authorized_policy_counts: dict[str, int]
    total_draws: int
    recovered_draws: int
    recovery_rate: float
    total_opportunity_revenue_paise: int
    expected_recovered_revenue_paise: int


class AgentOverallAggregate(BaseModel):
    """Overall summary aggregate for the agent evaluation run."""

    model_config = ConfigDict(extra="forbid")

    total_cases: int
    total_draws: int
    recovered_draws: int
    overall_recovery_rate: float
    total_opportunity_revenue_paise: int
    expected_recovered_revenue_paise: int
    proposal_counts: dict[str, int]
    authorized_policy_counts: dict[str, int]
    fallback_count: int
    validation_rejection_count: int
    categories: dict[str, AgentCategoryAggregate]


class AgentEvaluationResult(BaseModel):
    """Complete, self-contained agent evaluation artifact."""

    model_config = ConfigDict(extra="forbid")

    metadata: dict[str, str | int]
    summary: AgentOverallAggregate
    decision_records: list[AgentDecisionValidationRecord]
    case_aggregates: list[AgentCaseAggregate]
    draw_results: list[AgentDrawResult]
