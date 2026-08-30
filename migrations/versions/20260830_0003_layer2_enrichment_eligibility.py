"""Layer 2 schema updates: classification_evidence, eligibility_reason.

Revision ID: 0003_layer2_eligibility
Revises: 0002_layer1_domain
Create Date: 2026-08-30 17:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "0003_layer2_eligibility"
down_revision: Union[str, None] = "0002_layer1_domain"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

JsonType = sa.JSON().with_variant(JSONB, "postgresql")


def upgrade() -> None:
    op.add_column(
        "recovery_cases",
        sa.Column("classification_evidence", JsonType, nullable=True),
    )
    op.add_column(
        "recovery_cases",
        sa.Column("eligibility_reason", sa.String(length=64), nullable=True),
    )
    op.create_index("ix_recovery_cases_eligibility_status", "recovery_cases", ["eligibility_status"])
    op.create_index("ix_recovery_cases_eligibility_reason", "recovery_cases", ["eligibility_reason"])


def downgrade() -> None:
    op.drop_index("ix_recovery_cases_eligibility_reason", table_name="recovery_cases")
    op.drop_index("ix_recovery_cases_eligibility_status", table_name="recovery_cases")
    op.drop_column("recovery_cases", "eligibility_reason")
    op.drop_column("recovery_cases", "classification_evidence")
