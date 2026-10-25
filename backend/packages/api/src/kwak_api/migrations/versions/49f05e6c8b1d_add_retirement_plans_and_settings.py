"""add retirement plans and settings

Revision ID: 49f05e6c8b1d
Revises: b1f9e8619368
Create Date: 2026-10-25 02:06:23.100804
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "49f05e6c8b1d"
down_revision: str | None = "b1f9e8619368"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

HOUSEHOLD_CHECKS = (
    ("ck_household_retirement_share_range", "retirement_share BETWEEN 0.5 AND 1.5"),
    ("ck_household_retirement_spending_positive", "retirement_spending >= 0"),
    (
        "ck_household_retirement_share_or_amount",
        "retirement_share IS NULL OR retirement_spending IS NULL",
    ),
    ("ck_household_pension_indexation_range", "pension_indexation BETWEEN -0.02 AND 0.01"),
    ("ck_household_horizon_age_range", "horizon_age BETWEEN 85 AND 105"),
)


def upgrade() -> None:
    op.create_table(
        "member_retirement",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("birth", sa.Date(), nullable=False),
        sa.Column("retirement", sa.Date(), nullable=False),
        sa.Column("earnings", sa.Numeric(14, 2), nullable=False),
        sa.Column("pension_month", sa.Date(), nullable=False),
        sa.Column("pension", sa.Numeric(14, 2), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("birth < retirement", name=op.f("ck_member_retirement_born_before")),
        sa.CheckConstraint("earnings >= 0", name=op.f("ck_member_retirement_earnings_positive")),
        sa.CheckConstraint(
            "extract(day from birth) = 1", name=op.f("ck_member_retirement_birth_month")
        ),
        sa.CheckConstraint(
            "extract(day from pension_month) = 1",
            name=op.f("ck_member_retirement_pension_month_first"),
        ),
        sa.CheckConstraint(
            "extract(day from retirement) = 1", name=op.f("ck_member_retirement_retirement_month")
        ),
        sa.CheckConstraint("pension >= 0", name=op.f("ck_member_retirement_pension_positive")),
        sa.CheckConstraint(
            "pension_month >= retirement",
            name=op.f("ck_member_retirement_pension_after_retirement"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["app_user.id"],
            name=op.f("fk_member_retirement_user_id_app_user"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_member_retirement")),
        sa.UniqueConstraint("user_id", name=op.f("uq_member_retirement_user_id")),
    )
    # NULL: the defaults of F-RET-2 (80 % of today's spending, -0.3 % a year, 95).
    op.add_column("household", sa.Column("retirement_share", sa.Numeric(3, 2), nullable=True))
    op.add_column("household", sa.Column("retirement_spending", sa.Numeric(14, 2), nullable=True))
    op.add_column("household", sa.Column("pension_indexation", sa.Numeric(4, 3), nullable=True))
    op.add_column("household", sa.Column("horizon_age", sa.SmallInteger(), nullable=True))
    for name, condition in HOUSEHOLD_CHECKS:
        op.create_check_constraint(op.f(name), "household", condition)


def downgrade() -> None:
    for name, _ in reversed(HOUSEHOLD_CHECKS):
        op.drop_constraint(op.f(name), "household", type_="check")
    op.drop_column("household", "horizon_age")
    op.drop_column("household", "pension_indexation")
    op.drop_column("household", "retirement_spending")
    op.drop_column("household", "retirement_share")
    op.drop_table("member_retirement")
