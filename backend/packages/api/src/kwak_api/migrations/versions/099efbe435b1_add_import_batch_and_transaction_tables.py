"""add import_batch and transaction tables

Revision ID: 099efbe435b1
Revises: 68fa6acfbaab
Create Date: 2026-10-06 15:13:03.046900
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "099efbe435b1"
down_revision: str | None = "68fa6acfbaab"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "import_batch",
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("format_key", sa.String(length=50), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("file_sha256", sa.String(length=64), nullable=False),
        sa.Column("imported_count", sa.Integer(), nullable=False),
        sa.Column("duplicate_count", sa.Integer(), nullable=False),
        sa.Column("skipped_count", sa.Integer(), nullable=False),
        sa.Column("error_count", sa.Integer(), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=True),
        sa.Column("period_end", sa.Date(), nullable=True),
        sa.Column("bank_balance", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("bank_balance_on", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rolled_back_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["account_id"], ["account.id"], name=op.f("fk_import_batch_account_id_account")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["app_user.id"], name=op.f("fk_import_batch_user_id_app_user")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_import_batch")),
    )
    op.create_index(
        op.f("ix_import_batch_account_id"), "import_batch", ["account_id"], unique=False
    )
    op.create_index(
        "uq_import_batch_account_file",
        "import_batch",
        ["account_id", "file_sha256"],
        unique=True,
        postgresql_where=sa.text("rolled_back_at IS NULL AND imported_count > 0"),
    )
    op.create_table(
        "transaction",
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("booked_on", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("label_raw", sa.Text(), nullable=False),
        sa.Column("label_norm", sa.Text(), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=True),
        sa.Column("import_batch_id", sa.Uuid(), nullable=True),
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
            ["account_id"], ["account.id"], name=op.f("fk_transaction_account_id_account")
        ),
        sa.ForeignKeyConstraint(
            ["import_batch_id"],
            ["import_batch.id"],
            name=op.f("fk_transaction_import_batch_id_import_batch"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_transaction")),
    )
    op.create_index(
        "ix_transaction_account_booked_on", "transaction", ["account_id", "booked_on"], unique=False
    )
    op.create_index(
        op.f("ix_transaction_import_batch_id"), "transaction", ["import_batch_id"], unique=False
    )
    op.create_index(
        "uq_transaction_account_fingerprint",
        "transaction",
        ["account_id", "fingerprint"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_transaction_account_fingerprint", table_name="transaction")
    op.drop_index(op.f("ix_transaction_import_batch_id"), table_name="transaction")
    op.drop_index("ix_transaction_account_booked_on", table_name="transaction")
    op.drop_table("transaction")
    op.drop_index(
        "uq_import_batch_account_file",
        table_name="import_batch",
        postgresql_where=sa.text("rolled_back_at IS NULL AND imported_count > 0"),
    )
    op.drop_index(op.f("ix_import_batch_account_id"), table_name="import_batch")
    op.drop_table("import_batch")
