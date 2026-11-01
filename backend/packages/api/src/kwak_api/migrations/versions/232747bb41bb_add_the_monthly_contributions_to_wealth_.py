"""add the monthly contributions to wealth categories

Revision ID: 232747bb41bb
Revises: a0f22a064174
Create Date: 2026-11-01 03:01:41.285947
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "232747bb41bb"
down_revision: str | None = "a0f22a064174"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "wealth_category",
        sa.Column("monthly_contribution", sa.Numeric(precision=14, scale=2), nullable=True),
    )
    op.add_column(
        "wealth_category",
        sa.Column(
            "contribution_indexed", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
    )
    op.create_check_constraint(
        op.f("ck_wealth_category_contribution_range"),
        "wealth_category",
        "monthly_contribution BETWEEN 1 AND 100000",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_wealth_category_contribution_range"), "wealth_category", type_="check"
    )
    op.drop_column("wealth_category", "contribution_indexed")
    op.drop_column("wealth_category", "monthly_contribution")
