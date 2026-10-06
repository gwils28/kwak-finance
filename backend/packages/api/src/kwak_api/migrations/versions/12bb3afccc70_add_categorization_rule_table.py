"""add categorization_rule table

Revision ID: 12bb3afccc70
Revises: c4d5e6f7a8b9
Create Date: 2026-10-06 16:34:45.431595
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "12bb3afccc70"
down_revision: str | None = "c4d5e6f7a8b9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "categorization_rule",
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("category_id", sa.Uuid(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("label_contains", sa.String(length=100), nullable=True),
        sa.Column("amount_min", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("amount_max", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("account_id", sa.Uuid(), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["account.id"],
            name=op.f("fk_categorization_rule_account_id_account"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["category.id"],
            name=op.f("fk_categorization_rule_category_id_category"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["household_id"],
            ["household.id"],
            name=op.f("fk_categorization_rule_household_id_household"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_categorization_rule")),
    )
    op.create_index(
        op.f("ix_categorization_rule_category_id"),
        "categorization_rule",
        ["category_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_categorization_rule_household_id"),
        "categorization_rule",
        ["household_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_categorization_rule_household_id"), table_name="categorization_rule")
    op.drop_index(op.f("ix_categorization_rule_category_id"), table_name="categorization_rule")
    op.drop_table("categorization_rule")
