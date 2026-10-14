from typing import Any

import pytest
from alembic import command
from kwak_api.migrate import alembic_config
from sqlalchemy import Engine, text

from tests.api.db.test_savings_category_migration import _household, clean  # noqa: F401

WEALTH_REVISION = "02d05c0c4e51"


def _categories(engine: Engine, household: Any) -> list[tuple[str, str, int, str | None]]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT name, kind, position, holds FROM wealth_category"
                " WHERE household_id = :h ORDER BY position"
            ),
            {"h": household},
        ).all()
    return [(name, kind, position, holds) for name, kind, position, holds in rows]


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
    assert fr[0] == ("Livrets", "asset", 0, "savings")
    assert fr[1] == ("Comptes courants", "asset", 1, "checking")
    assert fr[-1] == ("Dettes", "debt", 10, None)
    assert [c[0] for c in _categories(engine, english)][:3] == [
        "Savings accounts",
        "Current accounts",
        "Stocks",
    ]
