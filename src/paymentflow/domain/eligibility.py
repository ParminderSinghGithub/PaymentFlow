"""Deterministic recovery eligibility evaluation engine."""

import logging
from datetime import datetime, timezone
from typing import Any

from paymentflow.domain.enums import (
    EligibilityReasonCode,
    EligibilityStatus,
    FailureCategory,
)
from paymentflow.domain.models import EligibilityDecision, PaymentContext

logger = logging.getLogger(__name__)

# Constants enforced by frozen specification
HIGH_VALUE_THRESHOLD_PAISE: int = 50_000_00  # ₹50,000 (5,000,000 paise)
MAX_CUSTOMER_RECOVERY_ATTEMPTS_PER_DAY: int = 3
MAX_STALENESS_SECONDS: int = 72 * 3600  # 72 hours
SUPPORTED_CURRENCIES: set[str] = {"INR"}


class EligibilityEngine:
    """Evaluates payment recovery eligibility against deterministic financial constraints."""

    @classmethod
    def evaluate(
        cls,
        context: PaymentContext,
        failure_category: FailureCategory | None = None,
        has_existing_recovery_link: bool = False,
        customer_attempts_today: int = 0,
        high_value_threshold_paise: int = HIGH_VALUE_THRESHOLD_PAISE,
        max_customer_attempts_per_day: int = MAX_CUSTOMER_RECOVERY_ATTEMPTS_PER_DAY,
        current_time_utc: datetime | None = None,
    ) -> EligibilityDecision:
        """Evaluate deterministic recovery eligibility in strict precedence order."""
        now = current_time_utc or datetime.now(timezone.utc)
        details: dict[str, Any] = {
            "payment_id": context.payment_id,
            "amount": context.amount,
            "currency": context.currency,
            "status": context.status,
            "failure_category": failure_category.value if failure_category else None,
            "has_existing_recovery_link": has_existing_recovery_link,
            "customer_attempts_today": customer_attempts_today,
        }

        # 1. Missing / Invalid Context Constraint
        if not context.payment_id or context.amount is None or context.amount <= 0:
            logger.info(
                f"Eligibility REJECT: Invalid or missing amount ({context.amount})."
            )
            return EligibilityDecision(
                eligible=False,
                status=EligibilityStatus.INELIGIBLE,
                reason_code=EligibilityReasonCode.INELIGIBLE_INVALID_AMOUNT,
                reasons=["Payment amount must be a positive integer in paise."],
                failure_category=failure_category,
                evaluated_amount=context.amount or 0,
                currency=context.currency,
                details=details,
            )

        # 2. Payment State Freshness / Success Check
        norm_status = str(context.status).strip().lower()
        if norm_status != "failed":
            logger.info(
                f"Eligibility REJECT: Payment state '{context.status}' is not 'failed'."
            )
            return EligibilityDecision(
                eligible=False,
                status=EligibilityStatus.INELIGIBLE,
                reason_code=EligibilityReasonCode.INELIGIBLE_PAYMENT_STATE,
                reasons=[f"Payment status is '{context.status}', expected 'failed'."],
                failure_category=failure_category,
                evaluated_amount=context.amount,
                currency=context.currency,
                details=details,
            )

        # 3. One-Recovery-Link / Already Attempted Constraint
        if has_existing_recovery_link:
            logger.info(
                f"Eligibility REJECT: Payment {context.payment_id} already has a recovery link."
            )
            return EligibilityDecision(
                eligible=False,
                status=EligibilityStatus.INELIGIBLE,
                reason_code=EligibilityReasonCode.INELIGIBLE_ALREADY_ATTEMPTED,
                reasons=["A recovery link has already been created for this failed payment."],
                failure_category=failure_category,
                evaluated_amount=context.amount,
                currency=context.currency,
                details=details,
            )

        # 4. Currency Constraint
        norm_currency = str(context.currency).strip().upper()
        if norm_currency not in SUPPORTED_CURRENCIES:
            logger.info(f"Eligibility REJECT: Currency '{context.currency}' not supported.")
            return EligibilityDecision(
                eligible=False,
                status=EligibilityStatus.INELIGIBLE,
                reason_code=EligibilityReasonCode.INELIGIBLE_CURRENCY,
                reasons=[f"Currency '{context.currency}' is not supported for recovery."],
                failure_category=failure_category,
                evaluated_amount=context.amount,
                currency=context.currency,
                details=details,
            )

        # 5. High-Value Threshold Constraint (> ₹50,000 / 5,000,000 paise)
        if context.amount > high_value_threshold_paise:
            logger.info(
                f"Eligibility ESCALATE: Amount {context.amount} paise exceeds "
                f"high-value threshold ({high_value_threshold_paise} paise)."
            )
            return EligibilityDecision(
                eligible=False,
                status=EligibilityStatus.REQUIRES_ESCALATION,
                reason_code=EligibilityReasonCode.INELIGIBLE_HIGH_VALUE,
                reasons=[
                    f"Payment amount of ₹{context.amount / 100:.2f} exceeds "
                    f"the maximum automated threshold of ₹{high_value_threshold_paise / 100:.2f}."
                ],
                failure_category=failure_category,
                evaluated_amount=context.amount,
                currency=context.currency,
                details=details,
            )

        # 6. Customer Cooldown Constraint (Max 3 recovery attempts / customer / day)
        if context.customer_id and customer_attempts_today >= max_customer_attempts_per_day:
            logger.info(
                f"Eligibility REJECT: Customer {context.customer_id} cooldown reached "
                f"({customer_attempts_today}/{max_customer_attempts_per_day})."
            )
            return EligibilityDecision(
                eligible=False,
                status=EligibilityStatus.INELIGIBLE,
                reason_code=EligibilityReasonCode.INELIGIBLE_COOLDOWN,
                reasons=[
                    f"Customer {context.customer_id} has reached the maximum daily recovery limit "
                    f"({customer_attempts_today}/{max_customer_attempts_per_day})."
                ],
                failure_category=failure_category,
                evaluated_amount=context.amount,
                currency=context.currency,
                details=details,
            )

        # 7. Unsupported Failure Category Constraint (C4 Risk & C5 Technical are ineligible)
        if failure_category in {FailureCategory.C4, FailureCategory.C5}:
            logger.info(
                f"Eligibility REJECT: Failure category '{failure_category.value}' is ineligible."
            )
            return EligibilityDecision(
                eligible=False,
                status=EligibilityStatus.INELIGIBLE,
                reason_code=EligibilityReasonCode.INELIGIBLE_UNSUPPORTED_FAILURE,
                reasons=[
                    f"Failure category {failure_category.value} is not eligible for recovery."
                ],
                failure_category=failure_category,
                evaluated_amount=context.amount,
                currency=context.currency,
                details=details,
            )

        # 8. State Freshness / Staleness Constraint
        if context.created_at:
            age_seconds = now.timestamp() - context.created_at
            if age_seconds > MAX_STALENESS_SECONDS:
                logger.info(
                    f"Eligibility REJECT: Payment is stale ({age_seconds:.0f}s > "
                    f"{MAX_STALENESS_SECONDS}s)."
                )
                return EligibilityDecision(
                    eligible=False,
                    status=EligibilityStatus.INELIGIBLE,
                    reason_code=EligibilityReasonCode.INELIGIBLE_STALE_STATE,
                    reasons=[
                        "Payment failure is older than maximum permitted recovery window (72h)."
                    ],
                    failure_category=failure_category,
                    evaluated_amount=context.amount,
                    currency=context.currency,
                    details=details,
                )

        # 9. All Constraints Passed -> ELIGIBLE
        logger.info(
            f"Eligibility APPROVED for payment {context.payment_id} "
            f"({context.amount} {context.currency})."
        )
        return EligibilityDecision(
            eligible=True,
            status=EligibilityStatus.ELIGIBLE,
            reason_code=EligibilityReasonCode.ELIGIBLE,
            reasons=["All deterministic eligibility and financial safety constraints satisfied."],
            failure_category=failure_category,
            evaluated_amount=context.amount,
            currency=context.currency,
            details=details,
        )
