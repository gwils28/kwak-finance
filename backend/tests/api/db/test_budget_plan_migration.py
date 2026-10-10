from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import pytest
from alembic import command
from kwak_api.db import Base
from kwak_api.migrate import alembic_config
from sqlalchemy import Connection, Engine, text

PLANS_REVISION = "e1f2a3b4c5d6"


@pytest.fixture
def clean(engine: Engine) -> Iterator[None]:
    yield
    with engine.begin() as conn:
        tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
        conn.execute(text(f"TRUNCATE {tables}"))


def _ids(conn: Connection) -> tuple[Any, Any, Any]:
    household = conn.scalar(
        text("INSERT INTO household (id, name) VALUES (gen_random_uuid(), 'Home') RETURNING id")
    )
    groceries, housing = (
        conn.scalar(
            text(
                "INSERT INTO category (id, household_id, name, kind)"
                " VALUES (gen_random_uuid(), :h, :n, 'expense') RETURNING id"
            ),
            {"h": household, "n": name},
        )
        for name in ("Groceries", "Housing")
    )
    return household, groceries, housing


def _target(
    conn: Connection, household: Any, category: Any, start: str, amount: str | None
) -> None:
    conn.execute(
        text(
            "INSERT INTO budget_target (id, household_id, category_id, valid_from, amount)"
            " VALUES (gen_random_uuid(), :h, :c, :v, :a)"
        ),
        {"h": household, "c": category, "v": date.fromisoformat(f"{start}-01"), "a": amount},
    )


@pytest.mark.usefixtures("clean")
def test_monthly_targets_become_quarterly_plans_and_come_back(
    database_url: str, engine: Engine
) -> None:
    config = alembic_config(database_url)
    command.downgrade(config, f"{PLANS_REVISION}-1")
    with engine.begin() as conn:
        household, groceries, housing = _ids(conn)
        _target(conn, household, housing, "2026-01", "900")
        _target(conn, household, groceries, "2026-02", "400")  # starts within Q1
        _target(conn, household, groceries, "2026-05", "450")  # changes within Q2
        _target(conn, household, groceries, "2026-08", None)  # removed within Q3

    command.upgrade(config, "head")

    with engine.connect() as conn:
        plans = conn.execute(
            text(
                "SELECT p.kind, p.year, p.number, p.start_month, p.end_month,"
                " coalesce(array_agg(t.amount ORDER BY t.amount)"
                " FILTER (WHERE t.id IS NOT NULL), '{}')"
                " FROM budget_plan p LEFT JOIN budget_plan_target t ON t.plan_id = p.id"
                " GROUP BY p.id ORDER BY p.start_month"
            )
        ).all()
    d, m = Decimal, date
    assert [tuple(p) for p in plans[:6]] == [
        ("quarter", 2026, 1, m(2026, 1, 1), m(2026, 1, 1), [d("900")]),
        ("quarter", 2026, 1, m(2026, 2, 1), m(2026, 3, 1), [d("400"), d("900")]),
        ("quarter", 2026, 2, m(2026, 4, 1), m(2026, 4, 1), [d("400"), d("900")]),
        ("quarter", 2026, 2, m(2026, 5, 1), m(2026, 6, 1), [d("450"), d("900")]),
        ("quarter", 2026, 3, m(2026, 7, 1), m(2026, 7, 1), [d("450"), d("900")]),
        ("quarter", 2026, 3, m(2026, 8, 1), m(2026, 9, 1), [d("900")]),
    ]
    # The targets stay in force up to the current quarter, as they were.
    assert all(p[5] == [d("900")] for p in plans[6:])
    assert plans[-1][4] >= datetime.now(UTC).date().replace(day=1)

    command.downgrade(config, f"{PLANS_REVISION}-1")

    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT c.name, t.valid_from, t.amount FROM budget_target t"
                " JOIN category c ON c.id = t.category_id ORDER BY c.name, t.valid_from"
            )
        ).all()
    in_force = {(name, start): amount for name, start, amount in rows}
    assert in_force[("Groceries", m(2026, 2, 1))] == d("400")
    assert in_force[("Groceries", m(2026, 5, 1))] == d("450")
    assert in_force[("Groceries", m(2026, 8, 1))] is None
    assert in_force[("Housing", m(2026, 1, 1))] == d("900")
    assert ("Housing", m(2026, 4, 1)) not in in_force  # unchanged: no redundant row
    command.upgrade(config, "head")
