"""seed the default categories for existing households

Revision ID: c4d5e6f7a8b9
Revises: 15d3c403acf9
Create Date: 2026-10-06 15:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from kwak_core.ids import uuid7

revision: str = "c4d5e6f7a8b9"
down_revision: str | None = "15d3c403acf9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# A frozen copy of kwak_core.categories.DEFAULT_CATEGORIES as of this revision: a migration
# must keep doing what it did, whatever the code becomes. New households are seeded in code.
DEFAULTS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("Housing", "expense", ("Rent or mortgage", "Utilities", "Home insurance", "Repairs")),
    ("Food", "expense", ("Groceries", "Restaurants", "Bakery and coffee")),
    ("Transport", "expense", ("Fuel", "Public transport", "Car", "Parking and tolls")),
    ("Health", "expense", ("Pharmacy", "Doctors", "Health insurance")),
    ("Subscriptions", "expense", ("Phone and internet", "Streaming", "Other subscriptions")),
    ("Shopping", "expense", ("Clothing", "Electronics", "Home and garden")),
    ("Leisure", "expense", ("Sports", "Culture", "Holidays")),
    ("Personal", "expense", ("Hair and care", "Gifts", "Donations")),
    ("Education", "expense", ("Courses", "Books")),
    ("Finance", "expense", ("Bank fees", "Taxes", "Cash withdrawals")),
    ("Income", "income", ("Salary", "Refunds", "Interest", "Other income")),
)


def upgrade() -> None:
    conn = op.get_bind()
    households = conn.scalars(
        sa.text(
            "SELECT id FROM household h"
            " WHERE NOT EXISTS (SELECT 1 FROM category c WHERE c.household_id = h.id)"
        )
    ).all()
    insert = sa.text(
        "INSERT INTO category (id, household_id, parent_id, name, kind)"
        " VALUES (:id, :household_id, :parent_id, :name, :kind)"
    )
    for household_id in households:
        for name, kind, children in DEFAULTS:
            parent_id = uuid7()
            row = {"household_id": household_id, "kind": kind}
            conn.execute(insert, {**row, "id": parent_id, "parent_id": None, "name": name})
            for child in children:
                conn.execute(insert, {**row, "id": uuid7(), "parent_id": parent_id, "name": child})


def downgrade() -> None:
    # Seeded rows cannot be told apart from the household's own edits: keep them.
    pass
