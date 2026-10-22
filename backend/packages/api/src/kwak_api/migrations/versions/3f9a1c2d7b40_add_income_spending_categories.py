"""add income spending categories

Every household gets the default income categories, and its monthly incomes become income
lines: one on the first of each month, from the first income entered to the current month
(or the last income entered, if later), the income carried forward included (F-INC-1).

Revision ID: 3f9a1c2d7b40
Revises: 7edfe02ae280
Create Date: 2026-10-22 10:00:00.000000
"""

from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import sqlalchemy as sa
from alembic import op
from kwak_core.ids import uuid7

revision: str = "3f9a1c2d7b40"
down_revision: str | None = "7edfe02ae280"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Frozen copy of the income part of kwak_core.categories.DEFAULT_SPENDING_CATEGORIES.
INCOME: tuple[tuple[str, str], ...] = (
    ("Salaries", "Salaires"),
    ("Benefits", "Aides et allocations"),
    ("Refunds", "Remboursements"),
    ("Other income", "Autres revenus"),
)
# Where the monthly incomes go, and the label of their lines.
TARGET = ("Other income", "Autres revenus")
LABEL = ("Income", "Revenus")
# The household's months are Paris months: the migration's current month is too.
ZONE = ZoneInfo("Europe/Paris")


def _months(first: date, last: date) -> list[date]:
    out, day = [], first
    while day <= last:
        out.append(day)
        day = date(day.year + day.month // 12, day.month % 12 + 1, 1)
    return out


def _free(name: str, taken: set[str]) -> str:
    """`name`, or `name (2)`, `name (3)`… when a category already has it."""
    n, candidate = 1, name
    while candidate.casefold() in taken:
        n += 1
        candidate = f"{name} ({n})"
    return candidate


def _add_categories(conn: sa.Connection, household_id: object, fr: bool) -> object:
    """The income categories whose name is free, and always the target one (renamed if its name
    is taken, so no income is lost); the target category's id."""
    taken = {
        name.casefold()
        for (name,) in conn.execute(
            sa.text("SELECT name FROM spending_category WHERE household_id = :h"),
            {"h": household_id},
        )
    }
    position = conn.scalar(
        sa.text("SELECT coalesce(max(position), 0) FROM spending_category WHERE household_id = :h"),
        {"h": household_id},
    )
    target = None
    for en, french in INCOME:
        name = french if fr else en
        if name.casefold() in taken:
            if (en, french) != TARGET:
                continue
            name = _free(name, taken)
        position += 1
        category_id = uuid7()
        conn.execute(
            sa.text(
                "INSERT INTO spending_category (id, household_id, name, kind, one_off, position)"
                " VALUES (:id, :h, :n, 'income', false, :p)"
            ),
            {"id": category_id, "h": household_id, "n": name, "p": position},
        )
        if (en, french) == TARGET:
            target = category_id
    if target is None:
        raise RuntimeError("the target income category was not created")
    return target


def _entered(month: date, latest: datetime | None) -> datetime:
    start = datetime(month.year, month.month, 1, tzinfo=UTC)
    return start if latest is None else min(start, latest - timedelta(seconds=1))


def _income_lines(
    conn: sa.Connection, household_id: object, fr: bool, owner: object, target: object
) -> None:
    entered = {
        month: amount
        for month, amount in conn.execute(
            sa.text("SELECT month, amount FROM monthly_income WHERE household_id = :h"),
            {"h": household_id},
        )
    }
    if not entered:
        return
    last = max(max(entered), datetime.now(ZONE).date().replace(day=1))
    # Entered at the start of its month, but never after the line the user entered last, so
    # that one stays the last entry (F-ENT-4).
    latest = conn.scalar(
        sa.text("SELECT max(created_at) FROM spending_line WHERE household_id = :h"),
        {"h": household_id},
    )
    amount = Decimal(0)
    for month in _months(min(entered), last):
        amount = entered.get(month, amount)
        if amount <= 0:
            continue
        conn.execute(
            sa.text(
                "INSERT INTO spending_line"
                " (id, household_id, day, label, amount, category_id, entered_by_id,"
                "  created_at, updated_at)"
                " VALUES (:id, :h, :d, :l, :a, :c, :u, :now, :now)"
            ),
            {
                "id": uuid7(),
                "h": household_id,
                "d": month,
                "l": LABEL[1] if fr else LABEL[0],
                "a": amount,
                "c": target,
                "u": owner,
                "now": _entered(month, latest),
            },
        )


def upgrade() -> None:
    op.drop_constraint(
        op.f("ck_spending_category_spending_kind"), "spending_category", type_="check"
    )
    op.create_check_constraint(
        op.f("ck_spending_category_spending_kind"),
        "spending_category",
        "kind IN ('expense', 'savings', 'income')",
    )
    conn = op.get_bind()
    households = conn.execute(
        sa.text(
            "SELECT h.id,"
            " (SELECT u.language FROM app_user u"
            "   WHERE u.household_id = h.id AND u.role = 'owner' LIMIT 1),"
            " (SELECT u.id FROM app_user u WHERE u.household_id = h.id"
            "   ORDER BY u.role = 'owner' DESC, u.created_at LIMIT 1)"
            " FROM household h"
        )
    ).all()
    for household_id, language, owner in households:
        fr = language == "fr"
        target = _add_categories(conn, household_id, fr)
        if owner is not None:
            _income_lines(conn, household_id, fr, owner, target)
        elif conn.scalar(
            sa.text("SELECT count(*) FROM monthly_income WHERE household_id = :h"),
            {"h": household_id},
        ):
            raise RuntimeError(f"household {household_id} has incomes but no member to enter them")
    op.drop_table("monthly_income")


def downgrade() -> None:
    op.create_table(
        "monthly_income",
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("month", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("amount >= 0", name=op.f("ck_monthly_income_amount_not_negative")),
        sa.CheckConstraint(
            "extract(day FROM month) = 1", name=op.f("ck_monthly_income_month_start")
        ),
        sa.ForeignKeyConstraint(
            ["household_id"],
            ["household.id"],
            name=op.f("fk_monthly_income_household_id_household"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_monthly_income")),
        sa.UniqueConstraint(
            "household_id", "month", name=op.f("uq_monthly_income_household_id_month")
        ),
    )
    conn = op.get_bind()
    for household_id, month, amount in conn.execute(
        sa.text(
            "SELECT household_id, date_trunc('month', day)::date, sum(amount) FROM ("
            " SELECT l.household_id, l.day, l.amount FROM spending_line l"
            "  JOIN spending_category c ON c.id = l.category_id WHERE c.kind = 'income'"
            " UNION ALL"
            " SELECT l.household_id, l.day, p.amount FROM spending_line_part p"
            "  JOIN spending_line l ON l.id = p.line_id"
            "  JOIN spending_category c ON c.id = p.category_id WHERE c.kind = 'income'"
            ") AS pieces GROUP BY 1, 2"
        )
    ):
        conn.execute(
            sa.text(
                "INSERT INTO monthly_income (id, household_id, month, amount)"
                " VALUES (:id, :h, :m, :a)"
            ),
            {"id": uuid7(), "h": household_id, "m": month, "a": max(amount, Decimal(0))},
        )
    op.execute(
        "DELETE FROM spending_line WHERE category_id IN"
        " (SELECT id FROM spending_category WHERE kind = 'income')"
        " OR id IN (SELECT p.line_id FROM spending_line_part p"
        "  JOIN spending_category c ON c.id = p.category_id WHERE c.kind = 'income')"
    )
    op.execute(
        "DELETE FROM fixed_expense WHERE category_id IN"
        " (SELECT id FROM spending_category WHERE kind = 'income')"
    )
    op.execute("DELETE FROM spending_category WHERE kind = 'income'")
    op.drop_constraint(
        op.f("ck_spending_category_spending_kind"), "spending_category", type_="check"
    )
    op.create_check_constraint(
        op.f("ck_spending_category_spending_kind"),
        "spending_category",
        "kind IN ('expense', 'savings')",
    )
