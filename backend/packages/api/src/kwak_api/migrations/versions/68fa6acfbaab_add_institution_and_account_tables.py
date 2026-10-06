"""add institution and account tables

Revision ID: 68fa6acfbaab
Revises: 70d7f8f27ada
Create Date: 2026-10-06 14:31:40.662700
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "68fa6acfbaab"
down_revision: str | None = "70d7f8f27ada"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "institution",
        sa.Column("household_id", sa.Uuid(), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["household_id"], ["household.id"], name=op.f("fk_institution_household_id_household")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_institution")),
    )
    op.create_index(
        op.f("ix_institution_household_id"), "institution", ["household_id"], unique=False
    )
    op.create_index(
        "uq_institution_household_name",
        "institution",
        ["household_id", sa.literal_column("lower(name)")],
        unique=True,
    )
    op.create_table(
        "account",
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("institution_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("type", sa.String(length=20), nullable=False),
        sa.Column("visibility", sa.String(length=20), nullable=False),
        sa.Column("opening_balance", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("opening_date", sa.Date(), nullable=False),
        sa.Column("closed_on", sa.Date(), nullable=True),
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
        sa.CheckConstraint(
            "type IN ('checking', 'savings', 'brokerage', 'life_insurance', 'employee_savings',"
            " 'crypto', 'loan', 'real_estate', 'use_asset', 'other')",
            name=op.f("ck_account_account_type"),
        ),
        sa.CheckConstraint(
            "visibility IN ('private', 'shared')", name=op.f("ck_account_visibility")
        ),
        sa.CheckConstraint(
            "closed_on IS NULL OR closed_on >= opening_date",
            name=op.f("ck_account_closed_after_opening"),
        ),
        sa.ForeignKeyConstraint(
            ["household_id"], ["household.id"], name=op.f("fk_account_household_id_household")
        ),
        sa.ForeignKeyConstraint(
            ["institution_id"],
            ["institution.id"],
            name=op.f("fk_account_institution_id_institution"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["app_user.id"], name=op.f("fk_account_owner_id_app_user")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_account")),
    )
    op.create_index(op.f("ix_account_household_id"), "account", ["household_id"], unique=False)
    op.create_index(op.f("ix_account_institution_id"), "account", ["institution_id"], unique=False)
    op.create_index(op.f("ix_account_owner_id"), "account", ["owner_id"], unique=False)
    op.create_index(
        "uq_account_institution_name",
        "account",
        ["institution_id", sa.literal_column("lower(name)")],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_account_institution_name", table_name="account")
    op.drop_index(op.f("ix_account_owner_id"), table_name="account")
    op.drop_index(op.f("ix_account_institution_id"), table_name="account")
    op.drop_index(op.f("ix_account_household_id"), table_name="account")
    op.drop_table("account")
    op.drop_index("uq_institution_household_name", table_name="institution")
    op.drop_index(op.f("ix_institution_household_id"), table_name="institution")
    op.drop_table("institution")
