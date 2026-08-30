"""Layer 4A schema updates: payment_link_short_url, payment_link_status.

Revision ID: 0004_layer4a_payment_link
Revises: 0003_layer2_eligibility
Create Date: 2026-08-30 17:35:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0004_layer4a_payment_link"
down_revision: Union[str, None] = "0003_layer2_eligibility"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "recovery_cases",
        sa.Column("payment_link_short_url", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "recovery_cases",
        sa.Column("payment_link_status", sa.String(length=32), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("recovery_cases", "payment_link_status")
    op.drop_column("recovery_cases", "payment_link_short_url")
