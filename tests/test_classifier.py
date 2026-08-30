"""Deterministic unit tests for FailureClassifier across all C1-C5 categories."""

from paymentflow.domain.classifier import FailureClassifier
from paymentflow.domain.enums import FailureCategory
from paymentflow.domain.models import PaymentFailureDetails


def test_classify_c1_customer_action_explicit_code():
    """Verify C1 classification for standard customer action/authentication failures."""
    details = PaymentFailureDetails(
        code="PAYMENT_AUTHENTICATION_ERROR",
        description="OTP verification failed",
        source="customer",
        step="payment_authentication",
        reason="otp_incorrect",
    )
    evidence = FailureClassifier.classify(details)
    assert evidence.category == FailureCategory.C1
    assert "CUSTOMER" in evidence.matched_rule
    assert evidence.confidence == 1.0


def test_classify_c1_customer_action_reason_override():
    """Verify C1 classification from card declined reason."""
    details = PaymentFailureDetails(
        code="BAD_REQUEST_ERROR",
        description="Declined by customer bank",
        source="customer",
        reason="card_declined",
    )
    evidence = FailureClassifier.classify(details)
    assert evidence.category == FailureCategory.C1
    assert evidence.matched_rule == "REASON_CUSTOMER_ACTION"


def test_classify_c2_soft_infrastructure_gateway_timeout():
    """Verify C2 classification for gateway/network timeouts."""
    details = PaymentFailureDetails(
        code="GATEWAY_TIMEOUT",
        description="Downstream bank took too long to respond",
        source="bank",
        step="payment_authorization",
    )
    evidence = FailureClassifier.classify(details)
    assert evidence.category == FailureCategory.C2
    assert "INFRASTRUCTURE" in evidence.matched_rule or "TIMEOUT" in evidence.matched_rule


def test_classify_c2_soft_infrastructure_heuristic():
    """Verify C2 classification for heuristic bank degradation."""
    details = PaymentFailureDetails(
        code="UNKNOWN_ERR",
        description="Bank servers unavailable due to downtime",
        source="bank",
    )
    evidence = FailureClassifier.classify(details)
    assert evidence.category == FailureCategory.C2


def test_classify_c3_hard_instrument_failure():
    """Verify C3 classification for expired or blocked cards/instruments."""
    details = PaymentFailureDetails(
        code="EXPIRED_CARD",
        description="Card expired",
        source="customer",
        step="payment_authorization",
    )
    evidence = FailureClassifier.classify(details)
    assert evidence.category == FailureCategory.C3
    assert evidence.matched_rule == "CODE_HARD_INSTRUMENT"

    # Reason override
    vpa_details = PaymentFailureDetails(
        code="BAD_REQUEST_ERROR",
        description="VPA not found on UPI network",
        reason="vpa_not_found",
    )
    vpa_evidence = FailureClassifier.classify(vpa_details)
    assert vpa_evidence.category == FailureCategory.C3


def test_classify_c4_business_risk_limit_rejection():
    """Verify C4 classification for risk/business limit failures."""
    details = PaymentFailureDetails(
        code="TRANSACTION_LIMIT_EXCEEDED",
        description="Card daily velocity limit exceeded",
        source="business",
    )
    evidence = FailureClassifier.classify(details)
    assert evidence.category == FailureCategory.C4
    assert "BUSINESS" in evidence.matched_rule or "RISK" in evidence.matched_rule

    risk_details = PaymentFailureDetails(
        code="UNKNOWN_ERR",
        reason="risk_check_failed",
    )
    assert FailureClassifier.classify(risk_details).category == FailureCategory.C4


def test_classify_c5_technical_integration_failure():
    """Verify C5 classification for API / invalid request / technical issues."""
    details = PaymentFailureDetails(
        code="INVALID_ORDER_ID",
        description="Order not found or corrupted",
        source="internal",
    )
    evidence = FailureClassifier.classify(details)
    assert evidence.category == FailureCategory.C5
    assert evidence.matched_rule == "CODE_TECHNICAL_INTEGRATION"


def test_classify_fallback_for_empty_unknown_input():
    """Verify safe C5 fallback for completely unknown/empty inputs."""
    assert FailureClassifier.classify(None).category == FailureCategory.C5
    assert (
        FailureClassifier.classify(PaymentFailureDetails()).category
        == FailureCategory.C5
    )


def test_classify_source_based_fallbacks():
    """Verify source-based fallback matching when error code is ambiguous."""
    assert (
        FailureClassifier.classify(
            PaymentFailureDetails(code="STRANGE_CODE", source="customer")
        ).category
        == FailureCategory.C1
    )
    assert (
        FailureClassifier.classify(
            PaymentFailureDetails(code="STRANGE_CODE", source="gateway")
        ).category
        == FailureCategory.C2
    )
    assert (
        FailureClassifier.classify(
            PaymentFailureDetails(code="STRANGE_CODE", source="business")
        ).category
        == FailureCategory.C4
    )
