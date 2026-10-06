from collections.abc import Iterator

import pytest
from alembic import command
from kwak_api.db import Base
from kwak_api.migrate import alembic_config
from sqlalchemy import Engine, text

SEED_REVISION = "c4d5e6f7a8b9"


@pytest.fixture
def clean(engine: Engine) -> Iterator[None]:
    yield
    with engine.begin() as conn:
        tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
        conn.execute(text(f"TRUNCATE {tables}"))


@pytest.mark.usefixtures("clean")
def test_households_created_before_categories_get_the_default_tree(
    database_url: str, engine: Engine
) -> None:
    config = alembic_config(database_url)
    command.downgrade(config, f"{SEED_REVISION}-1")
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO household (id, name) VALUES (gen_random_uuid(), 'Existing')")
        )

    command.upgrade(config, "head")

    with engine.connect() as conn:
        names = set(conn.scalars(text("SELECT name FROM category")))
    assert {"Food", "Groceries", "Income", "Salary"} <= names
