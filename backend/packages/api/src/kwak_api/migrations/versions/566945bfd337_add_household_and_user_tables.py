"""add household and user tables

Revision ID: 566945bfd337
Revises:
Create Date: 2026-10-06 10:41:40.432410
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "566945bfd337"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "household",
        sa.Column("name", sa.String(length=100), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_household")),
    )
    op.create_table(
        "app_user",
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
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
        sa.CheckConstraint("role IN ('owner', 'member')", name=op.f("ck_app_user_role")),
        sa.CheckConstraint(
            "email = lower(btrim(email))", name=op.f("ck_app_user_email_normalized")
        ),
        sa.ForeignKeyConstraint(
            ["household_id"], ["household.id"], name=op.f("fk_app_user_household_id_household")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_app_user")),
        sa.UniqueConstraint("email", name=op.f("uq_app_user_email")),
    )
    op.create_index(op.f("ix_app_user_household_id"), "app_user", ["household_id"], unique=False)
    op.create_index(
        "uq_app_user_household_owner",
        "app_user",
        ["household_id"],
        unique=True,
        postgresql_where=sa.text("role = 'owner'"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_app_user_household_owner",
        table_name="app_user",
        postgresql_where=sa.text("role = 'owner'"),
    )
    op.drop_index(op.f("ix_app_user_household_id"), table_name="app_user")
    op.drop_table("app_user")
    op.drop_table("household")
