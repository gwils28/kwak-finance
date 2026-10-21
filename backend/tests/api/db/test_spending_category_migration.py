from collections.abc import Iterator

import pytest
from alembic import command
from kwak_api.db import Base
from kwak_api.migrate import alembic_config
from sqlalchemy import Connection, Engine, text

REVISION = "c11fb2c06628"


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


@pytest.mark.usefixtures("clean")
def test_existing_households_get_the_flat_categories_in_their_owners_language(
    database_url: str, engine: Engine
) -> None:
    config = alembic_config(database_url)
    command.downgrade(config, f"{REVISION}-1")
    with engine.begin() as conn:
        french = _household(conn, "fr", "fr")
        unset = _household(conn, "unset", None)

    command.upgrade(config, "head")

    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT household_id::text, name, kind, one_off FROM spending_category"
                " ORDER BY position"
            )
        ).all()
    by_household = {
        h: [(n, k, o) for hh, n, k, o in rows if hh == h] for h in (str(french), str(unset))
    }
    assert by_household[str(french)][0] == ("Logement", "expense", True)
    assert ("Foyer", "expense", False) in by_household[str(french)]
    assert by_household[str(french)][-1] == ("Épargne", "savings", False)
    assert [n for n, _, _ in by_household[str(unset)]][:2] == ["Housing", "Groceries"]
    assert len(by_household[str(unset)]) == 12
