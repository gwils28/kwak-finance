"""add category table and transaction category

Revision ID: 15d3c403acf9
Revises: b3f1c2d4e5a6
Create Date: 2026-10-06 16:12:40.287229
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "15d3c403acf9"
down_revision: str | None = "b3f1c2d4e5a6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "category",
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("parent_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(length=60), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
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
        sa.CheckConstraint("kind IN ('expense', 'income')", name=op.f("ck_category_category_kind")),
        sa.ForeignKeyConstraint(
            ["household_id"], ["household.id"], name=op.f("fk_category_household_id_household")
        ),
        sa.ForeignKeyConstraint(
            ["parent_id"], ["category.id"], name=op.f("fk_category_parent_id_category")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_category")),
    )
    op.create_index(op.f("ix_category_household_id"), "category", ["household_id"], unique=False)
    op.create_index(op.f("ix_category_parent_id"), "category", ["parent_id"], unique=False)
    op.create_index(
        "uq_category_household_parent_name",
        "category",
        [
            "household_id",
            sa.literal_column("coalesce(parent_id, '00000000-0000-0000-0000-000000000000'::uuid)"),
            sa.literal_column("lower(name)"),
        ],
        unique=True,
    )
    op.add_column("transaction", sa.Column("category_id", sa.Uuid(), nullable=True))
    op.create_index(
        op.f("ix_transaction_category_id"), "transaction", ["category_id"], unique=False
    )
    op.create_foreign_key(
        op.f("fk_transaction_category_id_category"),
        "transaction",
        "category",
        ["category_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("fk_transaction_category_id_category"), "transaction", type_="foreignkey"
    )
    op.drop_index(op.f("ix_transaction_category_id"), table_name="transaction")
    op.drop_column("transaction", "category_id")
    op.drop_index("uq_category_household_parent_name", table_name="category")
    op.drop_index(op.f("ix_category_parent_id"), table_name="category")
    op.drop_index(op.f("ix_category_household_id"), table_name="category")
    op.drop_table("category")
