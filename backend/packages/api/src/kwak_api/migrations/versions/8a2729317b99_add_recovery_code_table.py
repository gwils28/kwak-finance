"""add recovery_code table

Revision ID: 8a2729317b99
Revises: 06878ca0b84c
Create Date: 2026-10-06 12:07:48.256133
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "8a2729317b99"
down_revision: str | None = "06878ca0b84c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "recovery_code",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["app_user.id"],
            name=op.f("fk_recovery_code_user_id_app_user"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_recovery_code")),
        sa.UniqueConstraint("code_hash", name=op.f("uq_recovery_code_code_hash")),
    )
    op.create_index(op.f("ix_recovery_code_user_id"), "recovery_code", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_recovery_code_user_id"), table_name="recovery_code")
    op.drop_table("recovery_code")
