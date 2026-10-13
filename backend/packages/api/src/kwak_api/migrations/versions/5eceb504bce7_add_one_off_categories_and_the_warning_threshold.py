"""add one-off categories and the warning threshold

Revision ID: 5eceb504bce7
Revises: 4cfbb5480a5f
Create Date: 2026-10-13 14:34:09.960194
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "5eceb504bce7"
down_revision: str | None = "4cfbb5480a5f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("category", sa.Column("one_off", sa.Boolean(), nullable=True))
    # F-CAT-6: the default Housing and Subscriptions are one-off, under either language's name.
    op.execute(
        """
        UPDATE category SET one_off = true
        WHERE parent_id IS NULL AND kind = 'expense'
          AND lower(name) IN ('housing', 'logement', 'subscriptions', 'abonnements')
        """
    )
    op.add_column(
        "household",
        sa.Column(
            "warn_at",
            sa.Numeric(precision=3, scale=2),
            server_default=sa.text("0.80"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        op.f("ck_household_warn_at_range"), "household", "warn_at BETWEEN 0.5 AND 1"
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_household_warn_at_range"), "household", type_="check")
    op.drop_column("household", "warn_at")
    op.drop_column("category", "one_off")
