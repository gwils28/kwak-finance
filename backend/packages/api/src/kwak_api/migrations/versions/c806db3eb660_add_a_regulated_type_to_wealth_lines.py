"""add a regulated type to wealth lines

Revision ID: c806db3eb660
Revises: 5c7af92e494e
Create Date: 2026-10-24 11:10:54.320020
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c806db3eb660"
down_revision: str | None = "5c7af92e494e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TYPES = ("livret_a", "ldds", "lep", "pel", "livret_jeune")


def upgrade() -> None:
    op.add_column("wealth_line", sa.Column("regulated_type", sa.String(length=20), nullable=True))
    op.create_check_constraint(
        op.f("ck_wealth_line_regulated_type"),
        "wealth_line",
        "regulated_type IN (" + ", ".join(f"'{t}'" for t in TYPES) + ")",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_wealth_line_regulated_type"), "wealth_line", type_="check")
    op.drop_column("wealth_line", "regulated_type")
