"""Razorpay webhook ingestion endpoint."""

import json
import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from paymentflow.adapters.razorpay_adapter import RazorpayAdapter, verify_webhook_signature
from paymentflow.config import Settings, get_settings
from paymentflow.db.session import get_db_session
from paymentflow.domain.exceptions import WebhookPayloadError
from paymentflow.services.webhook_service import WebhookProcessingResult, WebhookService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


@router.post(
    "/razorpay",
    response_model=WebhookProcessingResult,
    status_code=status.HTTP_200_OK,
    summary="Ingest Razorpay Webhooks",
)
async def handle_razorpay_webhook(
    request: Request,
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
        return await service.process_webhook(
            raw_body=raw_body,
            payload=payload,
            signature_verified=True,
        )
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
