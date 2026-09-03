"""Add case_source, eval_run_id and create evaluation_runs table.

Revision ID: 0006_case_source_eval_runs
Revises: 0005_add_scheduled_at
Create Date: 2026-09-03 21:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON

# revision identifiers, used by Alembic (max 32 chars).
revision: str = "0006_case_source_eval_runs"
down_revision: Union[str, None] = "0005_add_scheduled_at"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

JsonType = JSON().with_variant(JSONB, "postgresql")


def upgrade() -> None:
    """Add provenance fields and create evaluation_runs table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    # 1. Update recovery_cases
    if "recovery_cases" in tables:
        columns = [c["name"] for c in inspector.get_columns("recovery_cases")]
        if "case_source" not in columns:
            op.add_column(
                "recovery_cases",
                sa.Column(
                    "case_source",
                    sa.String(32),
                    nullable=False,
                    server_default="LIVE_CHECKOUT",
                ),
            )
            op.create_index(
                op.f("ix_recovery_cases_case_source"),
                "recovery_cases",
                ["case_source"],
                unique=False,
            )
        if "eval_run_id" not in columns:
            op.add_column(
                "recovery_cases",
                sa.Column("eval_run_id", sa.String(64), nullable=True),
            )
            op.create_index(
                op.f("ix_recovery_cases_eval_run_id"),
                "recovery_cases",
                ["eval_run_id"],
                unique=False,
            )

    # 2. Update audit_events
    if "audit_events" in tables:
        columns = [c["name"] for c in inspector.get_columns("audit_events")]
        if "eval_run_id" not in columns:
            op.add_column(
                "audit_events",
                sa.Column("eval_run_id", sa.String(64), nullable=True),
            )
            op.create_index(
                op.f("ix_audit_events_eval_run_id"),
                "audit_events",
                ["eval_run_id"],
                unique=False,
            )

    # 3. Create evaluation_runs
    if "evaluation_runs" not in tables:
        op.create_table(
            "evaluation_runs",
            sa.Column("eval_run_id", sa.String(64), primary_key=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("status", sa.String(32), nullable=False, server_default="COMPLETED"),
            sa.Column("total_cases", sa.Integer(), nullable=False),
            sa.Column("total_at_risk_amount", sa.BigInteger(), nullable=False),
            sa.Column("eligible_cases", sa.Integer(), nullable=False),
            sa.Column("eligible_opportunity_amount", sa.BigInteger(), nullable=False),
            sa.Column("recovery_actions_executed", sa.Integer(), nullable=False),
            sa.Column("recovery_actions_blocked", sa.Integer(), nullable=False),
            sa.Column("evaluation_recovered_cases", sa.Integer(), nullable=False),
            sa.Column("evaluation_recovered_amount", sa.BigInteger(), nullable=False),
            sa.Column("escalated_cases", sa.Integer(), nullable=False),
            sa.Column("escalated_amount", sa.BigInteger(), nullable=False),
            sa.Column("terminal_cases", sa.Integer(), nullable=False),
            sa.Column("terminal_amount", sa.BigInteger(), nullable=False),
            sa.Column("overall_case_recovery_rate_pct", sa.Float(), nullable=False),
            sa.Column("eligible_case_recovery_rate_pct", sa.Float(), nullable=False),
            sa.Column("portfolio_revenue_recovery_rate_pct", sa.Float(), nullable=False),
            sa.Column("eligible_opportunity_recovery_rate_pct", sa.Float(), nullable=False),
            sa.Column("summary_metadata", JsonType, nullable=True),
        )
        op.create_index(
            op.f("ix_evaluation_runs_created_at"),
            "evaluation_runs",
            ["created_at"],
            unique=False,
        )


def downgrade() -> None:
    """Revert provenance fields and evaluation_runs table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if "evaluation_runs" in tables:
        op.drop_table("evaluation_runs")

    if "audit_events" in tables:
        columns = [c["name"] for c in inspector.get_columns("audit_events")]
        if "eval_run_id" in columns:
            op.drop_index(op.f("ix_audit_events_eval_run_id"), table_name="audit_events")
            op.drop_column("audit_events", "eval_run_id")

    if "recovery_cases" in tables:
        columns = [c["name"] for c in inspector.get_columns("recovery_cases")]
        if "eval_run_id" in columns:
            op.drop_index(op.f("ix_recovery_cases_eval_run_id"), table_name="recovery_cases")
            op.drop_column("recovery_cases", "eval_run_id")
        if "case_source" in columns:
            op.drop_index(op.f("ix_recovery_cases_case_source"), table_name="recovery_cases")
            op.drop_column("recovery_cases", "case_source")
