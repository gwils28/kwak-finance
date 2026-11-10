"""add fill_first to goals

Several precaution goals may sit in the foundation; each is filled first unless unticked
(F-GOAL-1, spec v1.23). Existing goals are all filled first, as before.

Revision ID: 384a91d9ace2
Revises: c4e9a1f27d30
Create Date: 2026-11-10 12:35:21.881855
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "384a91d9ace2"
down_revision: str | None = "c4e9a1f27d30"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "goal",
        sa.Column("fill_first", sa.Boolean(), server_default=sa.text("true"), nullable=False),
    )
    op.create_check_constraint(
        op.f("ck_goal_fill_first_precaution"), "goal", "precaution OR fill_first"
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_goal_fill_first_precaution"), "goal", type_="check")
    op.drop_column("goal", "fill_first")
