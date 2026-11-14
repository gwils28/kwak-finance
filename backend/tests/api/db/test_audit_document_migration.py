from collections.abc import Iterator
from typing import Any

import pytest
from alembic import command
from kwak_api.db import Base
from kwak_api.migrate import alembic_config
from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError

REVISION = "fa4d3abca7b3"


@pytest.fixture
def clean(engine: Engine) -> Iterator[None]:
    yield
    with engine.begin() as conn:
        tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
        conn.execute(text(f"TRUNCATE {tables}"))


@pytest.mark.usefixtures("clean")
def test_default_spending_categories_get_their_preset_by_name_in_either_language(
    database_url: str, engine: Engine
) -> None:
    config = alembic_config(database_url)
    command.downgrade(config, f"{REVISION}-1")
    with engine.begin() as conn:
        household = conn.scalar(
            text("INSERT INTO household (id, name) VALUES (gen_random_uuid(), 'Home') RETURNING id")
        )
        for position, (name, kind) in enumerate(
            (
                ("Remboursements", "income"),
                ("salaries", "income"),
                ("Primes", "income"),  # added later: no preset
                ("Courses", "expense"),
            )
        ):
            conn.execute(
                text(
                    "INSERT INTO spending_category (id, household_id, name, kind, position,"
                    " created_at, updated_at) VALUES (gen_random_uuid(), :h, :n, :k, :p,"
                    " now(), now())"
                ),
                {"h": household, "n": name, "k": kind, "p": position},
            )

    command.upgrade(config, "head")

    with engine.connect() as conn:
        rows: list[Any] = conn.execute(
            text("SELECT name, preset FROM spending_category ORDER BY position")
        ).all()
    assert [tuple(r) for r in rows] == [
        ("Remboursements", "refunds"),
        ("salaries", "salaries"),
        ("Primes", None),
        ("Courses", "groceries"),
    ]


@pytest.mark.usefixtures("clean")
def test_a_line_holds_an_envelope_and_an_opening_year_from_1900(engine: Engine) -> None:
    with engine.begin() as conn:
        household = conn.scalar(
            text("INSERT INTO household (id, name) VALUES (gen_random_uuid(), 'Home') RETURNING id")
        )
        user = conn.scalar(
            text(
                "INSERT INTO app_user (id, household_id, email, display_name, password_hash,"
                " role, created_at, updated_at) VALUES (gen_random_uuid(), :h, 'a@b.c', 'A',"
                " 'x', 'owner', now(), now()) RETURNING id"
            ),
            {"h": household},
        )
        category = conn.scalar(
            text(
                "INSERT INTO wealth_category (id, household_id, name, kind, colour, position,"
                " created_at, updated_at) VALUES (gen_random_uuid(), :h, 'Stocks', 'asset',"
                " 'stocks', 0, now(), now()) RETURNING id"
            ),
            {"h": household},
        )
        conn.execute(
            text(
                "INSERT INTO wealth_line (id, household_id, category_id, name, owner_id,"
                " visibility, tax_envelope, opening_year, created_at, updated_at) VALUES"
                " (gen_random_uuid(), :h, :c, 'PEA', :u, 'private', 'pea', 2018, now(), now())"
            ),
            {"h": household, "c": category, "u": user},
        )
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO wealth_line (id, household_id, category_id, name, owner_id,"
                " visibility, opening_year, created_at, updated_at) VALUES"
                " (gen_random_uuid(), :h, :c, 'Old', :u, 'private', 1899, now(), now())"
            ),
            {"h": household, "c": category, "u": user},
        )
