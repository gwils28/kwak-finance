"""derive goal tiers, flag the precaution, permanent goals, archive or cancel, envelopes

Revision ID: b7c1d2e3f4a5
Revises: a6183037223d
Create Date: 2026-10-20 18:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b7c1d2e3f4a5"
down_revision: str | None = "a6183037223d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CLOSED_AS = {"reached": "archived", "abandoned": "cancelled"}


def _in(column: str, values: Sequence[str]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def _rename_closed_as(names: dict[str, str]) -> None:
    op.drop_constraint(op.f("ck_goal_goal_closed_as"), "goal", type_="check")
    for old, new in names.items():
        op.execute(
            sa.text("UPDATE goal SET closed_as = :new WHERE closed_as = :old").bindparams(
                new=new, old=old
            )
        )
    op.create_check_constraint(
        op.f("ck_goal_goal_closed_as"), "goal", _in("closed_as", tuple(names.values()))
    )


def upgrade() -> None:
    for flag in ("precaution", "permanent"):
        op.add_column(
            "goal", sa.Column(flag, sa.Boolean(), server_default=sa.text("false"), nullable=False)
        )
    op.drop_constraint(op.f("ck_goal_deadline_needed"), "goal", type_="check")
    op.execute("UPDATE goal SET precaution = true, permanent = true WHERE tier = 'precaution'")
    op.create_check_constraint(
        op.f("ck_goal_deadline_needed"), "goal", "deadline IS NOT NULL OR permanent"
    )
    op.create_check_constraint(
        op.f("ck_goal_precaution_permanent"), "goal", "permanent OR NOT precaution"
    )
    op.drop_constraint(op.f("ck_goal_goal_tier"), "goal", type_="check")
    op.drop_column("goal", "tier")
    _rename_closed_as(CLOSED_AS)
    op.add_column(
        "goal_funding",
        sa.Column(
            "opening",
            sa.Numeric(precision=14, scale=2),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        op.f("ck_goal_funding_opening_positive"), "goal_funding", "opening >= 0"
    )
    # A share of a line's value becomes an envelope opening with that share of its value then.
    op.execute(
        "UPDATE goal_funding f SET opening = floor(coalesce(("
        " SELECT v.amount FROM wealth_value v"
        " WHERE v.line_id = f.line_id AND v.month <= g.start ORDER BY v.month DESC LIMIT 1"
        " ), 0) * f.share) / 100 FROM goal g WHERE g.id = f.goal_id"
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_goal_funding_opening_positive"), "goal_funding", type_="check")
    op.drop_column("goal_funding", "opening")
    op.drop_constraint(op.f("ck_goal_precaution_permanent"), "goal", type_="check")
    # Only the precaution went without a deadline: the other permanent goals get this month.
    op.execute(
        "UPDATE goal SET deadline = date_trunc('month', CURRENT_DATE)::date"
        " WHERE deadline IS NULL AND NOT precaution"
    )
    _rename_closed_as({new: old for old, new in CLOSED_AS.items()})
    op.add_column("goal", sa.Column("tier", sa.String(length=20), nullable=True))
    # The tier the deadline gives today; there was no short term but the precaution.
    op.execute(
        "UPDATE goal SET tier = CASE"
        " WHEN precaution THEN 'precaution'"
        " WHEN deadline > (date_trunc('month', CURRENT_DATE) + interval '60 months')::date"
        " THEN 'long' ELSE 'medium' END"
    )
    op.alter_column("goal", "tier", nullable=False)
    op.create_check_constraint(
        op.f("ck_goal_goal_tier"), "goal", _in("tier", ("precaution", "medium", "long"))
    )
    op.drop_constraint(op.f("ck_goal_deadline_needed"), "goal", type_="check")
    op.create_check_constraint(
        op.f("ck_goal_deadline_needed"), "goal", "deadline IS NOT NULL OR tier = 'precaution'"
    )
    op.drop_column("goal", "permanent")
    op.drop_column("goal", "precaution")
