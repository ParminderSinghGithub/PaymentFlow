"""External Merchant Demo Server Application.

Operates as a completely independent product consumer of PaymentFlow.
- Communicates with PaymentFlow solely over HTTP APIs.
- Communicates with Razorpay over Razorpay APIs.
- Serves the merchant storefront and checkout UI.
- Never imports internal PaymentFlow Python recovery modules.
- Keeps RAZORPAY_KEY_SECRET and PAYMENTFLOW_API_KEY strictly server-side.
"""

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

try:
    from .config import get_merchant_settings
    from .paymentflow_client import MerchantPaymentFlowClient
    from .razorpay_client import MerchantRazorpayClient
except Exception:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from config import get_merchant_settings
    from paymentflow_client import MerchantPaymentFlowClient
    from razorpay_client import MerchantRazorpayClient

app = FastAPI(
    title="Merchant Store Demo — Merchant Server",
    description="External Merchant Server consuming PaymentFlow over HTTP",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


class CreateOrderRequest(BaseModel):
    amount: int = Field(gt=0, description="Amount in paise")
    currency: str = Field(default="INR")
    external_order_id: str = Field(min_length=1, max_length=128)
    customer_name: str | None = None
    customer_email: str | None = None
    customer_phone: str | None = None


@app.get("/health", summary="Merchant Server Health")
async def health_check() -> dict[str, str]:
    """Health check for external merchant server."""
    return {"status": "ok", "service": "merchant-demo-server"}


@app.get("/api/config", summary="Safe Public Merchant Configuration")
async def get_public_config() -> dict[str, str]:
    """Return only safe, public configuration to the browser client.

    Never exposes RAZORPAY_KEY_SECRET or PAYMENTFLOW_API_KEY.
    """
    settings = get_merchant_settings()
    return {
        "merchant_id": settings.merchant_id,
        "merchant_name": settings.merchant_name,
        "razorpay_key_id": settings.razorpay_key_id,
    }


@app.post("/api/orders", status_code=status.HTTP_201_CREATED, summary="Create Storefront Order")
async def create_storefront_order(payload: CreateOrderRequest) -> dict[str, Any]:
    """Handle checkout initiation on the merchant server.

    1. Creates order with Razorpay via thin server-side client.
    2. Registers checkout context with PaymentFlow via server-to-server HTTP API.
    3. Returns order ID and public Razorpay Key ID to the browser.
    """
    settings = get_merchant_settings()
    rzp_client = MerchantRazorpayClient()
    pf_client = MerchantPaymentFlowClient()

    # 1. Create order on Razorpay
    notes = {
        "merchant_id": settings.merchant_id,
        "external_order_id": payload.external_order_id,
        "storefront": "merchant_demo",
    }
    try:
        rzp_order = await rzp_client.create_order(
            amount=payload.amount,
            currency=payload.currency,
            receipt=payload.external_order_id[:40],
            notes=notes,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to create order with Razorpay: {exc}",
        )

    # 2. Register context with PaymentFlow over HTTP
    try:
        await pf_client.register_checkout_context(
            external_order_id=payload.external_order_id,
            amount=payload.amount,
            currency=payload.currency,
            customer_email=payload.customer_email,
            customer_phone=payload.customer_phone,
            metadata={"razorpay_order_id": rzp_order["id"]},
        )
    except Exception:
        # Non-fatal: checkout proceeds even if PaymentFlow logging encounters an issue
        pass

    return {
        "status": "created",
        "razorpay_order_id": rzp_order["id"],
        "external_order_id": payload.external_order_id,
        "amount": payload.amount,
        "currency": payload.currency,
        "merchant_name": settings.merchant_name,
        "razorpay_key_id": settings.razorpay_key_id,
    }


@app.get("/api/recovery-status", summary="Poll Safe Order Recovery Status")
async def get_order_recovery_status(order_id: str) -> dict[str, Any]:
    """Poll safe recovery status for an order via PaymentFlow API.

    Returns only safe customer status; never exposes secrets or recovery URLs.
    """
    pf_client = MerchantPaymentFlowClient()
    try:
        return await pf_client.get_recovery_status(order_id)
    except Exception as exc:
        return {
            "order_id": order_id,
            "status": "AWAITING_INGESTION",
            "message": f"Recovery status not yet available: {exc}",
        }


@app.get("/", response_class=HTMLResponse)
@app.get("/checkout", response_class=HTMLResponse)
async def serve_checkout_page() -> HTMLResponse:
    """Serve the merchant storefront checkout page."""
    html_file = FRONTEND_DIR / "index.html"
    if not html_file.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Storefront HTML not found."
        )
    return HTMLResponse(content=html_file.read_text(encoding="utf-8"))
