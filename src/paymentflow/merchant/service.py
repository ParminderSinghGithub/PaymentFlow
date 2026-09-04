"""Merchant registry and deterministic configuration resolution service.

Maintains the merchant identity boundary for the buildathon prototype.
Ensures merchant A cannot access or resolve merchant B's Razorpay credentials.
"""

from typing import Any, ClassVar

from paymentflow.config import get_settings
from paymentflow.merchant.models import (
    MerchantProfile,
    hash_api_key,
    verify_api_key,
)


class MerchantRegistry:
    """In-memory merchant credential and configuration registry.

    For the local buildathon prototype, loads the default merchant from environment
    settings while strictly supporting multi-merchant credential isolation for tests
    and future storefronts.
    """

    _merchants_by_id: ClassVar[dict[str, MerchantProfile]] = {}
    _merchants_by_hash: ClassVar[dict[str, MerchantProfile]] = {}
    _checkout_contexts: ClassVar[dict[str, dict[str, Any]]] = {}
    _initialized: ClassVar[bool] = False

    @classmethod
    def _ensure_initialized(cls) -> None:
        """Initialize default prototype merchant from configuration."""
        if not cls._initialized:
            cls.reset_to_default()

    @classmethod
    def reset_to_default(cls) -> None:
        """Reset registry to the default prototype merchant configuration."""
        settings = get_settings()
        cls._merchants_by_id.clear()
        cls._merchants_by_hash.clear()
        cls._checkout_contexts.clear()

        # Default buildathon prototype merchant
        default_key = settings.paymentflow_api_key
        default_hash = hash_api_key(default_key)
        default_merchant = MerchantProfile(
            merchant_id="merchant_demo_store",
            merchant_name="Acme Fashion Store (Buildathon Demo)",
            api_key_hash=default_hash,
            is_active=True,
            razorpay_key_id=settings.razorpay_key_id,
            razorpay_key_secret=settings.razorpay_key_secret,
        )

        cls._merchants_by_id[default_merchant.merchant_id] = default_merchant
        cls._merchants_by_hash[default_merchant.api_key_hash] = default_merchant
        cls._initialized = True

    @classmethod
    def register_merchant(cls, profile: MerchantProfile) -> None:
        """Register a new merchant profile (used for testing and multi-merchant setup)."""
        cls._ensure_initialized()
        cls._merchants_by_id[profile.merchant_id] = profile
        cls._merchants_by_hash[profile.api_key_hash] = profile

    @classmethod
    def get_by_api_key(cls, raw_key: str) -> MerchantProfile | None:
        """Resolve merchant profile by raw API key using constant-time hash comparison."""
        cls._ensure_initialized()
        if not raw_key:
            return None

        # Compare against all registered merchant hashes using constant-time check
        for stored_hash, profile in cls._merchants_by_hash.items():
            if verify_api_key(raw_key, stored_hash):
                return profile
        return None

    @classmethod
    def get_by_merchant_id(cls, merchant_id: str) -> MerchantProfile | None:
        """Retrieve merchant profile by ID."""
        cls._ensure_initialized()
        return cls._merchants_by_id.get(merchant_id)

    @classmethod
    def resolve_razorpay_credentials(cls, merchant_id: str) -> tuple[str, str] | None:
        """Deterministically resolve Razorpay key ID and secret for authenticated merchant.

        Guarantees that credentials belong exclusively to the queried merchant ID.
        """
        merchant = cls.get_by_merchant_id(merchant_id)
        if not merchant or not merchant.is_active:
            return None
        return merchant.razorpay_key_id, merchant.razorpay_key_secret

    @classmethod
    def get_razorpay_credentials(cls, merchant_id: str) -> tuple[str, str] | None:
        """Alias for resolve_razorpay_credentials."""
        return cls.resolve_razorpay_credentials(merchant_id)

    @classmethod
    def store_checkout_context(cls, context_id: str, data: dict[str, Any]) -> None:
        """Store checkout context indexed by context_id, external_order_id, and rzp order_id."""
        cls._ensure_initialized()
        merchant_id = data.get("merchant_id")

        # Primary lookup key (e.g. context_id)
        cls._checkout_contexts[context_id] = data
        if merchant_id:
            cls._checkout_contexts[f"{merchant_id}:{context_id}"] = data

        # Store by external_order_id: strictly tenant-scoped if merchant_id is present
        if "external_order_id" in data and data["external_order_id"]:
            ext_id = str(data["external_order_id"])
            if merchant_id:
                cls._checkout_contexts[f"{merchant_id}:{ext_id}"] = data
            else:
                cls._checkout_contexts[ext_id] = data

        # Store by razorpay_order_id (globally unique gateway ID)
        if "razorpay_order_id" in data and data["razorpay_order_id"]:
            rzp_id = str(data["razorpay_order_id"])
            if merchant_id:
                cls._checkout_contexts[f"{merchant_id}:{rzp_id}"] = data
            cls._checkout_contexts[rzp_id] = data

    @classmethod
    def get_checkout_context(
        cls, key: str | None, merchant_id: str | None = None
    ) -> dict[str, Any] | None:
        """Look up checkout context by context_id, external_order_id, or razorpay order_id.

        Strictly enforces tenant isolation when merchant_id is provided.
        """
        cls._ensure_initialized()
        if not key:
            return None
        s_key = str(key)
        if merchant_id:
            scoped_key = f"{merchant_id}:{s_key}"
            if scoped_key in cls._checkout_contexts:
                return cls._checkout_contexts[scoped_key]
            # If scoped key not found, check global key only if owned by this merchant
            ctx = cls._checkout_contexts.get(s_key)
            if ctx and ctx.get("merchant_id") == merchant_id:
                return ctx
            # Crucial: Never leak another merchant's context
            return None

        # Unscoped lookup (e.g. by unique razorpay_order_id or context_id)
        return cls._checkout_contexts.get(s_key)
