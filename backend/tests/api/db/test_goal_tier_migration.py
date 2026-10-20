from collections.abc import Iterator
from decimal import Decimal

import pytest
from alembic import command
from kwak_api.db import Base
from kwak_api.migrate import alembic_config
from sqlalchemy import Connection, Engine, text

TIER_REVISION = "b7c1d2e3f4a5"


@pytest.fixture
def clean(engine: Engine) -> Iterator[None]:
    yield
    with engine.begin() as conn:
        tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
        conn.execute(text(f"TRUNCATE {tables}"))


def _goal(conn: Connection, name: str, tier: str, deadline: str | None, closed: str | None) -> None:
    conn.execute(
        text(
            "INSERT INTO goal (id, household_id, name, tier, target, start, deadline, owner_id,"
            " visibility, closed_from, closed_as) SELECT gen_random_uuid(), household_id, :n, :t,"
            " 1000, '2026-01-01', CAST(:d AS date), id, 'shared',"
            " CASE WHEN CAST(:c AS text) IS NULL THEN NULL ELSE CAST('2026-02-01' AS date) END,"
            " :c FROM app_user"
        ),
        {"n": name, "t": tier, "d": deadline, "c": closed},
    )


@pytest.mark.usefixtures("clean")
def test_the_precaution_is_flagged_permanent_and_closed_goals_archived_or_cancelled(
    database_url: str, engine: Engine
) -> None:
    config = alembic_config(database_url)
    command.downgrade(config, f"{TIER_REVISION}-1")
    with engine.begin() as conn:
        household = conn.scalar(
            text("INSERT INTO household (id, name) VALUES (gen_random_uuid(), 'Home') RETURNING id")
        )
        conn.execute(
            text(
                "INSERT INTO app_user (id, household_id, email, display_name, password_hash, role)"
                " VALUES (gen_random_uuid(), :h, 'owner@example.test', 'Owner', 'x', 'owner')"
            ),
            {"h": household},
        )
        _goal(conn, "Précaution", "precaution", None, None)
        _goal(conn, "Japon", "medium", "2028-08-01", "reached")
        _goal(conn, "Bateau", "long", "2040-01-01", "abandoned")
        # half of the LDDS, worth 8500.01 in December (carried to the January start)
        conn.execute(
            text(
                "WITH c AS (INSERT INTO wealth_category (id, household_id, name, kind, colour,"
                " position) VALUES (gen_random_uuid(), :h, 'Livrets', 'asset', 'savings', 0)"
                " RETURNING id), l AS (INSERT INTO wealth_line (id, household_id, category_id,"
                " name, owner_id, visibility) SELECT gen_random_uuid(), :h, c.id, 'LDDS', u.id,"
                " 'shared' FROM c, app_user u RETURNING id), v AS (INSERT INTO wealth_value (id,"
                " line_id, month, amount) SELECT gen_random_uuid(), l.id, '2025-12-01', 8500.01"
                " FROM l) INSERT INTO goal_funding (id, goal_id, line_id, share)"
                " SELECT gen_random_uuid(), g.id, l.id, 50 FROM goal g, l WHERE g.name = 'Japon'"
            ),
            {"h": household},
        )

    command.upgrade(config, "head")
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT name, precaution, permanent, closed_as FROM goal")).all()
        assert set(rows) == {
            ("Précaution", True, True, None),
            ("Japon", False, False, "archived"),
            ("Bateau", False, False, "cancelled"),
        }
        # a share of the line's value becomes an envelope opening with that much
        assert conn.scalar(text("SELECT opening FROM goal_funding")) == Decimal("4250.00")

    command.downgrade(config, f"{TIER_REVISION}-1")
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT name, tier, closed_as FROM goal")).all()
        assert set(rows) == {
            ("Précaution", "precaution", None),
            ("Japon", "medium", "reached"),
            ("Bateau", "long", "abandoned"),
        }
    command.upgrade(config, "head")
