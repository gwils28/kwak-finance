"""add invite table

Revision ID: 70d7f8f27ada
Revises: 8a2729317b99
Create Date: 2026-10-06 13:27:10.138967
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "70d7f8f27ada"
down_revision: str | None = "8a2729317b99"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "invite",
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["app_user.id"],
            name=op.f("fk_invite_created_by_id_app_user"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["household_id"], ["household.id"], name=op.f("fk_invite_household_id_household")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_invite")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_invite_token_hash")),
    )
    op.create_index(op.f("ix_invite_email"), "invite", ["email"], unique=False)
    op.create_index(op.f("ix_invite_household_id"), "invite", ["household_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_invite_household_id"), table_name="invite")
    op.drop_index(op.f("ix_invite_email"), table_name="invite")
    op.drop_table("invite")
