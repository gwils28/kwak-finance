"""widen the retirement horizon to 70 to 105

F-RET-2: the horizon age goes from 85-105 to 70-105 (75 by default, in `kwak_core`; NULL keeps
following the default). Downgrading forgets a horizon below 85, which falls back to the default.

Revision ID: c4e9a1f27d30
Revises: b2f767ec0967
Create Date: 2026-11-02 10:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "c4e9a1f27d30"
down_revision: str | None = "b2f767ec0967"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NAME = "ck_household_horizon_age_range"


def upgrade() -> None:
    op.drop_constraint(op.f(NAME), "household", type_="check")
    op.create_check_constraint(op.f(NAME), "household", "horizon_age BETWEEN 70 AND 105")


def downgrade() -> None:
    op.drop_constraint(op.f(NAME), "household", type_="check")
    op.execute("UPDATE household SET horizon_age = NULL WHERE horizon_age < 85")
    op.create_check_constraint(op.f(NAME), "household", "horizon_age BETWEEN 85 AND 105")
