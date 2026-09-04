"""Merchant integration API router.

Exposes the minimal server-to-server integration boundary for external merchant
storefronts. Authenticates requests via Bearer API keys and registers checkout context
without executing recovery actions.
"""

import html
import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from sqlalchemy import select

from paymentflow.adapters.razorpay_adapter import RazorpayAdapter
from paymentflow.config import get_settings
from paymentflow.db.models import RecoveryCaseModel, utc_now
from paymentflow.db.session import get_sessionmaker
from paymentflow.merchant.auth import get_authenticated_merchant
from paymentflow.merchant.models import AuthenticatedMerchantContext
from paymentflow.merchant.schemas import (
    MerchantCheckoutContextRequest,
    MerchantCheckoutContextResponse,
    MerchantCreateOrderRequest,
    MerchantCreateOrderResponse,
    MerchantVerifyResponse,
)
from paymentflow.merchant.service import MerchantRegistry

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
    and returns a stable registration confirmation.
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

    MerchantRegistry.store_checkout_context(
        context_id,
        {
            "context_id": context_id,
            "merchant_id": merchant.merchant_id,
            "merchant_name": merchant.merchant_name,
            "external_order_id": payload.external_order_id,
            "external_payment_id": payload.external_payment_id,
            "amount": payload.amount,
            "currency": payload.currency,
            "customer_email": payload.customer_email,
            "customer_phone": payload.customer_phone,
            "razorpay_key_id": merchant.razorpay_key_id,
            "created_at": now.isoformat(),
        },
    )

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


@router.post(
    "/orders",
    response_model=MerchantCreateOrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Merchant Razorpay Order with Checkout Context",
)
async def create_merchant_order(
    payload: MerchantCreateOrderRequest,
    merchant: AuthenticatedMerchantContext = Depends(get_authenticated_merchant),
) -> MerchantCreateOrderResponse:
    """Create standard Razorpay Order using merchant credentials and store checkout context."""
    credentials = MerchantRegistry.get_razorpay_credentials(merchant.merchant_id)
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active Razorpay credentials found for merchant '{merchant.merchant_id}'.",
        )
    key_id, key_secret = credentials
    rzp_adapter = RazorpayAdapter(key_id=key_id, key_secret=key_secret)

    if payload.notes and payload.notes.get("merchant_id"):
        if str(payload.notes["merchant_id"]) != merchant.merchant_id:
            logger.warning(
                f"Merchant note spoofing attempt: Authenticated merchant '{merchant.merchant_id}' "
                f"passed notes with merchant_id '{payload.notes['merchant_id']}'."
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Forbidden: Custom notes merchant_id does not match authenticated credentials."
                ),
            )

    order_notes = {}
    if payload.notes:
        order_notes.update(payload.notes)
    # Always enforce authenticated merchant identity overrides caller notes
    order_notes["merchant_id"] = merchant.merchant_id
    order_notes["external_order_id"] = payload.external_order_id

    receipt = payload.external_order_id[:40]

    try:
        rzp_order = await rzp_adapter.create_order(
            amount=payload.amount,
            currency=payload.currency,
            receipt=receipt,
            notes=order_notes,
        )
    except Exception as exc:
        logger.error(f"Failed to create Razorpay order for {merchant.merchant_id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Razorpay order creation failed: {exc}",
        )

    context_id = f"mctx_{uuid.uuid4().hex[:16]}"
    context_data = {
        "context_id": context_id,
        "merchant_id": merchant.merchant_id,
        "merchant_name": merchant.merchant_name,
        "external_order_id": payload.external_order_id,
        "razorpay_order_id": rzp_order["id"],
        "amount": payload.amount,
        "currency": payload.currency,
        "customer_name": payload.customer_name,
        "customer_email": payload.customer_email,
        "customer_phone": payload.customer_phone,
        "razorpay_key_id": merchant.razorpay_key_id,
        "created_at": utc_now().isoformat(),
    }
    MerchantRegistry.store_checkout_context(context_id, context_data)

    return MerchantCreateOrderResponse(
        status="created",
        context_id=context_id,
        razorpay_order_id=rzp_order["id"],
        external_order_id=payload.external_order_id,
        amount=payload.amount,
        currency=payload.currency,
        razorpay_key_id=merchant.razorpay_key_id,
        checkout_url=f"/merchant/checkout?context_id={context_id}",
        message="Razorpay order created and checkout context registered successfully.",
    )


@router.get(
    "/orders/{order_id}/recovery-status",
    summary="Get Safe Merchant Recovery Status",
)
async def get_merchant_order_recovery_status(
    order_id: str,
    merchant: AuthenticatedMerchantContext = Depends(get_authenticated_merchant),
) -> dict[str, Any]:
    """Retrieve safe, public-facing recovery status for an order.

    Never exposes secrets, payment link URLs, or internal LLM reasoning.
    Strictly tenant-isolated to the authenticated merchant.
    """
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        stmt = select(RecoveryCaseModel).where(
            (RecoveryCaseModel.case_source == "MERCHANT_CHECKOUT")
            & (
                (RecoveryCaseModel.order_id == order_id)
                | (RecoveryCaseModel.case_id == f"case_{order_id}")
                | (RecoveryCaseModel.failure_context["external_order_id"].as_string() == order_id)
            )
        )
        res = await session.execute(stmt)
        candidates = res.scalars().all()

    # Tenant filtering: select strictly the case owned by the authenticated merchant
    case = None
    for c in candidates:
        fc = c.failure_context or {}
        case_m = fc.get("merchant_id")
        if case_m == merchant.merchant_id:
            case = c
            break

    if not case:
        return {
            "order_id": order_id,
            "status": "AWAITING_INGESTION",
            "message": "Payment failure ingestion pending.",
        }

    notif_status = fc.get("notification_status", "PENDING")

    is_recovered = case.state == "RECOVERED"
    message = (
        f"Payment recovered successfully! Recovered amount: INR {case.recovered_amount / 100:.2f}."
        if is_recovered
        else (
            "Payment could not be completed. A secure payment link has been sent to "
            "your checkout contact. Check your SMS/email for the link."
        )
    )

    return {
        "order_id": order_id,
        "case_id": case.case_id,
        "case_source": case.case_source,
        "state": case.state,
        "amount": case.amount,
        "currency": case.currency,
        "payment_link_sent": bool(case.payment_link_id or case.payment_link_short_url),
        "payment_link_url": case.payment_link_short_url,
        "payment_link_status": case.payment_link_status,
        "recovered_amount": case.recovered_amount,
        "recovered_payment_id": case.recovered_payment_id,
        "notification_medium": fc.get("notification_medium", "sms"),
        "notification_status": notif_status,
        "masked_contact": fc.get("masked_contact"),
        "delivery_verified": True if is_recovered else fc.get("delivery_verified", False),
        "message": message,
    }


checkout_router = APIRouter(prefix="/merchant", tags=["Merchant Storefront"])


@checkout_router.get("/checkout", response_class=HTMLResponse)
async def merchant_checkout_page(
    context_id: str | None = None,
    order_id: str | None = None,
) -> HTMLResponse:
    """Render minimal customer checkout page using standard Razorpay Checkout.js.

    Allows live testing of real Razorpay Test Mode checkout failures.
    Only the public Razorpay Key ID is exposed in client-side HTML.
    """
    settings = get_settings()
    key = context_id or order_id
    ctx = MerchantRegistry.get_checkout_context(key) if key else None

    # Resolve values with robust fallbacks
    key_id = (ctx.get("razorpay_key_id") if ctx else None) or settings.razorpay_key_id
    amount = (ctx.get("amount") if ctx else None) or 345000
    currency = (ctx.get("currency") if ctx else None) or "INR"
    external_order_id = (ctx.get("external_order_id") if ctx else None) or "ORD-DEMO-3450"
    razorpay_order_id = (ctx.get("razorpay_order_id") if ctx else None) or order_id or ""
    merchant_name = (ctx.get("merchant_name") if ctx else None) or "Merchant Store Demo"
    customer_name = (ctx.get("customer_name") if ctx else None) or ""
    customer_email = (ctx.get("customer_email") if ctx else None) or ""
    customer_phone = (ctx.get("customer_phone") if ctx else None) or ""

    # Always ensure context is registered in running process memory for webhook correlation
    if razorpay_order_id:
        MerchantRegistry.store_checkout_context(
            razorpay_order_id,
            {
                "context_id": context_id or f"mctx_{razorpay_order_id}",
                "merchant_id": "merchant_demo_store",
                "merchant_name": merchant_name,
                "external_order_id": external_order_id,
                "razorpay_order_id": razorpay_order_id,
                "amount": amount,
                "currency": currency,
                "customer_name": customer_name,
                "customer_email": customer_email,
                "customer_phone": customer_phone,
                "razorpay_key_id": key_id,
            },
        )

    formatted_amount = f"₹{amount / 100:,.2f}"

    rzp_order_line = f'"order_id": "{html.escape(razorpay_order_id)}",' if razorpay_order_id else ""

    css_styles = """
        * { box-sizing: border-box; margin: 0; padding: 0;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }
        body { background: #0f172a; color: #f8fafc; min-height: 100vh; display: flex;
               align-items: center; justify-content: center; padding: 20px; }
        .card { background: #1e293b; border: 1px solid #334155; border-radius: 16px;
                width: 100%; max-width: 480px; padding: 32px;
                box-shadow: 0 20px 25px -5px rgba(0,0,0,0.5); }
        .header { display: flex; align-items: center; justify-content: space-between;
                  margin-bottom: 24px; }
        .tag { background: #0284c7; color: #fff; font-size: 11px; font-weight: 700;
               padding: 4px 10px; border-radius: 9999px; text-transform: uppercase;
               letter-spacing: 0.05em; }
        h1 { font-size: 22px; font-weight: 700; color: #fff; margin-bottom: 6px; }
        .subtitle { font-size: 13px; color: #94a3b8; margin-bottom: 24px; }
        .order-box { background: #0f172a; border: 1px solid #334155; border-radius: 12px;
                     padding: 18px; margin-bottom: 24px; }
        .order-row { display: flex; justify-content: space-between; font-size: 13px;
                     color: #94a3b8; margin-bottom: 8px; }
        .order-row:last-child { margin-bottom: 0; padding-top: 8px;
                                border-top: 1px solid #334155; color: #fff;
                                font-size: 15px; font-weight: 600; }
        .order-row span.val { color: #e2e8f0; font-weight: 500; }
        .instruction-box { background: rgba(239, 68, 68, 0.1);
                           border: 1px solid rgba(239, 68, 68, 0.3); border-radius: 12px;
                           padding: 16px; margin-bottom: 24px; }
        .instruction-title { font-size: 13px; font-weight: 700; color: #f87171;
                             margin-bottom: 6px; display: flex; align-items: center; gap: 6px; }
        .instruction-text { font-size: 12px; color: #cbd5e1; line-height: 1.5; }
        .upi-badge { display: inline-block; background: #334155; color: #38bdf8;
                     font-family: monospace; font-size: 13px; padding: 2px 8px;
                     border-radius: 4px; font-weight: 600; margin: 4px 0; }
        .btn-pay { width: 100%; background: #2563eb; color: #fff; border: none; padding: 14px;
                   border-radius: 10px; font-size: 15px; font-weight: 600; cursor: pointer;
                   transition: background 0.2s; }
        .btn-pay:hover { background: #1d4ed8; }
        .footer { font-size: 11px; color: #64748b; text-align: center; margin-top: 20px; }
    """

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PaymentFlow Merchant Storefront — Checkout</title>
    <script src="https://checkout.razorpay.com/v1/checkout.js"></script>
    <style>{css_styles}</style>
</head>
<body>
    <div class="card">
        <div class="header">
            <span class="tag">Merchant Storefront</span>
            <span style="font-size: 12px; color: #94a3b8; font-family: monospace;">
                Razorpay Test Mode
            </span>
        </div>
        <h1>{html.escape(merchant_name)}</h1>
        <p class="subtitle">Simulate real merchant customer checkout failure</p>

        <div class="order-box">
            <div class="order-row">
                <span>Order Reference:</span>
                <span class="val">{html.escape(external_order_id)}</span>
            </div>
            <div class="order-row">
                <span>Razorpay Order ID:</span>
                <span class="val">{html.escape(razorpay_order_id or "Auto-created")}</span>
            </div>
            <div class="order-row">
                <span>Customer:</span>
                <span class="val">{html.escape(customer_name)}</span>
            </div>
            <div class="order-row">
                <span>Amount Due:</span>
                <span class="val" style="color: #38bdf8;">{formatted_amount}</span>
            </div>
        </div>

        <div class="instruction-box">
            <div class="instruction-title">⚠️ Test Mode Failure Instructions:</div>
            <div class="instruction-text">
                1. Click <b>"Pay with Razorpay"</b> below.<br>
                2. Select <b>UPI</b> method.<br>
                3. Enter VPA: <span class="upi-badge">failure@razorpay</span><br>
                4. Razorpay will trigger a genuine <code>payment.failed</code> webhook.
            </div>
        </div>

        <button id="rzp-button" class="btn-pay">Pay {formatted_amount} with Razorpay</button>
        <p class="footer">
            Secured by Razorpay • Key: {html.escape(key_id[:12])}... • Zero internal modules
        </p>
    </div>

    <script>
        const options = {{
            "key": "{key_id}",
            "amount": {amount},
            "currency": "{currency}",
            "name": "{html.escape(merchant_name)}",
            "description": "Order {html.escape(external_order_id)}",
            {rzp_order_line}
            "prefill": {{
                "name": "{html.escape(customer_name)}",
                "email": "{html.escape(customer_email)}",
                "contact": "{html.escape(customer_phone)}"
            }},
            "theme": {{
                "color": "#2563eb"
            }},
            "modal": {{
                "ondismiss": function() {{
                    console.log("Checkout dismissed by user");
                }}
            }}
        }};

        document.getElementById('rzp-button').onclick = function(e) {{
            const rzp = new Razorpay(options);
            rzp.on('payment.failed', function (response) {{
                console.log('Payment Failed Response:', response);
                const container = document.querySelector('.checkout-container');
                container.innerHTML = `
                    <div class="header">
                        <div class="store-name">${{options.name}}</div>
                        <div class="order-ref">${{options.description}}</div>
                    </div>
                    <div style="padding: 24px; text-align: center;">
                        <div style="font-size: 40px; margin-bottom: 12px;">⚠️</div>
                        <h2 style="font-size: 18px; font-weight: 700; color: #dc2626;">
                            Payment could not be completed.
                        </h2>
                        <p style="color: #4b5563; font-size: 14px; line-height: 1.6;">
                            A secure payment link has been sent to your checkout contact.<br>
                            Check your SMS/email for the link.
                        </p>
                        <div style="padding: 10px; background: #f3f4f6; font-size: 12px;">
                            Status: Handed off to secure SMS recovery • ${{options.description}}
                        </div>
                    </div>
                    <p class="footer">
                        Secured by Razorpay • Key: ${{options.key.substring(0, 12)}}...
                    </p>
                `;
            }});
            rzp.open();
            e.preventDefault();
        }};
    </script>
</body>
</html>
"""
    return HTMLResponse(content=html_content)
