"""add user language

Revision ID: 1cdee9503c79
Revises: 94f92811ab56
Create Date: 2026-10-06 23:10:17.969473
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "1cdee9503c79"
down_revision: str | None = "94f92811ab56"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("app_user", sa.Column("language", sa.String(length=5), nullable=True))
    op.create_check_constraint(op.f("ck_app_user_language"), "app_user", "language IN ('en', 'fr')")


def downgrade() -> None:
    op.drop_constraint(op.f("ck_app_user_language"), "app_user", type_="check")
    op.drop_column("app_user", "language")
