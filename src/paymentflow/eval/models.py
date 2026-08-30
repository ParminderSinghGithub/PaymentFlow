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
