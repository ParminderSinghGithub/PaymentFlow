"""Deterministic policy and guardrail authority engine."""

import logging
from datetime import datetime, timezone
from typing import Any

from paymentflow.domain.eligibility import (
    HIGH_VALUE_THRESHOLD_PAISE,
    MAX_CUSTOMER_RECOVERY_ATTEMPTS_PER_DAY,
    MAX_STALENESS_SECONDS,
    SUPPORTED_CURRENCIES,
)
from paymentflow.domain.enums import (
    FailureCategory,
    PolicyDecision,
    RecoveryPolicy,
)
from paymentflow.domain.models import (
    PaymentContext,
    PolicyValidationResult,
    RecoveryProposal,
)

logger = logging.getLogger(__name__)


class PolicyGuardrailEngine:
    """Deterministic authority evaluating and overriding AI recovery proposals."""

    @classmethod
    def validate(
        cls,
        context: PaymentContext,
        proposal: RecoveryProposal | None = None,
        requested_policy: RecoveryPolicy | str | None = None,
        failure_category: FailureCategory | None = None,
        has_existing_recovery_link: bool = False,
        customer_attempts_today: int = 0,
        proposed_amount: int | None = None,
        proposed_currency: str | None = None,
        high_value_threshold_paise: int = HIGH_VALUE_THRESHOLD_PAISE,
        max_customer_attempts_per_day: int = MAX_CUSTOMER_RECOVERY_ATTEMPTS_PER_DAY,
        current_time_utc: datetime | None = None,
    ) -> PolicyValidationResult:
        """Deterministically validate recovery proposal against safety guardrails in order."""
        now = current_time_utc or datetime.now(timezone.utc)
        guardrails_checked: list[str] = []

        # Resolve requested policy
        raw_policy = requested_policy or (proposal.policy_id if proposal else None)
        try:
            effective_requested_policy = (
                RecoveryPolicy(raw_policy) if raw_policy else RecoveryPolicy.P_NO_ACTION
            )
        except ValueError:
            effective_requested_policy = RecoveryPolicy.P_NO_ACTION
            return PolicyValidationResult(
                decision=PolicyDecision.REJECT,
                requested_policy=RecoveryPolicy.P_NO_ACTION,
                effective_policy=RecoveryPolicy.P_NO_ACTION,
                reason_code="INVALID_POLICY_ID",
                reasons=[f"Requested policy '{raw_policy}' is not recognized in allowed policies."],
                guardrails_checked=["POLICY_ALLOWLIST"],
                is_approved=False,
                details={"raw_policy": str(raw_policy)},
            )

        guardrails_checked.append("POLICY_ALLOWLIST")

        # Resolve category (use reference deterministic category if not supplied)
        effective_category = failure_category or (proposal.failure_category if proposal else None)

        details: dict[str, Any] = {
            "payment_id": context.payment_id,
            "amount": context.amount,
            "currency": context.currency,
            "requested_policy": effective_requested_policy.value,
            "failure_category": effective_category.value if effective_category else None,
            "has_existing_recovery_link": has_existing_recovery_link,
            "customer_attempts_today": customer_attempts_today,
        }

        # 1. Hard Security: Amount Immutability Guardrail
        guardrails_checked.append("AMOUNT_IMMUTABILITY")
        if proposed_amount is not None and proposed_amount != context.amount:
            logger.warning(
                f"Guardrail REJECT: Proposed {proposed_amount} != original {context.amount}."
            )
            return PolicyValidationResult(
                decision=PolicyDecision.REJECT,
                requested_policy=effective_requested_policy,
                effective_policy=RecoveryPolicy.P_NO_ACTION,
                reason_code="AMOUNT_MUTATION_FORBIDDEN",
                reasons=[
                    f"Proposed recovery amount ({proposed_amount}) does not match "
                    f"verified original payment amount ({context.amount})."
                ],
                guardrails_checked=guardrails_checked,
                is_approved=False,
                details=details,
            )

        # 2. Hard Security: Currency Immutability Guardrail
        guardrails_checked.append("CURRENCY_IMMUTABILITY")
        if (
            proposed_currency is not None
            and str(proposed_currency).upper() != str(context.currency).upper()
        ):
            logger.warning(
                f"Guardrail REJECT: Proposed {proposed_currency} != original {context.currency}."
            )
            return PolicyValidationResult(
                decision=PolicyDecision.REJECT,
                requested_policy=effective_requested_policy,
                effective_policy=RecoveryPolicy.P_NO_ACTION,
                reason_code="CURRENCY_MUTATION_FORBIDDEN",
                reasons=[
                    f"Proposed recovery currency ({proposed_currency}) does not match "
                    f"original currency ({context.currency})."
                ],
                guardrails_checked=guardrails_checked,
                is_approved=False,
                details=details,
            )

        # 3. Currency Allowlist Guardrail
        guardrails_checked.append("SUPPORTED_CURRENCY")
        if str(context.currency).upper() not in SUPPORTED_CURRENCIES:
            logger.warning(f"Guardrail REJECT: Currency '{context.currency}' not supported.")
            return PolicyValidationResult(
                decision=PolicyDecision.REJECT,
                requested_policy=effective_requested_policy,
                effective_policy=RecoveryPolicy.P_NO_ACTION,
                reason_code="UNSUPPORTED_CURRENCY",
                reasons=[f"Currency '{context.currency}' is not supported for recovery."],
                guardrails_checked=guardrails_checked,
                is_approved=False,
                details=details,
            )

        # 4. Payment State Freshness Guardrail
        guardrails_checked.append("PAYMENT_STATE_FRESHNESS")
        if str(context.status).lower() != "failed":
            logger.warning(f"Guardrail REJECT: Payment state '{context.status}' is not failed.")
            return PolicyValidationResult(
                decision=PolicyDecision.REJECT,
                requested_policy=effective_requested_policy,
                effective_policy=RecoveryPolicy.P_NO_ACTION,
                reason_code="INVALID_PAYMENT_STATE",
                reasons=[f"Payment status is '{context.status}', expected 'failed'."],
                guardrails_checked=guardrails_checked,
                is_approved=False,
                details=details,
            )

        # If policy is already P_NO_ACTION or P_ESCALATE_ONLY, approve safely
        if effective_requested_policy == RecoveryPolicy.P_NO_ACTION:
            return PolicyValidationResult(
                decision=PolicyDecision.APPROVE,
                requested_policy=effective_requested_policy,
                effective_policy=RecoveryPolicy.P_NO_ACTION,
                reason_code="NO_ACTION_APPROVED",
                reasons=["No action policy requested and approved."],
                guardrails_checked=guardrails_checked,
                is_approved=True,
                details=details,
            )

        if effective_requested_policy == RecoveryPolicy.P_ESCALATE_ONLY:
            return PolicyValidationResult(
                decision=PolicyDecision.APPROVE,
                requested_policy=effective_requested_policy,
                effective_policy=RecoveryPolicy.P_ESCALATE_ONLY,
                reason_code="ESCALATION_APPROVED",
                reasons=["Escalation policy requested and approved."],
                guardrails_checked=guardrails_checked,
                is_approved=True,
                details=details,
            )

        # The following guardrails apply when financial recovery actions are requested:
        is_link_requested = effective_requested_policy in {
            RecoveryPolicy.P_CREATE_LINK_IMMEDIATE,
            RecoveryPolicy.P_CREATE_LINK_DELAYED,
        }

        if is_link_requested:
            # 5. High-Value Threshold Guardrail (> ₹50,000 / 5,000,000 paise)
            guardrails_checked.append("HIGH_VALUE_THRESHOLD")
            if context.amount > high_value_threshold_paise:
                logger.info(
                    f"Guardrail ESCALATE: Amount {context.amount} paise exceeds "
                    f"high-value threshold ({high_value_threshold_paise} paise)."
                )
                return PolicyValidationResult(
                    decision=PolicyDecision.ESCALATE,
                    requested_policy=effective_requested_policy,
                    effective_policy=RecoveryPolicy.P_ESCALATE_ONLY,
                    reason_code="HIGH_VALUE_THRESHOLD",
                    reasons=[
                        f"Amount ₹{context.amount / 100:.2f} exceeds threshold "
                        f"₹{high_value_threshold_paise / 100:.2f}; escalated to manual review."
                    ],
                    guardrails_checked=guardrails_checked,
                    is_approved=False,
                    details=details,
                )

            # 6. One-Recovery-Link Limit Guardrail
            guardrails_checked.append("ONE_LINK_LIMIT")
            if has_existing_recovery_link:
                logger.info(
                    "Guardrail DOWNGRADE: Case already has recovery link. Downgrading."
                )
                return PolicyValidationResult(
                    decision=PolicyDecision.DOWNGRADE,
                    requested_policy=effective_requested_policy,
                    effective_policy=RecoveryPolicy.P_NO_ACTION,
                    reason_code="ONE_LINK_LIMIT_EXCEEDED",
                    reasons=["Recovery link already created for this payment; second forbidden."],
                    guardrails_checked=guardrails_checked,
                    is_approved=False,
                    details=details,
                )

            # 7. Customer Daily Cooldown Guardrail (Max 3/day)
            guardrails_checked.append("CUSTOMER_COOLDOWN")
            if context.customer_id and customer_attempts_today >= max_customer_attempts_per_day:
                logger.info(
                    f"Guardrail DOWNGRADE: Customer {context.customer_id} daily limit reached."
                )
                return PolicyValidationResult(
                    decision=PolicyDecision.DOWNGRADE,
                    requested_policy=effective_requested_policy,
                    effective_policy=RecoveryPolicy.P_NO_ACTION,
                    reason_code="CUSTOMER_COOLDOWN_EXCEEDED",
                    reasons=[
                        f"Customer {context.customer_id} reached daily recovery limit "
                        f"({customer_attempts_today}/{max_customer_attempts_per_day})."
                    ],
                    guardrails_checked=guardrails_checked,
                    is_approved=False,
                    details=details,
                )

            # 8. C4 / C5 Failure Category Restrictions
            guardrails_checked.append("CATEGORY_COMPATIBILITY")
            if effective_category == FailureCategory.C4:
                logger.info("Guardrail DOWNGRADE: C4 Risk failure cannot receive automated link.")
                return PolicyValidationResult(
                    decision=PolicyDecision.DOWNGRADE,
                    requested_policy=effective_requested_policy,
                    effective_policy=RecoveryPolicy.P_ESCALATE_ONLY,
                    reason_code="RISK_FAILURE_INELIGIBLE_FOR_LINK",
                    reasons=["Risk/business rejection (C4) cannot receive automated Payment Link."],
                    guardrails_checked=guardrails_checked,
                    is_approved=False,
                    details=details,
                )

            if effective_category == FailureCategory.C5:
                logger.info("Guardrail DOWNGRADE: C5 Technical failure cannot receive link.")
                return PolicyValidationResult(
                    decision=PolicyDecision.DOWNGRADE,
                    requested_policy=effective_requested_policy,
                    effective_policy=RecoveryPolicy.P_NO_ACTION,
                    reason_code="TECHNICAL_FAILURE_INELIGIBLE_FOR_LINK",
                    reasons=["Technical integration failure (C5) cannot receive Payment Link."],
                    guardrails_checked=guardrails_checked,
                    is_approved=False,
                    details=details,
                )

            # 9. State Staleness Guardrail (> 72 hours)
            guardrails_checked.append("STATE_FRESHNESS")
            if context.created_at:
                age_seconds = now.timestamp() - context.created_at
                if age_seconds > MAX_STALENESS_SECONDS:
                    logger.info("Guardrail DOWNGRADE: Stale payment failure (>72h).")
                    return PolicyValidationResult(
                        decision=PolicyDecision.DOWNGRADE,
                        requested_policy=effective_requested_policy,
                        effective_policy=RecoveryPolicy.P_NO_ACTION,
                        reason_code="PAYMENT_STALENESS_EXCEEDED",
                        reasons=["Payment failure is older than 72 hours."],
                        guardrails_checked=guardrails_checked,
                        is_approved=False,
                        details=details,
                    )

        # 10. All Guardrails Passed -> APPROVE
        logger.info(f"Guardrails APPROVED for policy {effective_requested_policy.value}.")
        return PolicyValidationResult(
            decision=PolicyDecision.APPROVE,
            requested_policy=effective_requested_policy,
            effective_policy=effective_requested_policy,
            reason_code="POLICY_APPROVED",
            reasons=["All deterministic financial guardrails satisfied."],
            guardrails_checked=guardrails_checked,
            is_approved=True,
            details=details,
        )
