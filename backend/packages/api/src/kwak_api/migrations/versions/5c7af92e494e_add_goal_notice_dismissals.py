"""add goal notice dismissals and wealth category presets

Revision ID: 5c7af92e494e
Revises: 24a4d2153871
Create Date: 2026-10-23 14:52:14.801965
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# The default wealth categories (kwak_core.wealth, at this revision): names and preset key.
DEFAULTS = (
    ("Savings accounts", "Livrets", "asset", "savings"),
    ("Current accounts", "Comptes courants", "asset", "current"),
    ("Stocks", "Actions", "asset", "stocks"),
    ("Crypto", "Cryptos", "asset", "crypto"),
    ("Bonds", "Obligations", "asset", "bonds"),
    ("Private equity", "Private equity", "asset", "private-equity"),
    ("Gold", "Or", "asset", "gold"),
    ("Real estate", "Immobilier", "asset", "real-estate"),
    ("Equipment", "Matériels", "asset", "equipment"),
    ("Exotic", "Exotiques", "asset", "exotic"),
    ("Debts", "Dettes", "debt", "debts"),
)

revision: str = "5c7af92e494e"
down_revision: str | None = "24a4d2153871"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "goal_notice_dismissal",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("rule", sa.String(length=30), nullable=False),
        sa.Column("goal_id", sa.Uuid(), nullable=True),
        sa.Column("line_id", sa.Uuid(), nullable=True),
        sa.Column("until", sa.Date(), nullable=True),
        sa.Column("severity", sa.String(length=10), nullable=True),
        sa.Column("amount", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "(until IS NULL) <> (severity IS NULL)",
            name=op.f("ck_goal_notice_dismissal_snoozed_or_dismissed"),
        ),
        sa.CheckConstraint(
            "extract(day from until) = 1", name=op.f("ck_goal_notice_dismissal_until_month")
        ),
        sa.ForeignKeyConstraint(
            ["goal_id"],
            ["goal.id"],
            name=op.f("fk_goal_notice_dismissal_goal_id_goal"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["line_id"],
            ["wealth_line.id"],
            name=op.f("fk_goal_notice_dismissal_line_id_wealth_line"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["app_user.id"],
            name=op.f("fk_goal_notice_dismissal_user_id_app_user"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_goal_notice_dismissal")),
        sa.UniqueConstraint(
            "user_id",
            "rule",
            "goal_id",
            "line_id",
            name=op.f("uq_goal_notice_dismissal_user_id_rule_goal_id_line_id"),
            postgresql_nulls_not_distinct=True,
        ),
    )

    op.add_column("wealth_category", sa.Column("preset", sa.String(length=20), nullable=True))
    # A default category is known by its default name, in either language, not its colour,
    # which its owner may have changed.
    for en, fr, kind, preset in DEFAULTS:
        op.execute(
            sa.text(
                "UPDATE wealth_category SET preset = :preset"
                " WHERE kind = :kind AND lower(name) IN (lower(:en), lower(:fr))"
            ).bindparams(preset=preset, kind=kind, en=en, fr=fr)
        )


def downgrade() -> None:
    op.drop_column("wealth_category", "preset")
    op.drop_table("goal_notice_dismissal")
