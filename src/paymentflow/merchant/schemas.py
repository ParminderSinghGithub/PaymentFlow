"""Public schemas for merchant integration contract.

These schemas represent the external, product-level merchant contract.
Internal database models, audit logs, and benchmark fields are strictly excluded.
"""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class MerchantCheckoutContextRequest(BaseModel):
    """Payload sent by merchant server when a customer begins or attempts checkout."""

    external_order_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Merchant's external order identifier (e.g. order_M12345)",
    )
    external_payment_id: str | None = Field(
        default=None,
        max_length=128,
        description="Optional initial payment attempt ID (e.g. pay_XYZ123)",
    )
    amount: int = Field(
        ...,
        gt=0,
        description="Transaction amount in paise (e.g. 299900 for ₹2,999.00)",
    )
    currency: str = Field(
        default="INR",
        description="Three-letter ISO currency code. Prototype strictly supports INR.",
    )
    customer_email: str | None = Field(
        default=None,
        description="Customer email address for recovery communications",
    )
    customer_phone: str | None = Field(
        default=None,
        description="Customer phone number in E.164 or national format",
    )
    merchant_reference: str | None = Field(
        default=None,
        description="Merchant internal reference or cart identifier",
    )
    error_code: str | None = Field(
        default=None,
        description="Initial gateway error code if checkout failure already occurred",
    )
    error_description: str | None = Field(
        default=None,
        description="Human-readable error description from gateway or merchant",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional merchant contextual metadata",
    )
    merchant_id: str | None = Field(
        default=None,
        description="Optional merchant ID. If provided, must match authenticated credentials.",
    )

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str) -> str:
        """Enforce supported currency for buildathon prototype."""
        normalized = v.strip().upper()
        if normalized != "INR":
            raise ValueError(
                f"Unsupported currency '{v}'. PaymentFlow prototype strictly supports INR."
            )
        return normalized


class MerchantCheckoutContextResponse(BaseModel):
    """Stable integration confirmation returned to merchant server."""

    status: Literal["accepted"] = "accepted"
    context_id: str = Field(
        default_factory=lambda: f"mctx_{uuid.uuid4().hex[:16]}",
        description="Unique registration identifier for this checkout context",
    )
    merchant_id: str = Field(
        ...,
        description="Authenticated merchant identifier that owns this context",
    )
    external_order_id: str = Field(
        ...,
        description="Merchant external order identifier",
    )
    external_payment_id: str | None = Field(
        default=None,
        description="Initial payment attempt ID if recorded",
    )
    amount: int = Field(
        ...,
        description="Transaction amount in paise",
    )
    currency: str = Field(
        ...,
        description="Currency code",
    )
    customer_email: str | None = None
    customer_phone: str | None = None
    registered_at: datetime = Field(
        ...,
        description="Timestamp when context was accepted",
    )
    message: str = "Merchant checkout context registered successfully for recovery monitoring."


class MerchantVerifyResponse(BaseModel):
    """Credential verification confirmation for merchant server."""

    status: Literal["authenticated"] = "authenticated"
    merchant_id: str = Field(
        ...,
        description="Resolved authenticated merchant identifier",
    )
    merchant_name: str = Field(
        ...,
        description="Registered business name",
    )
    razorpay_key_id: str = Field(
        ...,
        description="Merchant Razorpay Key ID for client-side checkout",
    )
    is_active: bool = Field(
        ...,
        description="Account operational status",
    )
    message: str = "Merchant API credential authenticated successfully."


class MerchantCreateOrderRequest(BaseModel):
    """Request by merchant to initiate a Razorpay order with attached context."""

    amount: int = Field(gt=0, description="Order amount in paise (e.g. 345000 for ₹3,450.00)")
    currency: str = Field(default="INR", description="Currency code (INR)")
    external_order_id: str = Field(
        min_length=1, max_length=128, description="Merchant external order reference"
    )
    customer_name: str | None = Field(default=None, description="Customer full name")
    customer_email: str | None = Field(default=None, description="Customer email")
    customer_phone: str | None = Field(default=None, description="Customer phone number")
    notes: dict[str, Any] = Field(default_factory=dict, description="Custom merchant notes")

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str) -> str:
        normalized = v.strip().upper()
        if normalized != "INR":
            raise ValueError(
                f"Unsupported currency '{v}'. PaymentFlow prototype strictly supports INR."
            )
        return normalized


class MerchantCreateOrderResponse(BaseModel):
    """Response returned when an order is successfully created in Razorpay with context."""

    status: Literal["created"] = "created"
    context_id: str = Field(..., description="Internal checkout context ID")
    razorpay_order_id: str = Field(..., description="Razorpay Order ID")
    external_order_id: str = Field(..., description="Merchant external order ID")
    amount: int = Field(..., description="Amount in paise")
    currency: str = Field(..., description="Currency")
    razorpay_key_id: str = Field(..., description="Public Razorpay Key ID for checkout")
    checkout_url: str = Field(..., description="URL to open the interactive checkout experience")
    message: str = "Razorpay order created and checkout context registered successfully."
