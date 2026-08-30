"""Webhook ingestion and processing service with strict idempotency."""

import hashlib
import logging
from typing import Any

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

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
    """Handles webhook ingestion, database-level idempotency, and recovery case creation."""

    def __init__(self, db_session: AsyncSession):
        self.session = db_session

    @staticmethod
    def extract_event_id(payload: dict[str, Any], raw_body: bytes) -> str:
        """Extract or generate a deterministic event identifier from the webhook payload."""
        # Check standard Razorpay event identifiers
        if "id" in payload and payload["id"]:
            return str(payload["id"])
        if "event_id" in payload and payload["event_id"]:
            return str(payload["event_id"])

        # If payload contains payment id and event type, derive a deterministic ID
        payment_id = payload.get("payload", {}).get("payment", {}).get("entity", {}).get("id")
        event_type = payload.get("event", "unknown")
        created_at = payload.get("created_at", "")

        if payment_id:
            return f"evt_{payment_id}_{event_type}_{created_at}"

        # Fallback to SHA256 of raw body
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
            # 3. Handle supported events
            if event_type == "payment.failed":
                processing_res = await self._handle_payment_failed(event_id, payload)
                webhook_event.status = WebhookStatus.PROCESSED.value
                webhook_event.processed_at = utc_now()
                await self.session.commit()
                return processing_res
            else:
                # Unsupported event for recovery in Layer 1
                logger.info(
                    f"Valid Razorpay event '{event_type}' received but not processed in Layer 1."
                )
                webhook_event.status = WebhookStatus.IGNORED.value
                webhook_event.processed_at = utc_now()
                await self.session.commit()
                return WebhookProcessingResult(
                    status="ok",
                    event_id=event_id,
                    event_type=event_type,
                    is_duplicate=False,
                    message=f"Event type '{event_type}' ignored in Layer 1.",
                )
        except IntegrityError as exc:
            # Handle potential concurrency race condition on unique keys
            logger.warning(
                f"Integrity conflict during webhook processing: {exc}. Rolling back."
            )
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
        query = select(RecoveryCaseModel).where(
            RecoveryCaseModel.failed_payment_id == payment_id
        )
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

        # Generate deterministic Case ID
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

        # Record initial audit event
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
