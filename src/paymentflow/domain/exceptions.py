"""Domain and application exceptions."""


class PaymentFlowError(Exception):
    """Base exception for PaymentFlow application errors."""

    pass


class DomainError(PaymentFlowError):
    """Base exception for domain business logic errors."""

    pass


class InvalidStateTransitionError(DomainError):
    """Raised when an illegal state machine transition is attempted."""

    def __init__(self, current_state: str, target_state: str, reason: str | None = None):
        self.current_state = current_state
        self.target_state = target_state
        self.reason = reason
        message = f"Invalid state transition from '{current_state}' to '{target_state}'."
        if reason:
            message += f" Reason: {reason}"
        super().__init__(message)


class WebhookVerificationError(DomainError):
    """Raised when webhook signature verification fails or signature is missing."""

    pass


class WebhookPayloadError(DomainError):
    """Raised when webhook payload is malformed or missing required event fields."""

    pass


class RazorpayAdapterError(PaymentFlowError):
    """Base exception for Razorpay external adapter failures."""

    pass


class RazorpayAuthError(RazorpayAdapterError):
    """Raised on authentication failure (HTTP 401)."""

    pass


class RazorpayNotFoundError(RazorpayAdapterError):
    """Raised when requested entity is not found in Razorpay (HTTP 404)."""

    pass


class RazorpayRateLimitError(RazorpayAdapterError):
    """Raised when Razorpay rate limits are exceeded (HTTP 429)."""

    pass


class RazorpayAPIError(RazorpayAdapterError):
    """Raised on general Razorpay API errors (HTTP 4xx/5xx)."""

    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        super().__init__(f"Razorpay API Error [{status_code}]: {message}")
