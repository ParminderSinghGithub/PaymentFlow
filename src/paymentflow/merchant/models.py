"""Merchant identity and configuration models for buildathon prototype.

Securely stores API key hashes and maps authenticated merchant identities to
isolated Razorpay configuration.
"""

import hashlib
import hmac
from datetime import datetime

from pydantic import BaseModel, Field

from paymentflow.db.models import utc_now


def hash_api_key(api_key: str) -> str:
    """Compute deterministic SHA-256 digest of merchant API key."""
    return hashlib.sha256(api_key.strip().encode("utf-8")).hexdigest()


def verify_api_key(api_key: str, expected_hash: str) -> bool:
    """Constant-time verification of API key against expected hash."""
    candidate_hash = hash_api_key(api_key)
    return hmac.compare_digest(candidate_hash, expected_hash)


class MerchantProfile(BaseModel):
    """Internal merchant profile and isolated Razorpay configuration."""

    merchant_id: str = Field(..., description="Unique merchant identifier")
    merchant_name: str = Field(..., description="Human-readable business name")
    api_key_hash: str = Field(..., description="SHA-256 hash of server-to-server API key")
    is_active: bool = Field(default=True, description="Whether merchant account is enabled")
    razorpay_key_id: str = Field(..., description="Merchant Razorpay Key ID")
    razorpay_key_secret: str = Field(
        ...,
        description="Merchant Razorpay Key Secret (Server-side only, never exposed)",
    )
    created_at: datetime = Field(default_factory=utc_now)


class AuthenticatedMerchantContext(BaseModel):
    """Resolved security context injected into authenticated merchant requests."""

    merchant_id: str
    merchant_name: str
    razorpay_key_id: str
    is_active: bool
