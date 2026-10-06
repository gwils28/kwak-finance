import kwak_api.models  # noqa: F401  (registers the tables on Base.metadata)
from alembic import context
from kwak_api.db import Base, make_engine
from kwak_api.settings import Settings

config = context.config
# Tests pass the URL in; the CLI (configured in pyproject.toml) reads it from the settings.
url = config.attributes.get("database_url") or Settings().database_url


def run_migrations_online() -> None:
    engine = make_engine(url)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    raise SystemExit("Offline (SQL script) migrations are not supported.")
run_migrations_online()
