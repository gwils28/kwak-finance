"""add the savings category kind and seed it for existing households

Revision ID: a7b8c9d0e1f2
Revises: 7761b8357349
Create Date: 2026-10-12 15:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from kwak_core.ids import uuid7

revision: str = "a7b8c9d0e1f2"
down_revision: str | None = "7761b8357349"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# A frozen copy of the savings default of kwak_core.categories as of this revision, by
# language: a migration must keep doing what it did, whatever the code becomes.
SAVINGS: dict[str, tuple[str, tuple[str, ...]]] = {
    "en": ("Savings & investments", ("Savings accounts", "Investments", "Retirement")),
    "fr": ("Épargne et placements", ("Livrets", "Placements", "Retraite")),
}


def upgrade() -> None:
    op.drop_constraint(op.f("ck_category_category_kind"), "category", type_="check")
    op.create_check_constraint(
        op.f("ck_category_category_kind"), "category", "kind IN ('expense', 'income', 'savings')"
    )
    conn = op.get_bind()
    # Households without a savings category, in their owner's language (English by default).
    households = conn.execute(
        sa.text(
            "SELECT h.id, coalesce(u.language, 'en') FROM household h"
            " LEFT JOIN app_user u ON u.household_id = h.id AND u.role = 'owner'"
            " WHERE NOT EXISTS ("
            "  SELECT 1 FROM category c WHERE c.household_id = h.id AND c.kind = 'savings')"
        )
    ).all()
    taken = sa.text(
        "SELECT 1 FROM category WHERE household_id = :household_id"
        " AND parent_id IS NULL AND lower(name) = lower(:name)"
    )
    insert = sa.text(
        "INSERT INTO category (id, household_id, parent_id, name, kind)"
        " VALUES (:id, :household_id, :parent_id, :name, 'savings')"
    )
    for household_id, language in households:
        name, children = SAVINGS[language]
        if conn.scalar(taken, {"household_id": household_id, "name": name}):
            continue  # the household made its own: leave it as it is
        parent_id = uuid7()
        row = {"household_id": household_id}
        conn.execute(insert, {**row, "id": parent_id, "parent_id": None, "name": name})
        for child in children:
            conn.execute(insert, {**row, "id": uuid7(), "parent_id": parent_id, "name": child})


def downgrade() -> None:
    # The seeded rows cannot be told apart from the household's own: keep them all, as the
    # closest older kind. Their transactions then count as spending again.
    op.execute("UPDATE category SET kind = 'expense' WHERE kind = 'savings'")
    op.drop_constraint(op.f("ck_category_category_kind"), "category", type_="check")
    op.create_check_constraint(
        op.f("ck_category_category_kind"), "category", "kind IN ('expense', 'income')"
    )
