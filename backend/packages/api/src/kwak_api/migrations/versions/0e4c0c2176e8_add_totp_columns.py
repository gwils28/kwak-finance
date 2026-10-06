"""add totp columns

Revision ID: 0e4c0c2176e8
Revises: d7b20ef8a5b9
Create Date: 2026-10-06 11:11:51.137734
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0e4c0c2176e8"
down_revision: str | None = "d7b20ef8a5b9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("app_user", sa.Column("totp_secret_enc", sa.LargeBinary(), nullable=True))
    op.add_column(
        "app_user", sa.Column("totp_confirmed_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("app_user", sa.Column("totp_last_counter", sa.BigInteger(), nullable=True))
    op.add_column(
        "user_session", sa.Column("mfa_verified_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("user_session", "mfa_verified_at")
    op.drop_column("app_user", "totp_last_counter")
    op.drop_column("app_user", "totp_confirmed_at")
    op.drop_column("app_user", "totp_secret_enc")
