"""Webhook ingestion and processing service with strict idempotency and revenue attribution."""

import hashlib
import logging
from typing import Any

from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from paymentflow.adapters.razorpay_adapter import RazorpayAdapter
from paymentflow.db.models import (
    AuditEventModel,
    RecoveryCaseModel,
    WebhookEventModel,
    utc_now,
)
from paymentflow.domain.enums import ActorType, CaseState, WebhookStatus
from paymentflow.domain.exceptions import WebhookPayloadError

logger = logging.getLogger(__name__)


class WebhookProcessingResult(BaseModel):
    """Structured response from webhook event processing."""

    status: str
    event_id: str
    event_type: str
    is_duplicate: bool = False
    case_id: str | None = None
    state: str | None = None
    message: str | None = None


class WebhookService:
    """Handles webhook ingestion, database-level idempotency, and recovery revenue attribution."""

    def __init__(
        self,
        db_session: AsyncSession,
        razorpay_adapter: RazorpayAdapter | None = None,
    ):
        self.session = db_session
        self.razorpay_adapter = razorpay_adapter

    @staticmethod
    def extract_event_id(payload: dict[str, Any], raw_body: bytes) -> str:
        """Extract or generate a deterministic event identifier from the webhook payload."""
        if "id" in payload and payload["id"]:
            return str(payload["id"])
        if "event_id" in payload and payload["event_id"]:
            return str(payload["event_id"])

        payment_id = payload.get("payload", {}).get("payment", {}).get("entity", {}).get("id")
        plink_id = payload.get("payload", {}).get("payment_link", {}).get("entity", {}).get("id")
        event_type = payload.get("event", "unknown")
        created_at = payload.get("created_at", "")

        if payment_id or plink_id:
            entity_id = payment_id or plink_id
            return f"evt_{entity_id}_{event_type}_{created_at}"

        return f"evt_hash_{hashlib.sha256(raw_body).hexdigest()[:24]}"

    async def process_webhook(
        self,
        raw_body: bytes,
        payload: dict[str, Any],
        signature_verified: bool,
    ) -> WebhookProcessingResult:
        """Process an incoming webhook transactionally with database-backed idempotency."""
        if not isinstance(payload, dict):
            raise WebhookPayloadError("Webhook payload must be a valid JSON object.")

        event_type = payload.get("event")
        if not event_type:
            raise WebhookPayloadError("Missing required 'event' field in webhook payload.")

        event_id = self.extract_event_id(payload, raw_body)
        logger.info(f"Ingesting webhook event: ID={event_id}, type={event_type}")

        # 1. Check idempotency: Has this event_id already been persisted?
        query = select(WebhookEventModel).where(WebhookEventModel.event_id == event_id)
        result = await self.session.execute(query)
        existing_event = result.scalar_one_or_none()

        if existing_event is not None:
            logger.info(
                f"Duplicate webhook event detected: ID={event_id}. Suppressing duplicate actions."
            )
            return WebhookProcessingResult(
                status="ok",
                event_id=event_id,
                event_type=event_type,
                is_duplicate=True,
                message="Duplicate event ignored.",
            )

        # 2. Persist new webhook event record
        webhook_event = WebhookEventModel(
            event_id=event_id,
            event_type=event_type,
            payload=payload,
            signature_verified=signature_verified,
            received_at=utc_now(),
            status=WebhookStatus.RECEIVED.value,
        )
        self.session.add(webhook_event)

        try:
            # 3. Route supported events
            if event_type == "payment.failed":
                processing_res = await self._handle_payment_failed(event_id, payload)
                webhook_event.status = WebhookStatus.PROCESSED.value
                webhook_event.processed_at = utc_now()
                await self.session.commit()
                return processing_res

            elif event_type in {"payment_link.paid", "payment.captured"}:
                processing_res = await self._handle_payment_outcome(event_id, event_type, payload)
                webhook_event.status = WebhookStatus.PROCESSED.value
                webhook_event.processed_at = utc_now()
                await self.session.commit()
                return processing_res

            else:
                logger.info(f"Razorpay event '{event_type}' received but not processed.")
                webhook_event.status = WebhookStatus.IGNORED.value
                webhook_event.processed_at = utc_now()
                await self.session.commit()
                return WebhookProcessingResult(
                    status="ok",
                    event_id=event_id,
                    event_type=event_type,
                    is_duplicate=False,
                    message=f"Event type '{event_type}' ignored.",
                )

        except IntegrityError as exc:
            logger.warning(f"Integrity conflict during webhook processing: {exc}. Rolling back.")
            await self.session.rollback()
            return WebhookProcessingResult(
                status="ok",
                event_id=event_id,
                event_type=event_type,
                is_duplicate=True,
                message="Concurrent duplicate event handled safely.",
            )
        except Exception as exc:
            logger.error(f"Error processing webhook event {event_id}: {exc}")
            await self.session.rollback()
            raise

    async def _handle_payment_failed(
        self, event_id: str, payload: dict[str, Any]
    ) -> WebhookProcessingResult:
        """Extract failed payment data and persist recovery case."""
        payment_entity = payload.get("payload", {}).get("payment", {}).get("entity")
        if not payment_entity or not isinstance(payment_entity, dict):
            raise WebhookPayloadError(
                "Malformed 'payment.failed' payload: missing 'payload.payment.entity'."
            )

        payment_id = payment_entity.get("id")
        if not payment_id:
            raise WebhookPayloadError("Missing required 'id' in payment entity.")

        amount = payment_entity.get("amount")
        if amount is None or not isinstance(amount, (int, float)):
            raise WebhookPayloadError("Missing or invalid 'amount' in payment entity.")

        currency = payment_entity.get("currency", "INR")
        order_id = payment_entity.get("order_id")
        customer_id = payment_entity.get("customer_id")
        payment_method = payment_entity.get("method")
        error_code = payment_entity.get("error_code")
        error_description = payment_entity.get("error_description")

        failure_context = {
            "error_code": error_code,
            "error_description": error_description,
            "error_source": payment_entity.get("error_source"),
            "error_step": payment_entity.get("error_step"),
            "error_reason": payment_entity.get("error_reason"),
            "email": payment_entity.get("email"),
            "contact": payment_entity.get("contact"),
            "description": payment_entity.get("description"),
            "notes": payment_entity.get("notes", {}),
        }

        # Check if recovery case for this payment ID already exists
        query = select(RecoveryCaseModel).where(RecoveryCaseModel.failed_payment_id == payment_id)
        result = await self.session.execute(query)
        existing_case = result.scalar_one_or_none()

        if existing_case is not None:
            logger.info(
                f"Recovery case already exists for payment {payment_id}: "
                f"Case ID={existing_case.case_id}"
            )
            return WebhookProcessingResult(
                status="ok",
                event_id=event_id,
                event_type="payment.failed",
                is_duplicate=False,
                case_id=existing_case.case_id,
                state=existing_case.state,
                message="Case already exists for this failed payment.",
            )

        case_id = f"case_{payment_id}"

        recovery_case = RecoveryCaseModel(
            case_id=case_id,
            failed_payment_id=payment_id,
            order_id=order_id,
            customer_id=customer_id,
            amount=int(amount),
            currency=currency,
            payment_method=payment_method,
            failure_code=error_code,
            failure_description=error_description,
            failure_context=failure_context,
            state=CaseState.FAILED_INGESTED.value,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        self.session.add(recovery_case)

        audit_event = AuditEventModel(
            case_id=case_id,
            event_type="WEBHOOK_INGESTED",
            actor=ActorType.SYSTEM.value,
            decision="CASE_CREATED",
            action="INGEST_FAILED_PAYMENT",
            outcome="SUCCESS",
            correlation_id=event_id,
            timestamp=utc_now(),
            details={
                "failed_payment_id": payment_id,
                "amount": amount,
                "currency": currency,
                "error_code": error_code,
            },
        )
        self.session.add(audit_event)

        logger.info(
            f"Created recovery case {case_id} for failed payment {payment_id} "
            f"(amount={amount} {currency})"
        )

        return WebhookProcessingResult(
            status="ok",
            event_id=event_id,
            event_type="payment.failed",
            is_duplicate=False,
            case_id=case_id,
            state=CaseState.FAILED_INGESTED.value,
            message="Recovery case created successfully.",
        )

    async def _handle_payment_outcome(
        self, event_id: str, event_type: str, payload: dict[str, Any]
    ) -> WebhookProcessingResult:
        """Handle payment_link.paid / payment.captured with verification and revenue attribution."""
        payload_container = payload.get("payload", {})
        plink_entity = payload_container.get("payment_link", {}).get("entity") or {}
        payment_entity = payload_container.get("payment", {}).get("entity") or {}

        plink_id = plink_entity.get("id") or payment_entity.get("payment_link_id")
        payment_id = payment_entity.get("id")

        notes = plink_entity.get("notes") or payment_entity.get("notes") or {}
        case_id_from_notes = notes.get("case_id")
        failed_payment_id_from_notes = notes.get("failed_payment_id")

        # 1. Correlate with Recovery Case using row-level lock
        conditions = []
        if plink_id:
            conditions.append(RecoveryCaseModel.payment_link_id == plink_id)
        if case_id_from_notes:
            conditions.append(RecoveryCaseModel.case_id == case_id_from_notes)
        if failed_payment_id_from_notes:
            conditions.append(RecoveryCaseModel.failed_payment_id == failed_payment_id_from_notes)

        if not conditions:
            logger.warning(
                f"Webhook {event_id} ({event_type}): No correlation identifiers found in payload."
            )
            return WebhookProcessingResult(
                status="ok",
                event_id=event_id,
                event_type=event_type,
                message="No correlation identifiers in payload.",
            )

        query = select(RecoveryCaseModel).where(or_(*conditions)).with_for_update()
        result = await self.session.execute(query)
        case = result.scalar_one_or_none()

        if not case:
            logger.warning(
                f"Webhook {event_id} ({event_type}): No matching recovery case found for "
                f"plink_id={plink_id}, case_id={case_id_from_notes}. Recording anomaly."
            )
            audit = AuditEventModel(
                case_id=None,
                event_type="UNMATCHED_RECOVERY_PAYMENT",
                actor=ActorType.SYSTEM.value,
                decision="ANOMALY",
                outcome="UNMATCHED",
                correlation_id=event_id,
                timestamp=utc_now(),
                details={
                    "event_type": event_type,
                    "payment_id": payment_id,
                    "payment_link_id": plink_id,
                    "notes": notes,
                },
            )
            self.session.add(audit)
            return WebhookProcessingResult(
                status="ok",
                event_id=event_id,
                event_type=event_type,
                message="Unmatched recovery payment.",
            )

        # 2. Single Attribution Invariant & Idempotency Check
        if case.state == CaseState.RECOVERED.value or case.recovered_payment_id == payment_id:
            logger.info(
                f"Webhook {event_id}: Case '{case.case_id}' already has recovered payment "
                f"'{case.recovered_payment_id}'. Suppressing duplicate attribution."
            )
            audit = AuditEventModel(
                case_id=case.case_id,
                event_type="PAYMENT_LINK_WEBHOOK_DUPLICATE",
                actor=ActorType.SYSTEM.value,
                decision="SUPPRESS_DUPLICATE",
                correlation_id=event_id,
                timestamp=utc_now(),
                details={
                    "existing_recovered_payment_id": case.recovered_payment_id,
                    "incoming_payment_id": payment_id,
                },
            )
            self.session.add(audit)
            return WebhookProcessingResult(
                status="ok",
                event_id=event_id,
                event_type=event_type,
                is_duplicate=True,
                case_id=case.case_id,
                state=case.state,
                message="Recovery case already attributed.",
            )

        # 3. Independent Payment Verification
        payment_status = payment_entity.get("status")
        payment_amount = payment_entity.get("amount")
        payment_currency = payment_entity.get("currency", "INR")

        if self.razorpay_adapter and payment_id:
            self.session.add(
                AuditEventModel(
                    case_id=case.case_id,
                    event_type="PAYMENT_VERIFICATION_REQUESTED",
                    actor=ActorType.SYSTEM.value,
                    action="verify_payment",
                    correlation_id=event_id,
                    timestamp=utc_now(),
                    details={"payment_id": payment_id},
                )
            )
            try:
                verified_data = await self.razorpay_adapter.get_payment(payment_id)
                payment_status = verified_data.get("status")
                payment_amount = verified_data.get("amount")
                payment_currency = verified_data.get("currency", "INR")
            except Exception as exc:
                logger.error(
                    f"Payment verification API call failed for payment '{payment_id}': {exc}. "
                    "Halting attribution; moving to unresolved VERIFICATION state."
                )
                case.state = CaseState.VERIFICATION.value
                case.updated_at = utc_now()

                self.session.add(
                    AuditEventModel(
                        case_id=case.case_id,
                        event_type="PAYMENT_VERIFICATION_FAILED",
                        actor=ActorType.SYSTEM.value,
                        decision="UNRESOLVED",
                        outcome="VERIFICATION_API_UNAVAILABLE",
                        correlation_id=event_id,
                        timestamp=utc_now(),
                        details={
                            "error": str(exc),
                            "payment_id": payment_id,
                            "requires_retry": True,
                        },
                    )
                )
                return WebhookProcessingResult(
                    status="ok",
                    event_id=event_id,
                    event_type=event_type,
                    case_id=case.case_id,
                    state=case.state,
                    message="Payment verification API unavailable; attribution unresolved.",
                )

        # 4. Strict Captured-Only Status Verification
        if payment_status != "captured":
            logger.warning(
                f"Webhook {event_id}: Payment '{payment_id}' status is '{payment_status}'. "
                "Only 'captured' payments are eligible for recovery attribution."
            )
            audit = AuditEventModel(
                case_id=case.case_id,
                event_type="RECOVERY_ATTRIBUTION_REJECTED",
                actor=ActorType.SYSTEM.value,
                decision="REJECTED",
                outcome="PAYMENT_NOT_CAPTURED",
                correlation_id=event_id,
                timestamp=utc_now(),
                details={"status": payment_status, "payment_id": payment_id},
            )
            self.session.add(audit)
            return WebhookProcessingResult(
                status="ok",
                event_id=event_id,
                event_type=event_type,
                case_id=case.case_id,
                state=case.state,
                message=f"Payment status '{payment_status}' is not captured.",
            )

        # 5. Amount and Currency Integrity Verification
        verified_amount = int(payment_amount) if payment_amount is not None else 0
        if verified_amount != case.amount or payment_currency != case.currency:
            logger.warning(
                f"Webhook {event_id}: Amount/currency mismatch for case '{case.case_id}': "
                f"expected {case.amount} {case.currency}, "
                f"got {verified_amount} {payment_currency}. "
                "Rejecting attribution and escalating."
            )
            case.state = CaseState.ESCALATED.value
            case.updated_at = utc_now()

            self.session.add(
                AuditEventModel(
                    case_id=case.case_id,
                    event_type="RECOVERY_AMOUNT_MISMATCH",
                    actor=ActorType.SYSTEM.value,
                    decision="MISMATCH_DETECTED",
                    outcome="AMOUNT_MISMATCH",
                    correlation_id=event_id,
                    timestamp=utc_now(),
                    details={
                        "expected_amount": case.amount,
                        "actual_amount": verified_amount,
                        "expected_currency": case.currency,
                        "actual_currency": payment_currency,
                        "payment_id": payment_id,
                    },
                )
            )
            self.session.add(
                AuditEventModel(
                    case_id=case.case_id,
                    event_type="RECOVERY_ATTRIBUTION_REJECTED",
                    actor=ActorType.SYSTEM.value,
                    decision="REJECTED",
                    outcome="AMOUNT_MISMATCH",
                    correlation_id=event_id,
                    timestamp=utc_now(),
                    details={"reason": "AMOUNT_MISMATCH"},
                )
            )
            return WebhookProcessingResult(
                status="ok",
                event_id=event_id,
                event_type=event_type,
                case_id=case.case_id,
                state=case.state,
                message="Amount/currency mismatch detected; attribution rejected.",
            )

        # 5. Persist Verified Attribution & Transition State to RECOVERED
        case.recovered_payment_id = payment_id
        case.recovered_amount = verified_amount
        case.payment_link_status = "paid"
        case.state = CaseState.RECOVERED.value
        case.updated_at = utc_now()

        self.session.add(
            AuditEventModel(
                case_id=case.case_id,
                event_type="PAYMENT_VERIFIED",
                actor=ActorType.SYSTEM.value,
                decision="VERIFIED",
                correlation_id=event_id,
                timestamp=utc_now(),
                details={
                    "payment_id": payment_id,
                    "amount_paise": verified_amount,
                    "currency": payment_currency,
                },
            )
        )
        self.session.add(
            AuditEventModel(
                case_id=case.case_id,
                event_type="RECOVERY_ATTRIBUTED",
                actor=ActorType.SYSTEM.value,
                decision="ATTRIBUTED",
                action="ATTRIBUTE_REVENUE",
                outcome="SUCCESS",
                correlation_id=event_id,
                timestamp=utc_now(),
                details={
                    "recovered_payment_id": payment_id,
                    "recovered_amount_paise": verified_amount,
                    "currency": payment_currency,
                    "payment_link_id": plink_id or case.payment_link_id,
                },
            )
        )

        logger.info(
            f"Recovery Attributed: Case '{case.case_id}' successfully recovered "
            f"₹{verified_amount / 100:.2f} via payment '{payment_id}'."
        )

        return WebhookProcessingResult(
            status="ok",
            event_id=event_id,
            event_type=event_type,
            case_id=case.case_id,
            state=CaseState.RECOVERED.value,
            message="Payment verified and recovered revenue attributed.",
        )
