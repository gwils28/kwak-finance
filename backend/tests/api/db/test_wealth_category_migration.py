from collections.abc import Iterator
from typing import Any

import pytest
from alembic import command
from kwak_api.db import Base
from kwak_api.migrate import alembic_config
from sqlalchemy import Connection, Engine, text

WEALTH_REVISION = "02d05c0c4e51"


@pytest.fixture
def clean(engine: Engine) -> Iterator[None]:
    yield
    with engine.begin() as conn:
        tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
        conn.execute(text(f"TRUNCATE {tables}"))


def _household(conn: Connection, owner_language: str | None) -> Any:
    household = conn.scalar(
        text("INSERT INTO household (id, name) VALUES (gen_random_uuid(), 'Home') RETURNING id")
    )
    conn.execute(
        text(
            "INSERT INTO app_user"
            " (id, household_id, email, display_name, password_hash, role, language)"
            " VALUES (gen_random_uuid(), :h, :e, 'Owner', 'x', 'owner', :l)"
        ),
        {"h": household, "e": f"{household}@example.test", "l": owner_language},
    )
    return household


def _categories(engine: Engine, household: Any) -> list[tuple[str, str, int]]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT name, kind, position FROM wealth_category"
                " WHERE household_id = :h ORDER BY position"
            ),
            {"h": household},
        ).all()
    return [(name, kind, position) for name, kind, position in rows]


@pytest.mark.usefixtures("clean")
def test_existing_households_get_the_wealth_categories_in_their_owners_language(
    database_url: str, engine: Engine
) -> None:
    config = alembic_config(database_url)
    command.downgrade(config, f"{WEALTH_REVISION}-1")
    with engine.begin() as conn:
        french, english = _household(conn, "fr"), _household(conn, None)

    command.upgrade(config, "head")

    fr = _categories(engine, french)
    assert fr[0] == ("Livrets", "asset", 0)
    assert fr[1] == ("Comptes courants", "asset", 1)
    assert fr[-1] == ("Dettes", "debt", 10)
    assert [c[0] for c in _categories(engine, english)][:3] == [
        "Savings accounts",
        "Current accounts",
        "Stocks",
    ]
