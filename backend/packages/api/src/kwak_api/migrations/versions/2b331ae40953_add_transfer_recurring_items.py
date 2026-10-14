"""add transfer recurring items

Revision ID: 2b331ae40953
Revises: 4cc0fe8c4297
Create Date: 2026-10-14 15:40:04.709341
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "2b331ae40953"
down_revision: str | None = "4cc0fe8c4297"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("recurring_item", sa.Column("destination_id", sa.Uuid(), nullable=True))
    op.create_index(
        op.f("ix_recurring_item_destination_id"), "recurring_item", ["destination_id"], unique=False
    )
    op.create_foreign_key(
        op.f("fk_recurring_item_destination_id_account"),
        "recurring_item",
        "account",
        ["destination_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_check_constraint(
        op.f("ck_recurring_item_transfer_accounts"),
        "recurring_item",
        "destination_id IS NULL OR destination_id <> account_id",
    )
    op.create_check_constraint(
        op.f("ck_recurring_item_transfer_no_category"),
        "recurring_item",
        "destination_id IS NULL OR category_id IS NULL",
    )


def downgrade() -> None:
    # Without its destination, a transfer item (empty label) would match every transaction.
    op.execute("DELETE FROM recurring_item WHERE destination_id IS NOT NULL")
    op.drop_constraint(
        op.f("ck_recurring_item_transfer_no_category"), "recurring_item", type_="check"
    )
    op.drop_constraint(op.f("ck_recurring_item_transfer_accounts"), "recurring_item", type_="check")
    op.drop_constraint(
        op.f("fk_recurring_item_destination_id_account"), "recurring_item", type_="foreignkey"
    )
    op.drop_index(op.f("ix_recurring_item_destination_id"), table_name="recurring_item")
    op.drop_column("recurring_item", "destination_id")
