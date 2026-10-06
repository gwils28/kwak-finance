"""add transaction transfer group

Revision ID: 94f92811ab56
Revises: 367653b1a7a9
Create Date: 2026-10-06 21:31:03.478007
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "94f92811ab56"
down_revision: str | None = "367653b1a7a9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("transaction", sa.Column("transfer_group_id", sa.Uuid(), nullable=True))
    op.create_index(
        op.f("ix_transaction_transfer_group_id"), "transaction", ["transfer_group_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_transaction_transfer_group_id"), table_name="transaction")
    op.drop_column("transaction", "transfer_group_id")
