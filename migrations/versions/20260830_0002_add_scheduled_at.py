"""Add scheduled_at column to recovery_cases.

Revision ID: 0002_add_scheduled_at
Revises: 0001_initial
Create Date: 2026-08-30 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0002_add_scheduled_at"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add scheduled_at column to recovery_cases table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    if "recovery_cases" in tables:
        columns = [c["name"] for c in inspector.get_columns("recovery_cases")]
        if "scheduled_at" not in columns:
            op.add_column(
                "recovery_cases",
                sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
            )
            op.create_index(
                op.f("ix_recovery_cases_scheduled_at"),
                "recovery_cases",
                ["scheduled_at"],
                unique=False,
            )


def downgrade() -> None:
    """Drop scheduled_at column from recovery_cases table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    if "recovery_cases" in tables:
        columns = [c["name"] for c in inspector.get_columns("recovery_cases")]
        if "scheduled_at" in columns:
            op.drop_index(op.f("ix_recovery_cases_scheduled_at"), table_name="recovery_cases")
            op.drop_column("recovery_cases", "scheduled_at")
