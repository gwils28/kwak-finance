"""add pleasure goals

Revision ID: 24a4d2153871
Revises: c77a847d28b5
Create Date: 2026-10-22 21:03:53.900467
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "24a4d2153871"
down_revision: str | None = "c77a847d28b5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "goal", sa.Column("pleasure", sa.Boolean(), server_default=sa.text("false"), nullable=False)
    )
    op.drop_constraint(op.f("ck_goal_deadline_needed"), "goal", type_="check")
    op.create_check_constraint(
        op.f("ck_goal_deadline_needed"), "goal", "deadline IS NOT NULL OR permanent OR pleasure"
    )
    op.create_check_constraint(
        op.f("ck_goal_pleasure_alone"),
        "goal",
        "NOT pleasure OR (deadline IS NULL AND NOT permanent AND NOT precaution)",
    )


def downgrade() -> None:
    # Without a deadline, a pleasure goal has no place in the pyramid below: it goes, with its
    # fundings and adjustments (cascades), never a line.
    op.execute("DELETE FROM goal WHERE pleasure")
    op.drop_constraint(op.f("ck_goal_pleasure_alone"), "goal", type_="check")
    op.drop_constraint(op.f("ck_goal_deadline_needed"), "goal", type_="check")
    op.create_check_constraint(
        op.f("ck_goal_deadline_needed"), "goal", "deadline IS NOT NULL OR permanent"
    )
    op.drop_column("goal", "pleasure")
