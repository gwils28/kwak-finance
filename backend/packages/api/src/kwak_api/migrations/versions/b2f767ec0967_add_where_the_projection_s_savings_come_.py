"""add where the projection's savings come from to household

F-SIM-3: `declared` (the contributions alone) or `measured` (the goals' capacity); NULL keeps
today's behaviour, declared once a contribution exists.

Revision ID: b2f767ec0967
Revises: 232747bb41bb
Create Date: 2026-11-01 21:15:40.563149
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b2f767ec0967"
down_revision: str | None = "232747bb41bb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("household", sa.Column("projection_savings", sa.String(length=10), nullable=True))
    op.create_check_constraint(
        op.f("ck_household_projection_savings_known"),
        "household",
        "projection_savings IN ('declared', 'measured')",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_household_projection_savings_known"), "household", type_="check")
    op.drop_column("household", "projection_savings")
