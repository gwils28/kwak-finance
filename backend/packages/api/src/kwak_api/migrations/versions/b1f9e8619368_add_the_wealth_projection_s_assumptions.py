"""add the wealth projection's assumptions

Revision ID: b1f9e8619368
Revises: c806db3eb660
Create Date: 2026-10-24 21:17:20.853232
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b1f9e8619368"
down_revision: str | None = "c806db3eb660"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CHECKS = (
    ("ck_household_inflation_range", "household", "inflation BETWEEN -0.05 AND 0.2"),
    (
        "ck_wealth_category_assumption_whole",
        "wealth_category",
        "(expected_return IS NULL) = (volatility IS NULL)",
    ),
    (
        "ck_wealth_category_assumption_range",
        "wealth_category",
        "expected_return > -1 AND expected_return <= 1 AND volatility BETWEEN 0 AND 2",
    ),
    ("ck_wealth_line_debt_payment_positive", "wealth_line", "debt_payment >= 0"),
    ("ck_wealth_line_debt_rate_range", "wealth_line", "debt_rate BETWEEN 0 AND 1"),
    ("ck_wealth_line_debt_insurance_positive", "wealth_line", "debt_insurance >= 0"),
)


def upgrade() -> None:
    # NULL: the defaults of F-SIM-1 (each category's by its preset, 2 % inflation).
    op.add_column("household", sa.Column("inflation", sa.Numeric(4, 3), nullable=True))
    op.add_column("wealth_category", sa.Column("expected_return", sa.Numeric(4, 3), nullable=True))
    op.add_column("wealth_category", sa.Column("volatility", sa.Numeric(4, 3), nullable=True))
    op.add_column("wealth_line", sa.Column("debt_payment", sa.Numeric(14, 2), nullable=True))
    op.add_column(
        "wealth_line",
        sa.Column("debt_rate", sa.Numeric(5, 4), server_default=sa.text("0"), nullable=False),
    )
    op.add_column(
        "wealth_line",
        sa.Column("debt_insurance", sa.Numeric(14, 2), server_default=sa.text("0"), nullable=False),
    )
    for name, table, condition in CHECKS:
        op.create_check_constraint(op.f(name), table, condition)


def downgrade() -> None:
    for name, table, _ in reversed(CHECKS):
        op.drop_constraint(op.f(name), table, type_="check")
    op.drop_column("wealth_line", "debt_insurance")
    op.drop_column("wealth_line", "debt_rate")
    op.drop_column("wealth_line", "debt_payment")
    op.drop_column("wealth_category", "volatility")
    op.drop_column("wealth_category", "expected_return")
    op.drop_column("household", "inflation")
