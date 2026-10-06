from collections.abc import Iterator

import pytest
from kwak_api.db import make_engine
from sqlalchemy import Connection, Engine
from sqlalchemy.orm import Session
from testcontainers.community.postgres import PostgresContainer


@pytest.fixture(scope="session")
def database_url() -> Iterator[str]:
    with PostgresContainer("postgres:17-alpine", driver="psycopg") as pg:
        yield pg.get_connection_url()


@pytest.fixture(scope="session")
def engine(database_url: str) -> Iterator[Engine]:
    engine = make_engine(database_url)
    yield engine
    engine.dispose()


@pytest.fixture
def connection(engine: Engine) -> Iterator[Connection]:
    """A connection inside a transaction that is rolled back after the test."""
    with engine.connect() as conn, conn.begin() as tx:
        yield conn
        tx.rollback()


@pytest.fixture
def session(connection: Connection) -> Iterator[Session]:
    with Session(bind=connection, join_transaction_mode="create_savepoint") as s:
        yield s
