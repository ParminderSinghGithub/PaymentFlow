"""Merchant integration API router.

Exposes the minimal server-to-server integration boundary for external merchant
storefronts. Authenticates requests via Bearer API keys and registers checkout context
without executing recovery actions.
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from paymentflow.db.models import utc_now
from paymentflow.merchant.auth import get_authenticated_merchant
from paymentflow.merchant.models import AuthenticatedMerchantContext
from paymentflow.merchant.schemas import (
    MerchantCheckoutContextRequest,
    MerchantCheckoutContextResponse,
    MerchantVerifyResponse,
)

logger = logging.getLogger("paymentflow.api.merchant")

router = APIRouter(prefix="/merchant/v1", tags=["Merchant Integration"])


@router.get(
    "/verify",
    response_model=MerchantVerifyResponse,
    summary="Verify Merchant API Credentials",
)
async def verify_merchant_credentials(
    merchant: AuthenticatedMerchantContext = Depends(get_authenticated_merchant),
) -> MerchantVerifyResponse:
    """Verify that merchant server credentials are authentic and active.

    Returns the public merchant identity and associated Razorpay Key ID.
    Never exposes Razorpay Key Secret or PaymentFlow API keys.
    """
    return MerchantVerifyResponse(
        status="authenticated",
        merchant_id=merchant.merchant_id,
        merchant_name=merchant.merchant_name,
        razorpay_key_id=merchant.razorpay_key_id,
        is_active=merchant.is_active,
        message="Merchant API credential authenticated successfully.",
    )


@router.post(
    "/checkout-context",
    response_model=MerchantCheckoutContextResponse,
    status_code=status.HTTP_200_OK,
    summary="Register Merchant Checkout Context",
)
async def register_checkout_context(
    payload: MerchantCheckoutContextRequest,
    merchant: AuthenticatedMerchantContext = Depends(get_authenticated_merchant),
) -> MerchantCheckoutContextResponse:
    """Register checkout failure or attempt context from external merchant server.

    Authenticates the merchant via Bearer token, enforces identity invariants,
    and returns a stable registration confirmation. Does not execute recovery
    actions in this phase (Phase C3.1).
    """
    # Enforce identity invariant: Request-body merchant_id cannot impersonate another merchant
    if payload.merchant_id and payload.merchant_id != merchant.merchant_id:
        logger.warning(
            f"Impersonation attempt detected: authenticated merchant '{merchant.merchant_id}' "
            f"attempted to submit payload with merchant_id '{payload.merchant_id}'."
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Forbidden: Request body merchant_id '{payload.merchant_id}' "
                f"does not match authenticated credentials for '{merchant.merchant_id}'."
            ),
        )

    now = utc_now()
    context_id = f"mctx_{uuid.uuid4().hex[:16]}"

    logger.info(
        f"Registered checkout context '{context_id}' for merchant '{merchant.merchant_id}' "
        f"[order_id={payload.external_order_id}, amount={payload.amount} {payload.currency}]"
    )

    return MerchantCheckoutContextResponse(
        status="accepted",
        context_id=context_id,
        merchant_id=merchant.merchant_id,
        external_order_id=payload.external_order_id,
        external_payment_id=payload.external_payment_id,
        amount=payload.amount,
        currency=payload.currency,
        customer_email=payload.customer_email,
        customer_phone=payload.customer_phone,
        registered_at=now,
        message="Merchant checkout context registered successfully for recovery monitoring.",
    )
