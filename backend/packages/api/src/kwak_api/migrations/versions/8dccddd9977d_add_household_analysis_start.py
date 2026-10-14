"""add household analysis_start

Revision ID: 8dccddd9977d
Revises: 396d41db423d
Create Date: 2026-10-14 23:56:13.796232
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "8dccddd9977d"
down_revision: str | None = "396d41db423d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("household", sa.Column("analysis_start", sa.Date(), nullable=True))
    op.create_check_constraint(
        op.f("ck_household_analysis_start_month"),
        "household",
        "extract(day from analysis_start) = 1",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_household_analysis_start_month"), "household", type_="check")
    op.drop_column("household", "analysis_start")
