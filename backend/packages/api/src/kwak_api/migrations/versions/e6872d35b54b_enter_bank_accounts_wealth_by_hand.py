"""enter the bank accounts' wealth lines by hand

The savings and current accounts categories no longer list the app's cash accounts
automatically (F-WLT-4): they take lines entered by hand like the others. No value was stored
for the automatic lines, so nothing is lost.

Revision ID: e6872d35b54b
Revises: 02d05c0c4e51
Create Date: 2026-10-15 11:42:56.982880
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e6872d35b54b"
down_revision: str | None = "02d05c0c4e51"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ACCOUNT_TYPES = (
    "checking",
    "savings",
    "brokerage",
    "life_insurance",
    "pension",
    "employee_savings",
    "crypto",
    "loan",
    "real_estate",
    "use_asset",
    "other",
)


def upgrade() -> None:
    # Dropping the column drops its CHECK constraint too.
    op.drop_constraint(
        op.f("uq_wealth_category_household_id_holds"), "wealth_category", type_="unique"
    )
    op.drop_column("wealth_category", "holds")


def downgrade() -> None:
    op.add_column("wealth_category", sa.Column("holds", sa.String(length=20), nullable=True))
    allowed = ", ".join(f"'{t}'" for t in ACCOUNT_TYPES)
    op.create_check_constraint(
        op.f("ck_wealth_category_account_type"), "wealth_category", f"holds IN ({allowed})"
    )
    op.create_unique_constraint(
        op.f("uq_wealth_category_household_id_holds"), "wealth_category", ["household_id", "holds"]
    )
    # The default cash categories, known by their colour, hold the accounts again.
    op.execute(
        "UPDATE wealth_category SET holds = CASE colour"
        " WHEN 'savings' THEN 'savings' WHEN 'current' THEN 'checking' END"
        " WHERE id IN (SELECT DISTINCT ON (household_id, colour) id FROM wealth_category"
        " WHERE colour IN ('savings', 'current') ORDER BY household_id, colour, position)"
    )
