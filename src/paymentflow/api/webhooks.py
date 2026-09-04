"""Razorpay webhook ingestion endpoint."""

import json
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from paymentflow.adapters.razorpay_adapter import RazorpayAdapter, verify_webhook_signature
from paymentflow.config import Settings, get_settings
from paymentflow.db.models import RecoveryCaseModel
from paymentflow.db.session import get_db_session, get_sessionmaker
from paymentflow.domain.exceptions import WebhookPayloadError
from paymentflow.services.webhook_service import WebhookProcessingResult, WebhookService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


async def _trigger_recovery_orchestration(case_id: str) -> None:
    """Execute durable, idempotent recovery orchestration in background after webhook ACK.

    Runs strictly for MERCHANT_CHECKOUT failures to advance the case through diagnosis,
    eligibility, LLM advisory, guardrails, and Razorpay-native Payment Link creation.
    """
    try:
        sessionmaker = get_sessionmaker()
        async with sessionmaker() as session:
            case = await session.get(RecoveryCaseModel, case_id)
            if not case or case.case_source != "MERCHANT_CHECKOUT":
                return

        from paymentflow.services.recovery_orchestrator import RecoveryOrchestrator

        orchestrator = RecoveryOrchestrator()
        await orchestrator.orchestrate_recovery(case_id=case_id, fetch_from_gateway=False)
        logger.info(f"Background recovery orchestration completed for merchant case {case_id}")
    except Exception as exc:
        logger.error(
            f"Error during background recovery orchestration for merchant case {case_id}: {exc}"
        )


@router.post(
    "/razorpay",
    response_model=WebhookProcessingResult,
    status_code=status.HTTP_200_OK,
    summary="Ingest Razorpay Webhooks",
)
async def handle_razorpay_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_razorpay_signature: str | None = Header(default=None, alias="X-Razorpay-Signature"),
    settings: Settings = Depends(get_settings),
    db: AsyncSession = Depends(get_db_session),
) -> WebhookProcessingResult:
    """Ingest, verify, and process Razorpay webhooks idempotently."""
    raw_body = await request.body()
    logger.info(
        "Incoming webhook request received: size_bytes=%d, signature_present=%s",
        len(raw_body),
        bool(x_razorpay_signature),
    )

    # 1. Verify webhook signature against raw request body
    if not x_razorpay_signature:
        logger.warning("Rejected webhook: Missing 'X-Razorpay-Signature' header.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing X-Razorpay-Signature header.",
        )

    is_valid = verify_webhook_signature(
        raw_body=raw_body,
        signature=x_razorpay_signature,
        secret=settings.razorpay_webhook_secret,
    )

    if not is_valid:
        logger.warning("Rejected webhook: Invalid X-Razorpay-Signature.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid webhook signature.",
        )

    logger.info("Webhook HMAC-SHA256 signature verified successfully.")

    # 2. Parse JSON payload
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except Exception as exc:
        logger.error(f"Malformed JSON in webhook request body: {exc}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Malformed JSON in request body.",
        )

    # 3. Process webhook idempotently
    try:
        adapter = RazorpayAdapter(settings=settings)
        service = WebhookService(db, razorpay_adapter=adapter)
        result = await service.process_webhook(
            raw_body=raw_body,
            payload=payload,
            signature_verified=True,
        )
        if result.event_type == "payment.failed" and result.case_id and not result.is_duplicate:
            background_tasks.add_task(_trigger_recovery_orchestration, result.case_id)
        return result
    except WebhookPayloadError as exc:
        logger.warning(f"Invalid webhook payload: {exc}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except Exception as exc:
        logger.error(f"Internal server error processing webhook: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal error processing webhook.",
        )
