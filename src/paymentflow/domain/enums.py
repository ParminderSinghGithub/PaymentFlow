"""Domain enumerations for PaymentFlow Recovery Agent."""

from enum import Enum


class CaseState(str, Enum):
    """Lifecycle states for a payment recovery case."""

    FAILED_INGESTED = "FAILED_INGESTED"
    CONTEXT_RETRIEVED = "CONTEXT_RETRIEVED"
    ELIGIBILITY_CHECKED = "ELIGIBILITY_CHECKED"
    AI_TRIAGED = "AI_TRIAGED"
    POLICY_VALIDATED = "POLICY_VALIDATED"
    ACTION_APPROVED = "ACTION_APPROVED"
    ACTION_EXECUTED = "ACTION_EXECUTED"
    AWAITING_PAYMENT = "AWAITING_PAYMENT"
    VERIFICATION = "VERIFICATION"
    RECOVERED = "RECOVERED"
    EXPIRED = "EXPIRED"
    ESCALATED = "ESCALATED"
    TERMINAL_NO_ACTION = "TERMINAL_NO_ACTION"
    ERROR_TERMINAL = "ERROR_TERMINAL"


class WebhookStatus(str, Enum):
    """Processing statuses for received webhook events."""

    RECEIVED = "RECEIVED"
    PROCESSED = "PROCESSED"
    DUPLICATE = "DUPLICATE"
    IGNORED = "IGNORED"
    FAILED = "FAILED"


class ActorType(str, Enum):
    """Actors recorded in the audit trail."""

    SYSTEM = "system"
    LLM = "llm"
    POLICY_ENGINE = "policy_engine"
    RAZORPAY = "razorpay"
    MERCHANT = "merchant"
