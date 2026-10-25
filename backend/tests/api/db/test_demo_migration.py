from collections.abc import Iterator
from datetime import UTC, date, datetime

import pytest
from alembic import command
from kwak_api.db import Base
from kwak_api.migrate import alembic_config
from kwak_api.services import demo
from kwak_api.services.households import create_household
from kwak_core.demo import generate
from kwak_core.users import Language
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

DEMO_REVISION = "a0f22a064174"


@pytest.fixture
def clean(engine: Engine) -> Iterator[None]:
    yield
    with engine.begin() as conn:
        tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
        conn.execute(text(f"TRUNCATE {tables}"))


@pytest.mark.usefixtures("clean")
def test_going_back_deletes_the_demo_and_keeps_the_household(
    database_url: str, engine: Engine
) -> None:
    with Session(engine) as session:
        create_household(
            session,
            household_name="Home",
            email="owner@example.com",
            display_name="Owner",
            password="correct horse battery",
        )
        now = datetime(2026, 10, 25, 12, tzinfo=UTC)
        demo.build(session, generate(date(2026, 10, 25), Language.EN), now)
        session.commit()
    config = alembic_config(database_url)
    command.downgrade(config, f"{DEMO_REVISION}-1")
    try:
        with engine.connect() as conn:
            assert conn.scalars(text("SELECT name FROM household")).all() == ["Home"]
            assert conn.scalar(text("SELECT count(*) FROM app_user")) == 1
            assert conn.scalar(text("SELECT count(*) FROM wealth_value")) == 0
    finally:
        command.upgrade(config, "head")
