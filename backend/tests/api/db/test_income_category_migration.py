from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from alembic import command
from kwak_api.db import Base
from kwak_api.migrate import alembic_config
from sqlalchemy import Connection, Engine, text

REVISION = "3f9a1c2d7b40"


@pytest.fixture
def clean(engine: Engine) -> Iterator[None]:
    yield
    with engine.begin() as conn:
        tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
        conn.execute(text(f"TRUNCATE {tables}"))


def _household(conn: Connection, name: str, owner_language: str | None) -> str:
    household: str = conn.scalar(
        text("INSERT INTO household (id, name) VALUES (gen_random_uuid(), :n) RETURNING id"),
        {"n": name},
    )
    conn.execute(
        text(
            "INSERT INTO app_user"
            " (id, household_id, email, display_name, password_hash, role, language)"
            " VALUES (gen_random_uuid(), :h, :e, 'Owner', 'x', 'owner', :l)"
        ),
        {"h": household, "e": f"{name}@example.test", "l": owner_language},
    )
    return household


def _category(conn: Connection, household: str, name: str, kind: str) -> None:
    conn.execute(
        text(
            "INSERT INTO spending_category (id, household_id, name, kind, one_off, position)"
            " VALUES (gen_random_uuid(), :h, :n, :k, false, 50)"
        ),
        {"h": household, "n": name, "k": kind},
    )


def _line(conn: Connection, household: str, day: date, amount: str, at: datetime) -> str:
    """An expense line in the household's first category, entered at `at`."""
    line: str = conn.scalar(
        text(
            "INSERT INTO spending_line"
            " (id, household_id, day, label, amount, category_id, entered_by_id, created_at)"
            " SELECT gen_random_uuid(), :h, :d, 'x', :a,"
            "  (SELECT id FROM spending_category WHERE household_id = :h"
            "   ORDER BY position LIMIT 1),"
            "  (SELECT id FROM app_user WHERE household_id = :h LIMIT 1), :at"
            " RETURNING id"
        ),
        {"h": household, "d": day, "a": Decimal(amount), "at": at},
    )
    return line


def _income(conn: Connection, household: str, month: date, amount: str) -> None:
    conn.execute(
        text(
            "INSERT INTO monthly_income (id, household_id, month, amount)"
            " VALUES (gen_random_uuid(), :h, :m, :a)"
        ),
        {"h": household, "m": month, "a": Decimal(amount)},
    )


@pytest.mark.usefixtures("clean")
def test_households_get_income_categories_and_their_monthly_incomes_become_lines(
    database_url: str, engine: Engine
) -> None:
    config = alembic_config(database_url)
    command.downgrade(config, f"{REVISION}-1")
    with engine.begin() as conn:
        french = _household(conn, "fr", "fr")
        english = _household(conn, "en", None)
        # A category already named like a default one keeps its name and kind.
        _category(conn, french, "Remboursements", "expense")
        _income(conn, french, date(2026, 1, 1), "2000.00")
        _income(conn, french, date(2026, 3, 1), "2100.50")
        _income(conn, french, date(2026, 4, 1), "0.00")

    command.upgrade(config, "head")

    with engine.connect() as conn:
        categories = conn.execute(
            text(
                "SELECT household_id::text, name, kind FROM spending_category"
                " WHERE kind = 'income' ORDER BY position"
            )
        ).all()
        lines = conn.execute(
            text(
                "SELECT l.day, l.label, l.amount, c.name, u.role FROM spending_line l"
                " JOIN spending_category c ON c.id = l.category_id"
                " JOIN app_user u ON u.id = l.entered_by_id"
                " WHERE l.household_id = :h ORDER BY l.day"
            ),
            {"h": french},
        ).all()
        kinds = conn.execute(
            text("SELECT kind FROM spending_category WHERE name = 'Remboursements'")
        ).all()

    assert [n for h, n, _ in categories if h == str(english)] == [
        "Salaries",
        "Benefits",
        "Refunds",
        "Other income",
    ]
    assert [n for h, n, _ in categories if h == str(french)] == [
        "Salaires",
        "Aides et allocations",
        "Autres revenus",
    ]
    assert kinds == [("expense",)]
    # The income carried forward into February counts as February's; a zero income is no line.
    assert [(d, a) for d, _, a, _, _ in lines] == [
        (date(2026, 1, 1), Decimal("2000.00")),
        (date(2026, 2, 1), Decimal("2000.00")),
        (date(2026, 3, 1), Decimal("2100.50")),
    ]
    assert {(label, c, role) for _, label, _, c, role in lines} == {
        ("Revenus", "Autres revenus", "owner")
    }


@pytest.mark.usefixtures("clean")
def test_an_income_carried_to_this_month_keeps_the_last_entry_and_a_taken_name(
    database_url: str, engine: Engine
) -> None:
    config = alembic_config(database_url)
    command.downgrade(config, f"{REVISION}-1")
    entered_last = datetime(2026, 9, 2, 8, tzinfo=UTC)
    with engine.begin() as conn:
        household = _household(conn, "en", "en")
        _category(conn, household, "Other income", "expense")
        last = _line(conn, household, date(2026, 9, 1), "-12.00", entered_last)
        _income(conn, household, date(2026, 6, 1), "1800.00")

    command.upgrade(config, "head")

    with engine.connect() as conn:
        latest = conn.scalar(
            text(
                "SELECT id::text FROM spending_line WHERE household_id = :h"
                " ORDER BY created_at DESC, id DESC LIMIT 1"
            ),
            {"h": household},
        )
        months = conn.execute(
            text(
                "SELECT l.day, c.name FROM spending_line l"
                " JOIN spending_category c ON c.id = l.category_id"
                " WHERE c.kind = 'income' ORDER BY l.day"
            )
        ).all()
    # The line entered last is still the user's own (F-ENT-4).
    assert latest == str(last)
    # Carried every month up to the current one, into a target renamed off the taken name.
    this_month = datetime.now(ZoneInfo("Europe/Paris")).date().replace(day=1)
    assert months[0] == (date(2026, 6, 1), "Other income (2)")
    assert months[-1][0] == this_month
    assert {name for _, name in months} == {"Other income (2)"}


@pytest.mark.usefixtures("clean")
def test_the_downgrade_sums_the_income_lines_back_into_monthly_incomes(
    database_url: str, engine: Engine
) -> None:
    config = alembic_config(database_url)
    command.downgrade(config, f"{REVISION}-1")
    with engine.begin() as conn:
        household = _household(conn, "en", "en")
        _income(conn, household, date(2026, 1, 1), "1500.00")
    command.upgrade(config, REVISION)
    with engine.begin() as conn:
        ids = dict(
            conn.execute(text("SELECT name, id FROM spending_category WHERE kind = 'income'")).all()
        )
        line = _line(conn, household, date(2026, 1, 20), "100.00", datetime.now(UTC))
        conn.execute(text("UPDATE spending_line SET category_id = NULL WHERE id = :l"), {"l": line})
        conn.execute(
            text(
                "INSERT INTO spending_line_part (id, line_id, position, category_id, amount)"
                " VALUES (gen_random_uuid(), :l, 0, :a, 60), (gen_random_uuid(), :l, 1, :b, 40)"
            ),
            {"l": line, "a": ids["Refunds"], "b": ids["Benefits"]},
        )

    command.downgrade(config, f"{REVISION}-1")

    with engine.connect() as conn:
        incomes = conn.execute(text("SELECT month, amount FROM monthly_income")).all()
        left = conn.scalar(text("SELECT count(*) FROM spending_category WHERE kind = 'income'"))
    # The converted income plus the split income line of January.
    assert (date(2026, 1, 1), Decimal("1600.00")) in incomes
    assert (date(2026, 2, 1), Decimal("1500.00")) in incomes
    assert left == 0
    command.upgrade(config, "head")
