"""add auth_failure table

Revision ID: 06878ca0b84c
Revises: 0e4c0c2176e8
Create Date: 2026-10-06 11:58:29.637572
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "06878ca0b84c"
down_revision: str | None = "0e4c0c2176e8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "auth_failure",
        sa.Column("subject", sa.String(length=400), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_auth_failure")),
    )
    op.create_index(
        "ix_auth_failure_subject_occurred_at",
        "auth_failure",
        ["subject", "occurred_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_auth_failure_subject_occurred_at", table_name="auth_failure")
    op.drop_table("auth_failure")
