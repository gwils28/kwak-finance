from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from kwak_api.db import Base
from kwak_api.migrate import alembic_config
from sqlalchemy import Engine


def test_migrations_upgrade_downgrade_upgrade(database_url: str) -> None:
    config = alembic_config(database_url)
    command.upgrade(config, "head")
    command.downgrade(config, "base")
    command.upgrade(config, "head")


def test_models_match_migrations(database_url: str, engine: Engine) -> None:
    command.upgrade(alembic_config(database_url), "head")
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == []
