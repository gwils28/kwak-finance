"""add budget plan target paid from

Revision ID: 7761b8357349
Revises: f3a4b5c6d7e8
Create Date: 2026-10-11 11:47:16.242315
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "7761b8357349"
down_revision: str | None = "f3a4b5c6d7e8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("budget_plan_target", sa.Column("paid_from", sa.String(length=10), nullable=True))
    op.create_check_constraint(
        op.f("ck_budget_plan_target_paid_from"),
        "budget_plan_target",
        "paid_from IN ('joint', 'personal')",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_budget_plan_target_paid_from"), "budget_plan_target", type_="check")
    op.drop_column("budget_plan_target", "paid_from")
