"""add professional goals

Professional goals sit in the tier of their deadline, their cost less what others pay as their
target, equipment renewed every few years (F-GOAL-11, spec v1.24). The activity log records a
renewal.

Revision ID: ce114400dfb0
Revises: 384a91d9ace2
Create Date: 2026-11-14 09:39:33.828942
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "ce114400dfb0"
down_revision: str | None = "384a91d9ace2"
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
    "wealth_line_deleted",
    "wealth_category_deleted",
    "goal_deleted",
    "spending_line_deleted",
    "spending_category_deleted",
    "fixed_expense_deleted",
    "categories_restored",
)
AUDIT_AFTER = (*AUDIT_BEFORE, "goal_renewed")
PRO_TYPES = ("equipment", "training", "business", "career_change", "move")
AID_SOURCES = ("cpf", "employer", "france_travail", "honour_loan", "other")


def _in(column: str, values: Sequence[str]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def _audit_check(values: Sequence[str]) -> None:
    op.drop_constraint(op.f("ck_audit_event_audit_action"), "audit_event", type_="check")
    op.create_check_constraint(
        op.f("ck_audit_event_audit_action"), "audit_event", _in("action", values)
    )


def upgrade() -> None:
    op.create_table(
        "goal_aid",
        sa.Column("goal_id", sa.Uuid(), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("received", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(_in("source", AID_SOURCES), name=op.f("ck_goal_aid_goal_aid_source")),
        sa.CheckConstraint("amount > 0", name=op.f("ck_goal_aid_amount_positive")),
        sa.ForeignKeyConstraint(
            ["goal_id"], ["goal.id"], name=op.f("fk_goal_aid_goal_id_goal"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_goal_aid")),
    )
    op.create_index(op.f("ix_goal_aid_goal_id"), "goal_aid", ["goal_id"], unique=False)
    op.add_column("goal", sa.Column("pro_type", sa.String(length=20), nullable=True))
    op.create_check_constraint(op.f("ck_goal_goal_pro_type"), "goal", _in("pro_type", PRO_TYPES))
    op.add_column("goal", sa.Column("cost", sa.Numeric(precision=14, scale=2), nullable=True))
    op.add_column("goal", sa.Column("renew_years", sa.SmallInteger(), nullable=True))
    op.add_column("goal", sa.Column("renewed_from", sa.Uuid(), nullable=True))
    op.add_column("goal", sa.Column("next_cycle", sa.String(length=20), nullable=True))
    op.create_check_constraint(
        op.f("ck_goal_goal_next_cycle"), "goal", _in("next_cycle", ("started", "declined"))
    )
    op.create_unique_constraint(op.f("uq_goal_renewed_from"), "goal", ["renewed_from"])
    op.create_foreign_key(
        op.f("fk_goal_renewed_from_goal"),
        "goal",
        "goal",
        ["renewed_from"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_check_constraint(
        op.f("ck_goal_professional_alone"),
        "goal",
        "pro_type IS NULL OR (deadline IS NOT NULL AND NOT permanent AND NOT precaution"
        " AND NOT pleasure)",
    )
    op.create_check_constraint(
        op.f("ck_goal_cost_professional"),
        "goal",
        "(pro_type IS NULL) = (cost IS NULL) AND (cost IS NULL OR cost >= target)",
    )
    op.create_check_constraint(
        op.f("ck_goal_renew_equipment"),
        "goal",
        "renew_years IS NULL OR (pro_type = 'equipment' AND renew_years BETWEEN 1 AND 10)",
    )
    _audit_check(AUDIT_AFTER)


def downgrade() -> None:
    op.execute("DELETE FROM audit_event WHERE action = 'goal_renewed'")
    _audit_check(AUDIT_BEFORE)
    # Professional goals become standard goals with the same target and deadline.
    op.drop_constraint(op.f("ck_goal_renew_equipment"), "goal", type_="check")
    op.drop_constraint(op.f("ck_goal_cost_professional"), "goal", type_="check")
    op.drop_constraint(op.f("ck_goal_professional_alone"), "goal", type_="check")
    op.drop_constraint(op.f("fk_goal_renewed_from_goal"), "goal", type_="foreignkey")
    op.drop_constraint(op.f("uq_goal_renewed_from"), "goal", type_="unique")
    op.drop_constraint(op.f("ck_goal_goal_next_cycle"), "goal", type_="check")
    op.drop_column("goal", "next_cycle")
    op.drop_column("goal", "renewed_from")
    op.drop_column("goal", "renew_years")
    op.drop_column("goal", "cost")
    op.drop_constraint(op.f("ck_goal_goal_pro_type"), "goal", type_="check")
    op.drop_column("goal", "pro_type")
    op.drop_index(op.f("ix_goal_aid_goal_id"), table_name="goal_aid")
    op.drop_table("goal_aid")
