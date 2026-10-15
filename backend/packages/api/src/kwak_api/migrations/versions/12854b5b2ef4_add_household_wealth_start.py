"""add household wealth_start

Revision ID: 12854b5b2ef4
Revises: e6872d35b54b
Create Date: 2026-10-15 12:06:46.872045
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "12854b5b2ef4"
down_revision: str | None = "e6872d35b54b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("household", sa.Column("wealth_start", sa.Date(), nullable=True))
    op.create_check_constraint(
        op.f("ck_household_wealth_start_month"),
        "household",
        "extract(day from wealth_start) = 1",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_household_wealth_start_month"), "household", type_="check")
    op.drop_column("household", "wealth_start")
