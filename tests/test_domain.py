"""Tests for domain models and value objects."""

import pytest
from pydantic import ValidationError

from paymentflow.domain.enums import CaseState, WebhookStatus
from paymentflow.domain.models import PaymentContext, PaymentFailureDetails


def test_payment_failure_details():
    """Verify PaymentFailureDetails model creation and field extraction."""
    failure = PaymentFailureDetails(
        code="BAD_REQUEST_ERROR",
        description="Payment failed due to card decline",
        source="customer",
        step="payment_authentication",
        reason="card_declined",
    )
    assert failure.code == "BAD_REQUEST_ERROR"
    assert failure.reason == "card_declined"


def test_payment_context_model():
    """Verify PaymentContext model creation with valid data."""
    ctx = PaymentContext(
        payment_id="pay_test123",
        order_id="order_test456",
        customer_id="cust_test789",
        amount=50000,
        currency="INR",
        status="failed",
        method="card",
        email="customer@example.com",
        contact="+919876543210",
        failure=PaymentFailureDetails(code="AUTH_FAILED", description="Authentication failed"),
    )
    assert ctx.payment_id == "pay_test123"
    assert ctx.amount == 50000
    assert ctx.currency == "INR"
    assert ctx.failure.code == "AUTH_FAILED"


def test_payment_context_validation_failure():
    """Verify PaymentContext rejects invalid types for required fields."""
    with pytest.raises(ValidationError):
        PaymentContext(payment_id="pay_123", amount="not_a_number", status="failed")


def test_enums_integrity():
    """Verify core domain enum values."""
    assert CaseState.FAILED_INGESTED.value == "FAILED_INGESTED"
    assert CaseState.RECOVERED.value == "RECOVERED"
    assert WebhookStatus.PROCESSED.value == "PROCESSED"
    assert WebhookStatus.DUPLICATE.value == "DUPLICATE"
