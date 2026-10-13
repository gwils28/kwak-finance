"""add the budget month and the shift day

Revision ID: 4cfbb5480a5f
Revises: a7b8c9d0e1f2
Create Date: 2026-10-13 10:41:41.937116
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "4cfbb5480a5f"
down_revision: str | None = "a7b8c9d0e1f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("category", sa.Column("shift_day", sa.SmallInteger(), nullable=True))
    op.create_check_constraint(
        op.f("ck_category_shift_day_range"), "category", "shift_day BETWEEN 0 AND 31"
    )
    op.add_column("transaction", sa.Column("budget_month", sa.Date(), nullable=True))
    op.create_check_constraint(
        op.f("ck_transaction_budget_month_first_day"),
        "transaction",
        "extract(day FROM budget_month) = 1",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_transaction_budget_month_first_day"), "transaction", type_="check")
    op.drop_column("transaction", "budget_month")
    op.drop_constraint(op.f("ck_category_shift_day_range"), "category", type_="check")
    op.drop_column("category", "shift_day")
