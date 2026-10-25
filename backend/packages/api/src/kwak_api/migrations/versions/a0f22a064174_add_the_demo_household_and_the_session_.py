"""add the demo household and the session's acting user

Revision ID: a0f22a064174
Revises: 49f05e6c8b1d
Create Date: 2026-10-25 11:35:23.602501
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a0f22a064174"
down_revision: str | None = "49f05e6c8b1d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "household",
        sa.Column("is_demo", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.create_index(
        "uq_household_demo",
        "household",
        ["is_demo"],
        unique=True,
        postgresql_where=sa.text("is_demo"),
    )
    op.add_column("user_session", sa.Column("acting_user_id", sa.Uuid(), nullable=True))
    op.create_index(
        op.f("ix_user_session_acting_user_id"), "user_session", ["acting_user_id"], unique=False
    )
    op.create_foreign_key(
        op.f("fk_user_session_acting_user_id_app_user"),
        "user_session",
        "app_user",
        ["acting_user_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    # Without the flag, the demo would become a second real household: it goes first.
    for statement in (
        "DELETE FROM goal_notice_dismissal WHERE user_id IN"
        " (SELECT id FROM app_user WHERE household_id IN (SELECT id FROM household WHERE is_demo))",
        "DELETE FROM goal WHERE household_id IN (SELECT id FROM household WHERE is_demo)",
        "DELETE FROM wealth_line WHERE household_id IN (SELECT id FROM household WHERE is_demo)",
        "DELETE FROM wealth_category WHERE household_id IN"
        " (SELECT id FROM household WHERE is_demo)",
        "DELETE FROM spending_line WHERE household_id IN (SELECT id FROM household WHERE is_demo)",
        "DELETE FROM fixed_expense WHERE household_id IN (SELECT id FROM household WHERE is_demo)",
        "DELETE FROM spending_category WHERE household_id IN"
        " (SELECT id FROM household WHERE is_demo)",
        "DELETE FROM invite WHERE household_id IN (SELECT id FROM household WHERE is_demo)",
        "DELETE FROM audit_event WHERE household_id IN (SELECT id FROM household WHERE is_demo)",
        "DELETE FROM member_retirement WHERE user_id IN"
        " (SELECT id FROM app_user WHERE household_id IN (SELECT id FROM household WHERE is_demo))",
        "DELETE FROM app_user WHERE household_id IN (SELECT id FROM household WHERE is_demo)",
        "DELETE FROM household WHERE is_demo",
    ):
        op.execute(statement)
    op.drop_constraint(
        op.f("fk_user_session_acting_user_id_app_user"), "user_session", type_="foreignkey"
    )
    op.drop_index(op.f("ix_user_session_acting_user_id"), table_name="user_session")
    op.drop_column("user_session", "acting_user_id")
    op.drop_index("uq_household_demo", table_name="household", postgresql_where=sa.text("is_demo"))
    op.drop_column("household", "is_demo")
