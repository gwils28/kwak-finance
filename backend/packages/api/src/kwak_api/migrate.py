"""Programmatic Alembic configuration (tests, container entrypoint)."""

from alembic.config import Config

SCRIPT_LOCATION = "kwak_api:migrations"


def alembic_config(database_url: str) -> Config:
    config = Config()
    config.set_main_option("script_location", SCRIPT_LOCATION)
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return config
