"""allow joint account visibility

Revision ID: f3a4b5c6d7e8
Revises: e1f2a3b4c5d6
Create Date: 2026-10-11 10:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "f3a4b5c6d7e8"
down_revision: str | None = "e1f2a3b4c5d6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(op.f("ck_account_visibility"), "account", type_="check")
    op.create_check_constraint(
        op.f("ck_account_visibility"), "account", "visibility IN ('private', 'shared', 'joint')"
    )


def downgrade() -> None:
    # A joint account stays visible to every member: the closest older value is shared.
    op.execute("UPDATE account SET visibility = 'shared' WHERE visibility = 'joint'")
    op.drop_constraint(op.f("ck_account_visibility"), "account", type_="check")
    op.create_check_constraint(
        op.f("ck_account_visibility"), "account", "visibility IN ('private', 'shared')"
    )
