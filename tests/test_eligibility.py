"""Deterministic unit tests for EligibilityEngine across all rules and boundary conditions."""

from datetime import datetime, timedelta, timezone

from paymentflow.domain.eligibility import (
    HIGH_VALUE_THRESHOLD_PAISE,
    EligibilityEngine,
)
from paymentflow.domain.enums import (
    EligibilityReasonCode,
    EligibilityStatus,
    FailureCategory,
)
from paymentflow.domain.models import PaymentContext, PaymentFailureDetails


def make_valid_context(
    payment_id: str = "pay_test_01",
    amount: int = 150000,
    currency: str = "INR",
    status: str = "failed",
    customer_id: str | None = "cust_test_01",
    created_at: int | None = None,
) -> PaymentContext:
    """Helper to construct valid payment context."""
    now = datetime.now(timezone.utc)
    return PaymentContext(
        payment_id=payment_id,
        amount=amount,
        currency=currency,
        status=status,
        customer_id=customer_id,
        created_at=created_at or int(now.timestamp()),
        failure=PaymentFailureDetails(code="PAYMENT_AUTHENTICATION_ERROR"),
    )


def test_eligibility_fully_eligible():
    """Verify standard happy-path eligible payment."""
    ctx = make_valid_context(amount=250000)
    decision = EligibilityEngine.evaluate(
        context=ctx,
        failure_category=FailureCategory.C1,
        has_existing_recovery_link=False,
        customer_attempts_today=0,
    )
    assert decision.eligible is True
    assert decision.status == EligibilityStatus.ELIGIBLE
    assert decision.reason_code == EligibilityReasonCode.ELIGIBLE
    assert decision.evaluated_amount == 250000


def test_eligibility_invalid_payment_state():
    """Verify non-failed payments (captured, refunded, etc.) are rejected."""
    ctx = make_valid_context(status="captured")
    decision = EligibilityEngine.evaluate(context=ctx, failure_category=FailureCategory.C1)
    assert decision.eligible is False
    assert decision.status == EligibilityStatus.INELIGIBLE
    assert decision.reason_code == EligibilityReasonCode.INELIGIBLE_PAYMENT_STATE


def test_eligibility_already_attempted():
    """Verify payment with existing recovery link is rejected."""
    ctx = make_valid_context()
    decision = EligibilityEngine.evaluate(
        context=ctx,
        failure_category=FailureCategory.C1,
        has_existing_recovery_link=True,
    )
    assert decision.eligible is False
    assert decision.status == EligibilityStatus.INELIGIBLE
    assert decision.reason_code == EligibilityReasonCode.INELIGIBLE_ALREADY_ATTEMPTED


def test_eligibility_high_value_rule():
    """Verify high-value threshold (₹50,000 / 5,000,000 paise)."""
    # Exactly at threshold ₹50,000 -> Eligible
    ctx_exact = make_valid_context(amount=HIGH_VALUE_THRESHOLD_PAISE)
    decision_exact = EligibilityEngine.evaluate(
        context=ctx_exact, failure_category=FailureCategory.C1
    )
    assert decision_exact.eligible is True

    # 1 paise above threshold (₹50,000.01) -> Requires Escalation
    ctx_above = make_valid_context(amount=HIGH_VALUE_THRESHOLD_PAISE + 1)
    decision_above = EligibilityEngine.evaluate(
        context=ctx_above, failure_category=FailureCategory.C1
    )
    assert decision_above.eligible is False
    assert decision_above.status == EligibilityStatus.REQUIRES_ESCALATION
    assert decision_above.reason_code == EligibilityReasonCode.INELIGIBLE_HIGH_VALUE


def test_eligibility_customer_cooldown():
    """Verify maximum 3 recovery attempts per customer per day."""
    ctx = make_valid_context(customer_id="cust_repeat_01")

    # 0, 1, 2 attempts -> Eligible
    for attempts in (0, 1, 2):
        dec = EligibilityEngine.evaluate(
            context=ctx,
            failure_category=FailureCategory.C1,
            customer_attempts_today=attempts,
        )
        assert dec.eligible is True, f"Failed at attempts={attempts}"

    # 3 or more attempts -> Cooldown rejection
    for attempts in (3, 4, 5):
        dec = EligibilityEngine.evaluate(
            context=ctx,
            failure_category=FailureCategory.C1,
            customer_attempts_today=attempts,
        )
        assert dec.eligible is False
        assert dec.status == EligibilityStatus.INELIGIBLE
        assert dec.reason_code == EligibilityReasonCode.INELIGIBLE_COOLDOWN


def test_eligibility_missing_customer_id_cooldown_safe():
    """Verify missing customer_id bypasses customer cooldown safely without failing."""
    ctx = make_valid_context(customer_id=None)
    decision = EligibilityEngine.evaluate(
        context=ctx,
        failure_category=FailureCategory.C1,
        customer_attempts_today=5,
    )
    assert decision.eligible is True


def test_eligibility_unsupported_failure_categories():
    """Verify C4 (Risk) and C5 (Technical) are ineligible for recovery."""
    ctx = make_valid_context()

    # C4
    dec_c4 = EligibilityEngine.evaluate(context=ctx, failure_category=FailureCategory.C4)
    assert dec_c4.eligible is False
    assert dec_c4.reason_code == EligibilityReasonCode.INELIGIBLE_UNSUPPORTED_FAILURE

    # C5
    dec_c5 = EligibilityEngine.evaluate(context=ctx, failure_category=FailureCategory.C5)
    assert dec_c5.eligible is False
    assert dec_c5.reason_code == EligibilityReasonCode.INELIGIBLE_UNSUPPORTED_FAILURE

    # C2 and C3 are eligible
    assert (
        EligibilityEngine.evaluate(context=ctx, failure_category=FailureCategory.C2).eligible
        is True
    )
    assert (
        EligibilityEngine.evaluate(context=ctx, failure_category=FailureCategory.C3).eligible
        is True
    )


def test_eligibility_unsupported_currency():
    """Verify unsupported currencies are rejected."""
    ctx = make_valid_context(currency="USD")
    decision = EligibilityEngine.evaluate(context=ctx, failure_category=FailureCategory.C1)
    assert decision.eligible is False
    assert decision.reason_code == EligibilityReasonCode.INELIGIBLE_CURRENCY


def test_eligibility_invalid_amount():
    """Verify non-positive amounts are rejected."""
    ctx_zero = make_valid_context(amount=0)
    decision_zero = EligibilityEngine.evaluate(
        context=ctx_zero, failure_category=FailureCategory.C1
    )
    assert decision_zero.eligible is False
    assert decision_zero.reason_code == EligibilityReasonCode.INELIGIBLE_INVALID_AMOUNT


def test_eligibility_staleness_rule():
    """Verify payments older than 72 hours are rejected as stale."""
    now = datetime.now(timezone.utc)
    old_timestamp = int((now - timedelta(hours=75)).timestamp())
    ctx_old = make_valid_context(created_at=old_timestamp)

    decision = EligibilityEngine.evaluate(
        context=ctx_old,
        failure_category=FailureCategory.C1,
        current_time_utc=now,
    )
    assert decision.eligible is False
    assert decision.reason_code == EligibilityReasonCode.INELIGIBLE_STALE_STATE


def test_eligibility_precedence_order():
    """Verify deterministic precedence when multiple rules fail simultaneously."""
    # When both non-failed status AND high value fail, state check takes precedence
    ctx = make_valid_context(status="captured", amount=99999999)
    decision = EligibilityEngine.evaluate(context=ctx, failure_category=FailureCategory.C4)
    assert decision.reason_code == EligibilityReasonCode.INELIGIBLE_PAYMENT_STATE
