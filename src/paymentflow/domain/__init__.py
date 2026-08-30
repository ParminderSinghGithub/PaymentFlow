"""Domain layer components."""

from paymentflow.domain.classifier import FailureClassifier
from paymentflow.domain.eligibility import (
    HIGH_VALUE_THRESHOLD_PAISE,
    MAX_CUSTOMER_RECOVERY_ATTEMPTS_PER_DAY,
    EligibilityEngine,
)
from paymentflow.domain.enums import (
    ActorType,
    CaseState,
    EligibilityReasonCode,
    EligibilityStatus,
    FailureCategory,
    WebhookStatus,
)
from paymentflow.domain.exceptions import (
    DomainError,
    InvalidStateTransitionError,
    RazorpayAdapterError,
    RazorpayAPIError,
    RazorpayAuthError,
    RazorpayNotFoundError,
    RazorpayRateLimitError,
    WebhookPayloadError,
    WebhookVerificationError,
)
from paymentflow.domain.models import (
    ClassificationEvidence,
    EligibilityDecision,
    PaymentContext,
    PaymentFailureDetails,
    RecoveryCaseView,
    WebhookEventPayload,
)
from paymentflow.domain.state_machine import RecoveryStateMachine

__all__ = [
    "HIGH_VALUE_THRESHOLD_PAISE",
    "MAX_CUSTOMER_RECOVERY_ATTEMPTS_PER_DAY",
    "ActorType",
    "CaseState",
    "ClassificationEvidence",
    "DomainError",
    "EligibilityDecision",
    "EligibilityEngine",
    "EligibilityReasonCode",
    "EligibilityStatus",
    "FailureCategory",
    "FailureClassifier",
    "InvalidStateTransitionError",
    "PaymentContext",
    "PaymentFailureDetails",
    "RazorpayAPIError",
    "RazorpayAdapterError",
    "RazorpayAuthError",
    "RazorpayNotFoundError",
    "RazorpayRateLimitError",
    "RecoveryCaseView",
    "RecoveryStateMachine",
    "WebhookEventPayload",
    "WebhookPayloadError",
    "WebhookStatus",
    "WebhookVerificationError",
]
