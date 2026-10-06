"""enable unaccent for accent-insensitive search

Revision ID: b3f1c2d4e5a6
Revises: 099efbe435b1
Create Date: 2026-10-06 14:00:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "b3f1c2d4e5a6"
down_revision: str | None = "099efbe435b1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Ships with Postgres (contrib); the compose database user owns the database.
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")


def downgrade() -> None:
    op.execute("DROP EXTENSION IF EXISTS unaccent")
