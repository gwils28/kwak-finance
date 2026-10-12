from collections.abc import Iterator
from typing import Any

import pytest
from alembic import command
from kwak_api.db import Base
from kwak_api.migrate import alembic_config
from sqlalchemy import Connection, Engine, text

SAVINGS_REVISION = "a7b8c9d0e1f2"


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


def _tree(conn: Connection, household: Any) -> dict[str, tuple[str, list[str]]]:
    rows = conn.execute(
        text(
            "SELECT p.name, p.kind, coalesce(array_agg(c.name ORDER BY c.name)"
            " FILTER (WHERE c.id IS NOT NULL), '{}')"
            " FROM category p LEFT JOIN category c ON c.parent_id = p.id"
            " WHERE p.household_id = :h AND p.parent_id IS NULL GROUP BY p.id"
        ),
        {"h": household},
    ).all()
    return {name: (kind, list(children)) for name, kind, children in rows}


@pytest.mark.usefixtures("clean")
def test_existing_households_get_the_savings_category_in_their_owners_language(
    database_url: str, engine: Engine
) -> None:
    config = alembic_config(database_url)
    command.downgrade(config, f"{SAVINGS_REVISION}-1")
    with engine.begin() as conn:
        french, english = _household(conn, "fr"), _household(conn, None)

    command.upgrade(config, "head")

    with engine.connect() as conn:
        assert _tree(conn, french)["Épargne et placements"] == (
            "savings",
            ["Livrets", "Placements", "Retraite"],
        )
        assert _tree(conn, english)["Savings & investments"] == (
            "savings",
            ["Investments", "Retirement", "Savings accounts"],
        )


@pytest.mark.usefixtures("clean")
def test_a_category_already_named_so_is_not_duplicated_and_downgrade_turns_savings_to_expense(
    database_url: str, engine: Engine
) -> None:
    config = alembic_config(database_url)
    command.downgrade(config, f"{SAVINGS_REVISION}-1")
    with engine.begin() as conn:
        household = _household(conn, "fr")
        conn.execute(
            text(
                "INSERT INTO category (id, household_id, name, kind)"
                " VALUES (gen_random_uuid(), :h, 'épargne et placements', 'expense')"
            ),
            {"h": household},
        )

    command.upgrade(config, "head")
    with engine.connect() as conn:
        assert _tree(conn, household) == {"épargne et placements": ("expense", [])}

    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO category (id, household_id, name, kind)"
                " VALUES (gen_random_uuid(), :h, 'PEA', 'savings')"
            ),
            {"h": household},
        )
    command.downgrade(config, f"{SAVINGS_REVISION}-1")
    with engine.connect() as conn:
        assert _tree(conn, household)["PEA"] == ("expense", [])
    command.upgrade(config, "head")
