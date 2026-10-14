"""add transaction parts and notes

Revision ID: 1bc2ea744331
Revises: 2b331ae40953
Create Date: 2026-10-14 16:36:45.328536
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "1bc2ea744331"
down_revision: str | None = "2b331ae40953"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "transaction_part",
        sa.Column("transaction_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("category_id", sa.Uuid(), nullable=True),
        sa.Column("amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("amount <> 0", name=op.f("ck_transaction_part_amount_not_zero")),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["category.id"],
            name=op.f("fk_transaction_part_category_id_category"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["transaction_id"],
            ["transaction.id"],
            name=op.f("fk_transaction_part_transaction_id_transaction"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_transaction_part")),
    )
    op.create_index(
        op.f("ix_transaction_part_category_id"), "transaction_part", ["category_id"], unique=False
    )
    op.create_index(
        op.f("ix_transaction_part_transaction_id"),
        "transaction_part",
        ["transaction_id"],
        unique=False,
    )
    op.create_index(
        "uq_transaction_part_position",
        "transaction_part",
        ["transaction_id", "position"],
        unique=True,
    )
    op.add_column("transaction", sa.Column("note", sa.String(length=500), nullable=True))


def downgrade() -> None:
    # Split transactions lose their parts and go back to categorise.
    op.drop_column("transaction", "note")
    op.drop_index("uq_transaction_part_position", table_name="transaction_part")
    op.drop_index(op.f("ix_transaction_part_transaction_id"), table_name="transaction_part")
    op.drop_index(op.f("ix_transaction_part_category_id"), table_name="transaction_part")
    op.drop_table("transaction_part")
