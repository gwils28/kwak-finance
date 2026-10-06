"""add budget_target table

Revision ID: 367653b1a7a9
Revises: 12bb3afccc70
Create Date: 2026-10-06 18:45:12.627273
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "367653b1a7a9"
down_revision: str | None = "12bb3afccc70"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "budget_target",
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("category_id", sa.Uuid(), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=14, scale=2), nullable=True),
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
        sa.CheckConstraint(
            "amount IS NULL OR amount >= 0", name=op.f("ck_budget_target_amount_not_negative")
        ),
        sa.CheckConstraint(
            "extract(day from valid_from) = 1",
            name=op.f("ck_budget_target_valid_from_first_of_month"),
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["category.id"],
            name=op.f("fk_budget_target_category_id_category"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["household_id"], ["household.id"], name=op.f("fk_budget_target_household_id_household")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_budget_target")),
        sa.UniqueConstraint(
            "category_id", "valid_from", name=op.f("uq_budget_target_category_id_valid_from")
        ),
    )
    op.create_index(
        op.f("ix_budget_target_household_id"), "budget_target", ["household_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_budget_target_household_id"), table_name="budget_target")
    op.drop_table("budget_target")
