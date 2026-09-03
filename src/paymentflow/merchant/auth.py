"""Server-to-server merchant authentication middleware and dependencies.

Enforces:
    Authorization: Bearer <PAYMENTFLOW_API_KEY>
Resolves authenticated merchant identity from the credential, never from request body.
"""

from fastapi import HTTPException, Request, status

from paymentflow.merchant.models import AuthenticatedMerchantContext
from paymentflow.merchant.service import MerchantRegistry


async def get_authenticated_merchant(request: Request) -> AuthenticatedMerchantContext:
    """Authenticate incoming server-to-server merchant request.

    Extracts Bearer token from Authorization header and resolves the authenticated
    merchant identity using constant-time hash lookup.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header. Expected 'Bearer <PAYMENTFLOW_API_KEY>'.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    parts = auth_header.strip().split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed Authorization header format. Expected 'Bearer <API_KEY>'.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    raw_api_key = parts[1].strip()
    merchant = MerchantRegistry.get_by_api_key(raw_api_key)

    if not merchant:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid PaymentFlow API key.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not merchant.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Merchant account '{merchant.merchant_id}' is disabled.",
        )

    return AuthenticatedMerchantContext(
        merchant_id=merchant.merchant_id,
        merchant_name=merchant.merchant_name,
        razorpay_key_id=merchant.razorpay_key_id,
        is_active=merchant.is_active,
    )
