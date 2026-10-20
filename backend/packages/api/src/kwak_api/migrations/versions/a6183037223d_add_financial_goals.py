"""add financial goals

Revision ID: a6183037223d
Revises: 12854b5b2ef4
Create Date: 2026-10-20 14:50:12.859763
"""

from collections.abc import Sequence
from datetime import datetime

import sqlalchemy as sa
from alembic import op

revision: str = "a6183037223d"
down_revision: str | None = "12854b5b2ef4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Frozen copies as of this revision: a migration must keep doing what it did.
AUDIT_BEFORE = (
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
    "wealth_line_deleted",
    "wealth_category_deleted",
    "rule_created",
    "rule_updated",
    "rule_deleted",
    "rules_applied",
    "categories_restored",
)
AUDIT_AFTER = (*AUDIT_BEFORE, "goal_deleted")


def _in(column: str, values: Sequence[str]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def _audit_check(values: Sequence[str]) -> None:
    op.drop_constraint(op.f("ck_audit_event_audit_action"), "audit_event", type_="check")
    op.create_check_constraint(
        op.f("ck_audit_event_audit_action"), "audit_event", _in("action", values)
    )


def _timestamps() -> list[sa.Column[datetime]]:
    return [
        sa.Column(name, sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)
        for name in ("created_at", "updated_at")
    ]


def upgrade() -> None:
    op.create_table(
        "goal",
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("tier", sa.String(length=20), nullable=False),
        sa.Column("target", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("start", sa.Date(), nullable=False),
        sa.Column("deadline", sa.Date(), nullable=True),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("visibility", sa.String(length=20), nullable=False),
        sa.Column("closed_from", sa.Date(), nullable=True),
        sa.Column("closed_as", sa.String(length=20), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            _in("tier", ("precaution", "medium", "long")), name=op.f("ck_goal_goal_tier")
        ),
        sa.CheckConstraint(
            _in("visibility", ("private", "shared", "joint")), name=op.f("ck_goal_visibility")
        ),
        sa.CheckConstraint(
            _in("closed_as", ("reached", "abandoned")), name=op.f("ck_goal_goal_closed_as")
        ),
        sa.CheckConstraint("target > 0", name=op.f("ck_goal_target_positive")),
        sa.CheckConstraint(
            "deadline IS NOT NULL OR tier = 'precaution'", name=op.f("ck_goal_deadline_needed")
        ),
        sa.CheckConstraint("extract(day from start) = 1", name=op.f("ck_goal_start_month")),
        sa.CheckConstraint("extract(day from deadline) = 1", name=op.f("ck_goal_deadline_month")),
        sa.CheckConstraint(
            "extract(day from closed_from) = 1", name=op.f("ck_goal_closed_from_month")
        ),
        sa.CheckConstraint(
            "(closed_from IS NULL) = (closed_as IS NULL)", name=op.f("ck_goal_closed_as_given")
        ),
        sa.ForeignKeyConstraint(
            ["household_id"], ["household.id"], name=op.f("fk_goal_household_id_household")
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["app_user.id"], name=op.f("fk_goal_owner_id_app_user")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_goal")),
    )
    op.create_index(op.f("ix_goal_household_id"), "goal", ["household_id"], unique=False)
    op.create_index(op.f("ix_goal_owner_id"), "goal", ["owner_id"], unique=False)
    op.create_table(
        "goal_funding",
        sa.Column("goal_id", sa.Uuid(), nullable=False),
        sa.Column("line_id", sa.Uuid(), nullable=False),
        sa.Column("share", sa.Integer(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("share BETWEEN 1 AND 100", name=op.f("ck_goal_funding_share_range")),
        sa.ForeignKeyConstraint(
            ["goal_id"], ["goal.id"], name=op.f("fk_goal_funding_goal_id_goal"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["line_id"],
            ["wealth_line.id"],
            name=op.f("fk_goal_funding_line_id_wealth_line"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_goal_funding")),
        sa.UniqueConstraint("goal_id", "line_id", name=op.f("uq_goal_funding_goal_id_line_id")),
    )
    op.create_index(op.f("ix_goal_funding_line_id"), "goal_funding", ["line_id"], unique=False)
    op.add_column(
        "household",
        sa.Column(
            "precaution_share",
            sa.Numeric(precision=3, scale=2),
            server_default=sa.text("0.70"),
            nullable=False,
        ),
    )
    op.add_column(
        "household", sa.Column("goal_capacity", sa.Numeric(precision=14, scale=2), nullable=True)
    )
    op.create_check_constraint(
        op.f("ck_household_precaution_share_range"),
        "household",
        "precaution_share BETWEEN 0.5 AND 1",
    )
    op.create_check_constraint(
        op.f("ck_household_goal_capacity_positive"), "household", "goal_capacity >= 0"
    )
    _audit_check(AUDIT_AFTER)


def downgrade() -> None:
    op.execute("DELETE FROM audit_event WHERE action = 'goal_deleted'")
    _audit_check(AUDIT_BEFORE)
    op.drop_constraint(op.f("ck_household_goal_capacity_positive"), "household", type_="check")
    op.drop_constraint(op.f("ck_household_precaution_share_range"), "household", type_="check")
    op.drop_column("household", "goal_capacity")
    op.drop_column("household", "precaution_share")
    op.drop_index(op.f("ix_goal_funding_line_id"), table_name="goal_funding")
    op.drop_table("goal_funding")
    op.drop_index(op.f("ix_goal_owner_id"), table_name="goal")
    op.drop_index(op.f("ix_goal_household_id"), table_name="goal")
    op.drop_table("goal")
