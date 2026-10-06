from alembic import context
from kwak_api.db import Base, make_engine
from kwak_api.settings import Settings

config = context.config
url = config.get_main_option("sqlalchemy.url") or Settings().database_url


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
