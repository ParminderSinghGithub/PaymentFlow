"""Deterministic C1-C5 failure classification engine."""

import logging
from typing import Any

from paymentflow.domain.enums import FailureCategory
from paymentflow.domain.models import ClassificationEvidence, PaymentFailureDetails

logger = logging.getLogger(__name__)


class FailureClassifier:
    """Classifies payment failures into frozen recovery taxonomy C1-C5 deterministically."""

    # Explicit code mappings (normalized uppercase)
    _C1_CODES = {
        "PAYMENT_AUTHENTICATION_ERROR",
        "AUTHENTICATION_FAILED",
        "AUTH_FAILED",
        "BAD_REQUEST_ERROR",
        "CARD_DECLINED",
        "CUSTOMER_CANCELLED",
        "CUSTOMER_ACTION_TIMEOUT",
        "DECLINED_BY_ISSUER",
        "INSUFFICIENT_BALANCE",
        "INSUFFICIENT_FUNDS",
        "OTP_EXPIRED",
        "OTP_INCORRECT",
        "OTP_TIMEOUT",
        "PAYMENT_CANCELLED",
        "PAYMENT_DECLINED",
        "USER_DROPPED",
        "USER_CANCELLED",
    }

    _C2_CODES = {
        "BAD_GATEWAY",
        "BANK_TIMEOUT",
        "BANK_UNAVAILABLE",
        "DOWNSTREAM_TIMEOUT",
        "GATEWAY_ERROR",
        "GATEWAY_TIMEOUT",
        "GATEWAY_UNAVAILABLE",
        "INTERNAL_SERVER_ERROR",
        "NETWORK_ERROR",
        "SERVER_ERROR",
        "SERVICE_UNAVAILABLE",
        "TIMEOUT",
    }

    _C3_CODES = {
        "ACCOUNT_CLOSED",
        "BLOCKED_CARD",
        "CARD_NOT_SUPPORTED",
        "EXPIRED_CARD",
        "INACTIVE_ACCOUNT",
        "INSTRUMENT_INVALID",
        "INVALID_ACCOUNT",
        "INVALID_CARD",
        "INVALID_CVV",
        "INVALID_EXPIRY",
        "INVALID_VPA",
        "PAYMENT_INSTRUMENT_ERROR",
        "VPA_BLOCKED",
        "VPA_NOT_FOUND",
    }

    _C4_CODES = {
        "BUSINESS_ERROR",
        "CURRENCY_NOT_SUPPORTED_FOR_ACCOUNT",
        "FRAUD_SUSPECTED",
        "INTERNATIONAL_NOT_ALLOWED",
        "LIMIT_EXCEEDED",
        "MAXIMUM_AMOUNT_EXCEEDED",
        "MERCHANT_RISK_REJECT",
        "MINIMUM_AMOUNT_NOT_MET",
        "RISK_CHECK_FAILED",
        "TRANSACTION_LIMIT_EXCEEDED",
        "VELOCITY_LIMIT_EXCEEDED",
    }

    _C5_CODES = {
        "AUTHENTICATION_ERROR",
        "INVALID_AMOUNT",
        "INVALID_ORDER_ID",
        "INVALID_REQUEST_ERROR",
        "MERCHANT_NOT_ACTIVE",
        "MISSING_REQUIRED_FIELD",
        "SIGNATURE_VERIFICATION_FAILED",
        "UNAUTHORIZED",
    }

    @classmethod
    def classify(
        cls,
        failure: PaymentFailureDetails | None = None,
        raw_context: dict[str, Any] | None = None,
    ) -> ClassificationEvidence:
        """Deterministically classify failure into C1-C5 taxonomy with structured evidence."""
        code = (failure.code if failure else None) or (
            raw_context.get("error_code") if raw_context else None
        )
        source = (failure.source if failure else None) or (
            raw_context.get("error_source") if raw_context else None
        )
        step = (failure.step if failure else None) or (
            raw_context.get("error_step") if raw_context else None
        )
        reason = (failure.reason if failure else None) or (
            raw_context.get("error_reason") if raw_context else None
        )
        description = (failure.description if failure else None) or (
            raw_context.get("error_description") if raw_context else None
        )

        norm_code = str(code).strip().upper() if code else ""
        norm_source = str(source).strip().lower() if source else ""
        norm_step = str(step).strip().lower() if step else ""
        norm_reason = str(reason).strip().lower() if reason else ""
        norm_desc = str(description).strip().lower() if description else ""

        details = {
            "code": code,
            "source": source,
            "step": step,
            "reason": reason,
            "description": description,
        }

        # 1. Check explicit reason code overrides
        if norm_reason in {"card_declined", "insufficient_funds", "user_cancelled", "otp_timeout"}:
            return ClassificationEvidence(
                category=FailureCategory.C1,
                matched_rule="REASON_CUSTOMER_ACTION",
                primary_code=code,
                source=source,
                step=step,
                reason=reason,
                details=details,
            )

        if norm_reason in {"expired_card", "invalid_card", "vpa_not_found", "account_closed"}:
            return ClassificationEvidence(
                category=FailureCategory.C3,
                matched_rule="REASON_HARD_INSTRUMENT",
                primary_code=code,
                source=source,
                step=step,
                reason=reason,
                details=details,
            )

        if norm_reason in {"limit_exceeded", "risk_check_failed", "fraud_suspected"}:
            return ClassificationEvidence(
                category=FailureCategory.C4,
                matched_rule="REASON_BUSINESS_RISK",
                primary_code=code,
                source=source,
                step=step,
                reason=reason,
                details=details,
            )

        # 2. Check exact code sets
        if norm_code in cls._C3_CODES:
            return ClassificationEvidence(
                category=FailureCategory.C3,
                matched_rule="CODE_HARD_INSTRUMENT",
                primary_code=code,
                source=source,
                step=step,
                reason=reason,
                details=details,
            )

        if norm_code in cls._C4_CODES:
            return ClassificationEvidence(
                category=FailureCategory.C4,
                matched_rule="CODE_BUSINESS_RISK",
                primary_code=code,
                source=source,
                step=step,
                reason=reason,
                details=details,
            )

        if norm_code in cls._C5_CODES:
            return ClassificationEvidence(
                category=FailureCategory.C5,
                matched_rule="CODE_TECHNICAL_INTEGRATION",
                primary_code=code,
                source=source,
                step=step,
                reason=reason,
                details=details,
            )

        if norm_code in cls._C2_CODES:
            return ClassificationEvidence(
                category=FailureCategory.C2,
                matched_rule="CODE_SOFT_INFRASTRUCTURE",
                primary_code=code,
                source=source,
                step=step,
                reason=reason,
                details=details,
            )

        if norm_code in cls._C1_CODES:
            return ClassificationEvidence(
                category=FailureCategory.C1,
                matched_rule="CODE_CUSTOMER_ACTION",
                primary_code=code,
                source=source,
                step=step,
                reason=reason,
                details=details,
            )

        # 3. Contextual heuristic matching on step, source, and description keywords
        if "authentication" in norm_step or "authentication" in norm_desc or "otp" in norm_desc:
            return ClassificationEvidence(
                category=FailureCategory.C1,
                matched_rule="HEURISTIC_AUTHENTICATION_STEP",
                primary_code=code,
                source=source,
                step=step,
                reason=reason,
                details=details,
            )

        if norm_source in {"bank", "gateway"} and (
            "timeout" in norm_desc or "unavailable" in norm_desc or "down" in norm_desc
        ):
            return ClassificationEvidence(
                category=FailureCategory.C2,
                matched_rule="HEURISTIC_GATEWAY_TIMEOUT",
                primary_code=code,
                source=source,
                step=step,
                reason=reason,
                details=details,
            )

        if "expired" in norm_desc or "blocked" in norm_desc or "invalid card" in norm_desc:
            return ClassificationEvidence(
                category=FailureCategory.C3,
                matched_rule="HEURISTIC_INSTRUMENT_FAILURE",
                primary_code=code,
                source=source,
                step=step,
                reason=reason,
                details=details,
            )

        if "limit" in norm_desc or "risk" in norm_desc or "fraud" in norm_desc:
            return ClassificationEvidence(
                category=FailureCategory.C4,
                matched_rule="HEURISTIC_RISK_LIMIT",
                primary_code=code,
                source=source,
                step=step,
                reason=reason,
                details=details,
            )

        # 4. Source-based fallback
        if norm_source == "customer":
            return ClassificationEvidence(
                category=FailureCategory.C1,
                matched_rule="SOURCE_CUSTOMER_FALLBACK",
                primary_code=code,
                source=source,
                step=step,
                reason=reason,
                details=details,
            )

        if norm_source in {"bank", "gateway"}:
            return ClassificationEvidence(
                category=FailureCategory.C2,
                matched_rule="SOURCE_GATEWAY_FALLBACK",
                primary_code=code,
                source=source,
                step=step,
                reason=reason,
                details=details,
            )

        if norm_source == "business":
            return ClassificationEvidence(
                category=FailureCategory.C4,
                matched_rule="SOURCE_BUSINESS_FALLBACK",
                primary_code=code,
                source=source,
                step=step,
                reason=reason,
                details=details,
            )

        # 5. Default safe non-recoverable fallback
        return ClassificationEvidence(
            category=FailureCategory.C5,
            matched_rule="DEFAULT_NON_RECOVERABLE_FALLBACK",
            primary_code=code,
            source=source,
            step=step,
            reason=reason,
            details=details,
        )
