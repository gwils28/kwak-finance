"""add recurring items

Revision ID: 4cc0fe8c4297
Revises: 9c0c6f613bdb
Create Date: 2026-10-13 20:49:28.300397
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "4cc0fe8c4297"
down_revision: str | None = "9c0c6f613bdb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "recurring_item",
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("category_id", sa.Uuid(), nullable=True),
        sa.Column("label", sa.String(length=100), nullable=False),
        sa.Column("amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("frequency", sa.String(length=10), nullable=False),
        sa.Column("day", sa.SmallInteger(), nullable=False),
        sa.Column("start_on", sa.Date(), nullable=False),
        sa.Column("end_on", sa.Date(), nullable=True),
        sa.Column("estimated", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("paused", sa.Boolean(), server_default=sa.text("false"), nullable=False),
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
            "frequency IN ('weekly', 'monthly', 'quarterly', 'yearly')",
            name=op.f("ck_recurring_item_recurring_frequency"),
        ),
        sa.CheckConstraint("day BETWEEN 0 AND 31", name=op.f("ck_recurring_item_day_range")),
        sa.CheckConstraint(
            "end_on IS NULL OR end_on >= start_on",
            name=op.f("ck_recurring_item_start_before_end"),
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["account.id"],
            name=op.f("fk_recurring_item_account_id_account"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["category.id"],
            name=op.f("fk_recurring_item_category_id_category"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["household_id"],
            ["household.id"],
            name=op.f("fk_recurring_item_household_id_household"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_recurring_item")),
    )
    op.create_index(op.f("ix_recurring_item_account_id"), "recurring_item", ["account_id"])
    op.create_index(op.f("ix_recurring_item_household_id"), "recurring_item", ["household_id"])
    op.create_table(
        "recurring_skip",
        sa.Column("item_id", sa.Uuid(), nullable=False),
        sa.Column("due_on", sa.Date(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["item_id"],
            ["recurring_item.id"],
            name=op.f("fk_recurring_skip_item_id_recurring_item"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_recurring_skip")),
        sa.UniqueConstraint("item_id", "due_on", name=op.f("uq_recurring_skip_item_id_due_on")),
    )
    op.create_table(
        "dismissed_suggestion",
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("label", sa.String(length=200), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["account.id"],
            name=op.f("fk_dismissed_suggestion_account_id_account"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dismissed_suggestion")),
        sa.UniqueConstraint(
            "account_id", "label", name=op.f("uq_dismissed_suggestion_account_id_label")
        ),
    )


def downgrade() -> None:
    op.drop_table("dismissed_suggestion")
    op.drop_table("recurring_skip")
    op.drop_index(op.f("ix_recurring_item_household_id"), table_name="recurring_item")
    op.drop_index(op.f("ix_recurring_item_account_id"), table_name="recurring_item")
    op.drop_table("recurring_item")
