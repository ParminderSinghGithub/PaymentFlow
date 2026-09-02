"""Recovery triage service coordinating context enrichment, classification, and eligibility."""

import logging
from datetime import timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from paymentflow.adapters.razorpay_adapter import RazorpayAdapter
from paymentflow.db.models import AuditEventModel, RecoveryCaseModel, utc_now
from paymentflow.domain.classifier import FailureClassifier
from paymentflow.domain.eligibility import EligibilityEngine
from paymentflow.domain.enums import (
    ActorType,
    CaseState,
    EligibilityStatus,
    FailureCategory,
)
from paymentflow.domain.exceptions import (
    DomainError,
    RazorpayAdapterError,
)
from paymentflow.domain.models import (
    EligibilityDecision,
    PaymentContext,
    PaymentFailureDetails,
)
from paymentflow.domain.state_machine import RecoveryStateMachine

logger = logging.getLogger(__name__)


class RecoveryTriageService:
    """Coordinates deterministic Layer 2 recovery triage pipeline."""

    def __init__(
        self,
        db_session: AsyncSession,
        razorpay_adapter: RazorpayAdapter | None = None,
    ):
        self.session = db_session
        self.adapter = razorpay_adapter or RazorpayAdapter()

    async def get_case(self, case_id: str) -> RecoveryCaseModel:
        """Fetch recovery case by ID or raise DomainError."""
        query = select(RecoveryCaseModel).where(RecoveryCaseModel.case_id == case_id)
        result = await self.session.execute(query)
        case = result.scalar_one_or_none()
        if not case:
            raise DomainError(f"Recovery case '{case_id}' not found.")
        return case

    async def enrich_context(
        self,
        case_id: str,
        fetch_from_gateway: bool = True,
    ) -> RecoveryCaseModel:
        """Retrieve and enrich payment/order context from Razorpay gateway."""
        case = await self.get_case(case_id)
        current_state = CaseState(case.state)

        # Idempotency check: If already enriched, return cleanly
        if current_state != CaseState.FAILED_INGESTED:
            logger.info(
                f"Case '{case_id}' already at state '{current_state.value}'. "
                "Skipping duplicate enrichment."
            )
            return case

        payment_data: dict[str, Any] = {}
        order_data: dict[str, Any] = {}

        if fetch_from_gateway:
            try:
                payment_data = await self.adapter.get_payment(case.failed_payment_id)
                order_id = payment_data.get("order_id") or case.order_id
                if order_id:
                    try:
                        order_data = await self.adapter.get_order(order_id)
                    except RazorpayAdapterError as order_err:
                        logger.warning(
                            f"Could not fetch order {order_id} during enrichment: {order_err}"
                        )
            except RazorpayAdapterError as exc:
                logger.error(f"Gateway payment fetch failed for case {case_id}: {exc}")
                # Safe failure: transition to ERROR_TERMINAL and record audit
                case.state = RecoveryStateMachine.transition(
                    current_state, CaseState.ERROR_TERMINAL
                ).value
                case.updated_at = utc_now()

                audit_err = AuditEventModel(
                    case_id=case_id,
                    event_type="CONTEXT_ENRICHMENT_FAILED",
                    actor=ActorType.SYSTEM.value,
                    decision="ERROR",
                    action="FETCH_GATEWAY_CONTEXT",
                    outcome="FAILURE",
                    correlation_id=case.failed_payment_id,
                    timestamp=utc_now(),
                    details={"error": str(exc)},
                )
                self.session.add(audit_err)
                await self.session.commit()
                raise DomainError(f"Context enrichment failed for case '{case_id}': {exc}") from exc

        # Update case attributes from verified gateway payload where available
        if payment_data:
            if "amount" in payment_data:
                case.amount = int(payment_data["amount"])
            if "currency" in payment_data:
                case.currency = str(payment_data["currency"])
            if "customer_id" in payment_data and payment_data["customer_id"]:
                case.customer_id = str(payment_data["customer_id"])
            if "order_id" in payment_data and payment_data["order_id"]:
                case.order_id = str(payment_data["order_id"])
            if "method" in payment_data and payment_data["method"]:
                case.payment_method = str(payment_data["method"])

            error_code = payment_data.get("error_code")
            error_desc = payment_data.get("error_description")
            if error_code:
                case.failure_code = error_code
            if error_desc:
                case.failure_description = error_desc

            # Merge failure context
            existing_ctx = case.failure_context or {}
            existing_ctx.update(
                {
                    "gateway_payment": payment_data,
                    "gateway_order": order_data,
                    "error_source": payment_data.get("error_source"),
                    "error_step": payment_data.get("error_step"),
                    "error_reason": payment_data.get("error_reason"),
                }
            )
            case.failure_context = existing_ctx

        # State transition: FAILED_INGESTED -> CONTEXT_RETRIEVED
        case.state = RecoveryStateMachine.transition(
            current_state, CaseState.CONTEXT_RETRIEVED
        ).value
        case.updated_at = utc_now()

        # Audit Event
        audit_event = AuditEventModel(
            case_id=case_id,
            event_type="CONTEXT_ENRICHED",
            actor=ActorType.SYSTEM.value,
            decision="CONTEXT_RETRIEVED",
            action="ENRICH_PAYMENT_CONTEXT",
            outcome="SUCCESS",
            correlation_id=case.failed_payment_id,
            timestamp=utc_now(),
            details={
                "amount": case.amount,
                "currency": case.currency,
                "method": case.payment_method,
                "order_id": case.order_id,
                "customer_id": case.customer_id,
            },
        )
        self.session.add(audit_event)
        await self.session.commit()
        logger.info(f"Context enriched successfully for case {case_id}.")
        return case

    async def classify_case(self, case_id: str) -> RecoveryCaseModel:
        """Classify failure context deterministically into C1-C5 taxonomy."""
        case = await self.get_case(case_id)

        failure_details = PaymentFailureDetails(
            code=case.failure_code,
            description=case.failure_description,
            source=(case.failure_context or {}).get("error_source"),
            step=(case.failure_context or {}).get("error_step"),
            reason=(case.failure_context or {}).get("error_reason"),
        )

        evidence = FailureClassifier.classify(
            failure=failure_details,
            raw_context=case.failure_context,
        )

        case.failure_category = evidence.category.value
        case.classification_evidence = evidence.model_dump()
        case.updated_at = utc_now()

        # Record audit event
        audit_event = AuditEventModel(
            case_id=case_id,
            event_type="FAILURE_CLASSIFIED",
            actor=ActorType.SYSTEM.value,
            decision=evidence.category.value,
            action="CLASSIFY_FAILURE",
            outcome="SUCCESS",
            correlation_id=case.failed_payment_id,
            timestamp=utc_now(),
            details=evidence.model_dump(),
        )
        self.session.add(audit_event)
        await self.session.commit()
        logger.info(
            f"Case {case_id} classified as {evidence.category.value} "
            f"(rule: {evidence.matched_rule})."
        )
        return case

    async def evaluate_eligibility(
        self, case_id: str
    ) -> tuple[RecoveryCaseModel, EligibilityDecision]:
        """Evaluate deterministic recovery eligibility against financial safety constraints."""
        case = await self.get_case(case_id)
        current_state = CaseState(case.state)

        # 1. Count customer recovery attempts in the last 24h
        customer_attempts_today = 0
        if case.customer_id:
            twenty_four_hours_ago = utc_now() - timedelta(hours=24)
            count_query = select(func.count(RecoveryCaseModel.case_id)).where(
                RecoveryCaseModel.customer_id == case.customer_id,
                RecoveryCaseModel.case_id != case.case_id,
                RecoveryCaseModel.created_at >= twenty_four_hours_ago,
                RecoveryCaseModel.payment_link_id.isnot(None),
            )
            count_res = await self.session.execute(count_query)
            customer_attempts_today = count_res.scalar() or 0

        # 2. Check if a recovery link has already been created for this case
        has_existing_link = bool(case.payment_link_id)

        # 3. Build PaymentContext
        payment_context = PaymentContext(
            payment_id=case.failed_payment_id,
            order_id=case.order_id,
            customer_id=case.customer_id,
            amount=case.amount,
            currency=case.currency,
            status="failed",
            method=case.payment_method,
            failure=PaymentFailureDetails(
                code=case.failure_code,
                description=case.failure_description,
                source=(case.failure_context or {}).get("error_source"),
                step=(case.failure_context or {}).get("error_step"),
                reason=(case.failure_context or {}).get("error_reason"),
            ),
            created_at=int(case.created_at.timestamp()) if case.created_at else None,
        )

        category_enum = FailureCategory(case.failure_category) if case.failure_category else None

        # 4. Evaluate deterministic eligibility
        decision = EligibilityEngine.evaluate(
            context=payment_context,
            failure_category=category_enum,
            has_existing_recovery_link=has_existing_link,
            customer_attempts_today=customer_attempts_today,
            current_time_utc=utc_now(),
        )

        case.eligibility_status = decision.status.value
        case.eligibility_reason = decision.reason_code.value

        # 5. Transition state based on deterministic outcome
        if decision.status == EligibilityStatus.ELIGIBLE:
            case.state = RecoveryStateMachine.transition(
                current_state, CaseState.ELIGIBILITY_CHECKED
            ).value
        elif decision.status == EligibilityStatus.REQUIRES_ESCALATION:
            case.state = RecoveryStateMachine.transition(current_state, CaseState.ESCALATED).value
        else:
            case.state = RecoveryStateMachine.transition(
                current_state, CaseState.TERMINAL_NO_ACTION
            ).value

        case.updated_at = utc_now()

        # 6. Audit Trail
        audit_event = AuditEventModel(
            case_id=case_id,
            event_type="ELIGIBILITY_EVALUATED",
            actor=ActorType.SYSTEM.value,
            decision=decision.status.value,
            action="EVALUATE_ELIGIBILITY",
            outcome="SUCCESS",
            correlation_id=case.failed_payment_id,
            timestamp=utc_now(),
            details=decision.model_dump(),
        )
        self.session.add(audit_event)
        await self.session.commit()

        logger.info(
            f"Eligibility evaluated for case {case_id}: status={decision.status.value}, "
            f"reason={decision.reason_code.value}, final_state={case.state}."
        )
        return (case, decision)

    async def process_triage_pipeline(
        self,
        case_id: str,
        fetch_from_gateway: bool = True,
    ) -> tuple[RecoveryCaseModel, EligibilityDecision]:
        """Execute full Layer 2 pipeline: Enrichment -> Classification -> Eligibility."""
        # 1. Context Enrichment
        await self.enrich_context(case_id, fetch_from_gateway=fetch_from_gateway)

        # 2. Failure Classification
        await self.classify_case(case_id)

        # 3. Eligibility Evaluation
        return await self.evaluate_eligibility(case_id)
