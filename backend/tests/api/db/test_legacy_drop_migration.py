from collections.abc import Iterator
from datetime import UTC, date, datetime

import pytest
from alembic import command
from kwak_api.db import Base
from kwak_api.migrate import alembic_config
from sqlalchemy import Connection, Engine, inspect, text
from sqlalchemy.exc import IntegrityError

REVISION = "c77a847d28b5"


@pytest.fixture
def clean(engine: Engine) -> Iterator[None]:
    yield
    with engine.begin() as conn:
        tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
        conn.execute(text(f"TRUNCATE {tables}"))


def _household(conn: Connection, analysis: date | None, wealth: date | None) -> str:
    household: str = conn.scalar(
        text(
            "INSERT INTO household (id, name, analysis_start, wealth_start)"
            " VALUES (gen_random_uuid(), 'Home', :a, :w) RETURNING id"
        ),
        {"a": analysis, "w": wealth},
    )
    return household


def _event(conn: Connection, household: str, action: str) -> None:
    conn.execute(
        text(
            "INSERT INTO audit_event (id, household_id, at, action, details)"
            " VALUES (gen_random_uuid(), :h, :at, :a, '{}')"
        ),
        {"h": household, "at": datetime(2026, 10, 1, tzinfo=UTC), "a": action},
    )


@pytest.mark.usefixtures("clean")
def test_the_old_tables_and_their_log_entries_go_and_the_analyses_start_becomes_the_wealth_start(
    database_url: str, engine: Engine
) -> None:
    config = alembic_config(database_url)
    command.downgrade(config, f"{REVISION}-1")
    with engine.begin() as conn:
        unset = _household(conn, date(2025, 1, 1), None)
        _event(conn, unset, "imported")
        _event(conn, unset, "rule_created")
        _event(conn, unset, "signed_in")
        _event(conn, unset, "spending_line_deleted")
        both = _household(conn, date(2025, 1, 1), date(2024, 6, 1))

    command.upgrade(config, "head")

    with engine.connect() as conn:
        starts = dict(conn.execute(text("SELECT id::text, wealth_start FROM household")).all())
        actions = set(conn.scalars(text("SELECT action FROM audit_event")))
        tables = set(inspect(conn).get_table_names())
    assert starts == {str(unset): date(2025, 1, 1), str(both): date(2024, 6, 1)}
    assert actions == {"signed_in", "spending_line_deleted"}
    assert not tables & {"account", "transaction", "category", "budget_plan", "recurring_item"}
    # A removed action can no longer be logged.
    with pytest.raises(IntegrityError), engine.begin() as conn:
        _event(conn, unset, "imported")

    # The way back works with data in place: the tables come back empty.
    command.downgrade(config, f"{REVISION}-1")
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM account")) == 0
        assert set(conn.scalars(text("SELECT action FROM audit_event"))) == actions
    command.upgrade(config, "head")
