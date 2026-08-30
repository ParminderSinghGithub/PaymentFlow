"""Domain models and value objects."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from paymentflow.domain.enums import (
    CaseState,
    EligibilityReasonCode,
    EligibilityStatus,
    FailureCategory,
)


class PaymentFailureDetails(BaseModel):
    """Structured payment failure information extracted from Razorpay."""

    model_config = ConfigDict(extra="ignore")

    code: str | None = None
    description: str | None = None
    source: str | None = None
    step: str | None = None
    reason: str | None = None


class PaymentContext(BaseModel):
    """Domain model representing payment context."""

    model_config = ConfigDict(extra="ignore")

    payment_id: str
    order_id: str | None = None
    customer_id: str | None = None
    amount: int  # in paise (integer)
    currency: str = "INR"
    status: str
    method: str | None = None
    email: str | None = None
    contact: str | None = None
    failure: PaymentFailureDetails = Field(default_factory=PaymentFailureDetails)
    raw_notes: dict[str, Any] = Field(default_factory=dict)
    created_at: int | None = None


class WebhookEventPayload(BaseModel):
    """Parsed and validated Razorpay webhook event payload."""

    model_config = ConfigDict(extra="ignore")

    event_id: str
    event_type: str
    account_id: str | None = None
    created_at: int | None = None
    payment: PaymentContext | None = None
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class ClassificationEvidence(BaseModel):
    """Structured evidence for deterministic C1-C5 failure classification."""

    model_config = ConfigDict(extra="ignore")

    category: FailureCategory
    matched_rule: str
    primary_code: str | None = None
    source: str | None = None
    step: str | None = None
    reason: str | None = None
    confidence: float = 1.0
    details: dict[str, Any] = Field(default_factory=dict)


class EligibilityDecision(BaseModel):
    """Structured decision object produced by the deterministic eligibility engine."""

    model_config = ConfigDict(extra="ignore")

    eligible: bool
    status: EligibilityStatus
    reason_code: EligibilityReasonCode
    reasons: list[str] = Field(default_factory=list)
    failure_category: FailureCategory | None = None
    evaluated_amount: int
    currency: str = "INR"
    details: dict[str, Any] = Field(default_factory=dict)


class RecoveryCaseView(BaseModel):
    """Read-only domain representation of a recovery case."""

    model_config = ConfigDict(from_attributes=True)

    case_id: str
    failed_payment_id: str
    order_id: str | None = None
    customer_id: str | None = None
    amount: int
    currency: str
    payment_method: str | None = None
    state: CaseState
    failure_category: FailureCategory | None = None
    failure_code: str | None = None
    failure_description: str | None = None
    eligibility_status: EligibilityStatus | None = None
    eligibility_reason: EligibilityReasonCode | None = None
    created_at: datetime
    updated_at: datetime
