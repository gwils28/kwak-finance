from collections.abc import Iterator
from typing import Any

import pytest
from alembic import command
from kwak_api.db import Base
from kwak_api.migrate import alembic_config
from sqlalchemy import Engine, text

REVISION = "5c7af92e494e"


@pytest.fixture
def clean(engine: Engine) -> Iterator[None]:
    yield
    with engine.begin() as conn:
        tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
        conn.execute(text(f"TRUNCATE {tables}"))


@pytest.mark.usefixtures("clean")
def test_default_categories_keep_their_preset_whatever_their_colour(
    database_url: str, engine: Engine
) -> None:
    config = alembic_config(database_url)
    command.downgrade(config, f"{REVISION}-1")
    with engine.begin() as conn:
        household = conn.scalar(
            text("INSERT INTO household (id, name) VALUES (gen_random_uuid(), 'Home') RETURNING id")
        )
        for position, (name, kind, colour) in enumerate(
            (
                ("Actions", "asset", "savings"),  # recoloured: still stocks
                ("stocks", "asset", "stocks"),
                ("Montres", "asset", "crypto"),  # added later: no preset
                ("Dettes", "debt", "debts"),
            )
        ):
            conn.execute(
                text(
                    "INSERT INTO wealth_category (id, household_id, name, kind, colour, position,"
                    " created_at, updated_at) VALUES (gen_random_uuid(), :h, :n, :k, :c, :p,"
                    " now(), now())"
                ),
                {"h": household, "n": name, "k": kind, "c": colour, "p": position},
            )

    command.upgrade(config, "head")

    with engine.connect() as conn:
        rows: list[Any] = conn.execute(
            text("SELECT name, preset FROM wealth_category ORDER BY position")
        ).all()
    assert [tuple(r) for r in rows] == [
        ("Actions", "stocks"),
        ("stocks", "stocks"),
        ("Montres", None),
        ("Dettes", "debts"),
    ]
