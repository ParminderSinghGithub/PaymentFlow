"""Merchant integration package for PaymentFlow.

Provides public integration contracts, server-to-server authentication,
and deterministic Razorpay credential resolution for external merchant servers.
"""

from paymentflow.merchant.auth import get_authenticated_merchant
from paymentflow.merchant.models import (
    AuthenticatedMerchantContext,
    MerchantProfile,
    hash_api_key,
    verify_api_key,
)
from paymentflow.merchant.schemas import (
    MerchantCheckoutContextRequest,
    MerchantCheckoutContextResponse,
    MerchantVerifyResponse,
)
from paymentflow.merchant.service import MerchantRegistry

__all__ = [
    "AuthenticatedMerchantContext",
    "MerchantCheckoutContextRequest",
    "MerchantCheckoutContextResponse",
    "MerchantProfile",
    "MerchantRegistry",
    "MerchantVerifyResponse",
    "get_authenticated_merchant",
    "hash_api_key",
    "verify_api_key",
]
