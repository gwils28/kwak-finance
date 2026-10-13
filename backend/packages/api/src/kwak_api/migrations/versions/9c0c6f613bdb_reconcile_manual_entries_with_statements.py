"""reconcile manual entries with statements

Revision ID: 9c0c6f613bdb
Revises: 5eceb504bce7
Create Date: 2026-10-13 16:05:01.043820
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9c0c6f613bdb"
down_revision: str | None = "5eceb504bce7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "import_batch",
        sa.Column("reconciled_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
    )
    op.add_column("transaction", sa.Column("bank_label", sa.Text(), nullable=True))
    op.add_column("transaction", sa.Column("entered_on", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("transaction", "entered_on")
    op.drop_column("transaction", "bank_label")
    op.drop_column("import_batch", "reconciled_count")
