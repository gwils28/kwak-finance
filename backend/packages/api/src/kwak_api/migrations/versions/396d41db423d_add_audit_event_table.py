"""add audit_event table

Revision ID: 396d41db423d
Revises: 1bc2ea744331
Create Date: 2026-10-14 22:15:54.264750
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "396d41db423d"
down_revision: str | None = "1bc2ea744331"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# A frozen copy of kwak_core.audit.AuditAction as of this revision.
ACTIONS = (
    "signed_in",
    "sign_in_failed",
    "signed_out",
    "recovery_codes_renewed",
    "invite_created",
    "invite_revoked",
    "member_joined",
    "settings_changed",
    "imported",
    "import_rolled_back",
    "transaction_deleted",
    "category_deleted",
    "plan_deleted",
    "recurring_deleted",
    "rule_created",
    "rule_updated",
    "rule_deleted",
    "rules_applied",
    "categories_restored",
)


def upgrade() -> None:
    allowed = ", ".join(f"'{a}'" for a in ACTIONS)
    op.create_table(
        "audit_event",
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("action", sa.String(length=40), nullable=False),
        sa.Column("private_to", sa.Uuid(), nullable=True),
        sa.Column("ip", sa.String(length=45), nullable=True),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(f"action IN ({allowed})", name=op.f("ck_audit_event_audit_action")),
        sa.ForeignKeyConstraint(
            ["household_id"],
            ["household.id"],
            name=op.f("fk_audit_event_household_id_household"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["private_to"],
            ["app_user.id"],
            name=op.f("fk_audit_event_private_to_app_user"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["app_user.id"],
            name=op.f("fk_audit_event_user_id_app_user"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_event")),
    )
    op.create_index(
        "ix_audit_event_household_id_at", "audit_event", ["household_id", "at"], unique=False
    )
    op.create_index(op.f("ix_audit_event_private_to"), "audit_event", ["private_to"], unique=False)
    op.create_index(op.f("ix_audit_event_user_id"), "audit_event", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_audit_event_user_id"), table_name="audit_event")
    op.drop_index(op.f("ix_audit_event_private_to"), table_name="audit_event")
    op.drop_index("ix_audit_event_household_id_at", table_name="audit_event")
    op.drop_table("audit_event")
