"""Initial schema setup for PaymentFlow foundation.

Revision ID: 0001_initial
Revises: 
Create Date: 2026-08-30 10:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Minimal initial schema proving Alembic migration pipeline works
    op.create_table(
        "app_metadata",
        sa.Column("key", sa.String(length=128), primary_key=True),
        sa.Column("value", sa.String(length=256), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("app_metadata")
