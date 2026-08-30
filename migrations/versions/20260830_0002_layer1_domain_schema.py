"""Layer 1 domain schema: webhook_events, recovery_cases, audit_events.

Revision ID: 0002_layer1_domain
Revises: 0001_initial
Create Date: 2026-08-30 11:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "0002_layer1_domain"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

JsonType = sa.JSON().with_variant(JSONB, "postgresql")


def upgrade() -> None:
    # 1. webhook_events
    op.create_table(
        "webhook_events",
        sa.Column("event_id", sa.String(length=128), primary_key=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("payload", JsonType, nullable=False),
        sa.Column("signature_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="RECEIVED"),
        sa.Column("error_message", sa.Text(), nullable=True),
    )
    op.create_index("ix_webhook_events_event_type", "webhook_events", ["event_type"])
    op.create_index("ix_webhook_events_status", "webhook_events", ["status"])
    op.create_index("ix_webhook_events_received_at", "webhook_events", ["received_at"])

    # 2. recovery_cases
    op.create_table(
        "recovery_cases",
        sa.Column("case_id", sa.String(length=64), primary_key=True),
        sa.Column("failed_payment_id", sa.String(length=64), nullable=False, unique=True),
        sa.Column("order_id", sa.String(length=64), nullable=True),
        sa.Column("customer_id", sa.String(length=64), nullable=True),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default="INR"),
        sa.Column("payment_method", sa.String(length=32), nullable=True),
        sa.Column("failure_category", sa.String(length=16), nullable=True),
        sa.Column("failure_code", sa.String(length=64), nullable=True),
        sa.Column("failure_description", sa.Text(), nullable=True),
        sa.Column("failure_context", JsonType, nullable=True),
        sa.Column("eligibility_status", sa.String(length=32), nullable=True),
        sa.Column("ai_policy_id", sa.String(length=64), nullable=True),
        sa.Column("ai_explanation", sa.Text(), nullable=True),
        sa.Column("validated_policy_id", sa.String(length=64), nullable=True),
        sa.Column("action_status", sa.String(length=32), nullable=True),
        sa.Column("payment_link_id", sa.String(length=64), nullable=True),
        sa.Column("payment_link_reference_id", sa.String(length=128), nullable=True),
        sa.Column("recovered_payment_id", sa.String(length=64), nullable=True),
        sa.Column("recovered_amount", sa.BigInteger(), nullable=True),
        sa.Column("state", sa.String(length=32), nullable=False, server_default="FAILED_INGESTED"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_recovery_cases_failed_payment_id", "recovery_cases", ["failed_payment_id"])
    op.create_index("ix_recovery_cases_order_id", "recovery_cases", ["order_id"])
    op.create_index("ix_recovery_cases_customer_id", "recovery_cases", ["customer_id"])
    op.create_index("ix_recovery_cases_failure_category", "recovery_cases", ["failure_category"])
    op.create_index("ix_recovery_cases_payment_link_id", "recovery_cases", ["payment_link_id"])
    op.create_index("ix_recovery_cases_payment_link_reference_id", "recovery_cases", ["payment_link_reference_id"])
    op.create_index("ix_recovery_cases_state", "recovery_cases", ["state"])

    # 3. audit_events
    op.create_table(
        "audit_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("case_id", sa.String(length=64), sa.ForeignKey("recovery_cases.case_id", ondelete="CASCADE"), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("actor", sa.String(length=32), nullable=False),
        sa.Column("decision", sa.String(length=64), nullable=True),
        sa.Column("policy", sa.String(length=64), nullable=True),
        sa.Column("guardrail_result", JsonType, nullable=True),
        sa.Column("action", sa.String(length=64), nullable=True),
        sa.Column("outcome", sa.String(length=64), nullable=True),
        sa.Column("correlation_id", sa.String(length=128), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("details", JsonType, nullable=True),
    )
    op.create_index("ix_audit_events_case_id", "audit_events", ["case_id"])
    op.create_index("ix_audit_events_event_type", "audit_events", ["event_type"])
    op.create_index("ix_audit_events_correlation_id", "audit_events", ["correlation_id"])
    op.create_index("ix_audit_events_timestamp", "audit_events", ["timestamp"])


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("recovery_cases")
    op.drop_table("webhook_events")
