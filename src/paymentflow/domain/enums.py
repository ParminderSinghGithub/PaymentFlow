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


class FailureCategory(str, Enum):
    """Normalized recovery-oriented failure classification taxonomy C1-C5."""

    C1 = "C1"  # Customer-action / transient customer failure
    C2 = "C2"  # Soft infrastructure / gateway / network failure
    C3 = "C3"  # Hard payment-instrument failure
    C4 = "C4"  # Business / risk / limit rejection
    C5 = "C5"  # Integration / invalid-request / non-recoverable technical failure


class EligibilityStatus(str, Enum):
    """Eligibility decision outcome status."""

    ELIGIBLE = "ELIGIBLE"
    INELIGIBLE = "INELIGIBLE"
    REQUIRES_ESCALATION = "REQUIRES_ESCALATION"


class EligibilityReasonCode(str, Enum):
    """Explicit deterministic reason codes for recovery eligibility decisions."""

    ELIGIBLE = "ELIGIBLE"
    INELIGIBLE_PAYMENT_STATE = "INELIGIBLE_PAYMENT_STATE"
    INELIGIBLE_ALREADY_ATTEMPTED = "INELIGIBLE_ALREADY_ATTEMPTED"
    INELIGIBLE_HIGH_VALUE = "INELIGIBLE_HIGH_VALUE"
    INELIGIBLE_COOLDOWN = "INELIGIBLE_COOLDOWN"
    INELIGIBLE_UNSUPPORTED_FAILURE = "INELIGIBLE_UNSUPPORTED_FAILURE"
    INELIGIBLE_CURRENCY = "INELIGIBLE_CURRENCY"
    INELIGIBLE_INVALID_AMOUNT = "INELIGIBLE_INVALID_AMOUNT"
    INELIGIBLE_STALE_STATE = "INELIGIBLE_STALE_STATE"
    INELIGIBLE_MISSING_CONTEXT = "INELIGIBLE_MISSING_CONTEXT"


class RecoveryPolicy(str, Enum):
    """Allowed recovery policy IDs frozen in the source of truth."""

    P_CREATE_LINK_IMMEDIATE = "P_CREATE_LINK_IMMEDIATE"
    P_CREATE_LINK_DELAYED = "P_CREATE_LINK_DELAYED"
    P_ESCALATE_ONLY = "P_ESCALATE_ONLY"
    P_NO_ACTION = "P_NO_ACTION"


class PolicyDecision(str, Enum):
    """Deterministic policy and guardrail authority decisions."""

    APPROVE = "APPROVE"
    DOWNGRADE = "DOWNGRADE"
    REJECT = "REJECT"
    ESCALATE = "ESCALATE"


class TemplateId(str, Enum):
    """Approved recovery communication message templates."""

    TPL_RECOVERY_STANDARD = "TPL_RECOVERY_STANDARD"
    TPL_RECOVERY_URGENT = "TPL_RECOVERY_URGENT"
    TPL_RECOVERY_DISCOUNT = "TPL_RECOVERY_DISCOUNT"
    TPL_ESCALATION_INTERNAL = "TPL_ESCALATION_INTERNAL"
    TPL_NONE = "TPL_NONE"
