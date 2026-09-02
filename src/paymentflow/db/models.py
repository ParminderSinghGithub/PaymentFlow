"""SQLAlchemy ORM models for PaymentFlow persistence."""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from paymentflow.db.base import Base

# Use JSONB on Postgres or fallback to standard JSON
JsonType = JSON().with_variant(JSONB, "postgresql")


def utc_now() -> datetime:
    """Return current timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


class WebhookEventModel(Base):
    """Stores all received webhook events for verification, audit, and idempotency."""

    __tablename__ = "webhook_events"

    event_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JsonType, nullable=False)
    signature_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="RECEIVED", index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (Index("ix_webhook_events_received_at", "received_at"),)


class RecoveryCaseModel(Base):
    """Core entity tracking the lifecycle and context of a failed payment recovery."""

    __tablename__ = "recovery_cases"

    case_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    failed_payment_id: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    order_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    customer_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)  # in paise
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="INR")
    payment_method: Mapped[str | None] = mapped_column(String(32), nullable=True)
    failure_category: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    failure_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    failure_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    failure_context: Mapped[dict[str, Any] | None] = mapped_column(JsonType, nullable=True)
    classification_evidence: Mapped[dict[str, Any] | None] = mapped_column(JsonType, nullable=True)
    eligibility_status: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    eligibility_reason: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    ai_policy_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ai_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    validated_policy_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    action_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    payment_link_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    payment_link_reference_id: Mapped[str | None] = mapped_column(
        String(128), index=True, nullable=True
    )
    payment_link_short_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payment_link_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    recovered_payment_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    recovered_amount: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    state: Mapped[str] = mapped_column(
        String(32), nullable=False, default="FAILED_INGESTED", index=True
    )
    scheduled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    # Relationships
    audit_events: Mapped[list["AuditEventModel"]] = relationship(
        "AuditEventModel",
        back_populates="case",
        cascade="all, delete-orphan",
        order_by="AuditEventModel.timestamp",
    )


class AuditEventModel(Base):
    """Immutable chronological audit log of all system and actor decisions."""

    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    case_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("recovery_cases.case_id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    actor: Mapped[str] = mapped_column(String(32), nullable=False)  # system, llm, policy_engine
    decision: Mapped[str | None] = mapped_column(String(64), nullable=True)
    policy: Mapped[str | None] = mapped_column(String(64), nullable=True)
    guardrail_result: Mapped[dict[str, Any] | None] = mapped_column(JsonType, nullable=True)
    action: Mapped[str | None] = mapped_column(String(64), nullable=True)
    outcome: Mapped[str | None] = mapped_column(String(64), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False, index=True
    )
    details: Mapped[dict[str, Any] | None] = mapped_column(JsonType, nullable=True)

    # Relationship
    case: Mapped[RecoveryCaseModel | None] = relationship(
        "RecoveryCaseModel", back_populates="audit_events"
    )
