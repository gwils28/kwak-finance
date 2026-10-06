from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from alembic import command
from fastapi.testclient import TestClient
from kwak_api.auth.crypto import SecretBox
from kwak_api.auth.passwords import hash_password
from kwak_api.db import make_engine
from kwak_api.deps import get_db, get_now, request_scope
from kwak_api.main import create_app
from kwak_api.migrate import alembic_config
from kwak_api.models import Role, User
from kwak_api.services.households import create_household
from kwak_api.settings import Settings
from kwak_core.totp import STEP, hotp
from sqlalchemy import Connection, Engine
from sqlalchemy.orm import Session
from testcontainers.community.postgres import PostgresContainer


@pytest.fixture(scope="session")
def database_url() -> Iterator[str]:
    with PostgresContainer("postgres:17-alpine", driver="psycopg") as pg:
        yield pg.get_connection_url()


@pytest.fixture(scope="session")
def engine(database_url: str) -> Iterator[Engine]:
    """Engine on a database migrated to head."""
    command.upgrade(alembic_config(database_url), "head")
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


PASSWORD = "correct horse battery"
TOTP_SECRET = b"12345678901234567890"


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 1, 1, 12, tzinfo=UTC)

    def advance(self, delta: timedelta) -> None:
        self.now += delta


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def client(session: Session, clock: Clock) -> Iterator[TestClient]:
    def db() -> Iterator[Session]:
        # Same commit/rollback as the real get_db; commits only release a savepoint.
        yield from request_scope(session)

    app = create_app()
    app.dependency_overrides[get_db] = db
    app.dependency_overrides[get_now] = lambda: clock.now
    # Session cookies are Secure: the client must speak https to send them back.
    with TestClient(app, base_url="https://testserver") as client:
        yield client


@pytest.fixture
def unenrolled_owner(session: Session) -> User:
    """An owner straight out of `kwak create-owner`: no TOTP yet."""
    owner = create_household(
        session,
        household_name="Home",
        email="owner@example.com",
        display_name="Owner",
        password=PASSWORD,
    )
    # Committed, so a request that fails and rolls back does not take it away.
    session.commit()
    return owner


@pytest.fixture
def owner(unenrolled_owner: User, session: Session, clock: Clock) -> User:
    """An owner with TOTP enrolled on TOTP_SECRET."""
    box = SecretBox(Settings().encryption_key)
    unenrolled_owner.totp_secret_enc = box.encrypt(TOTP_SECRET, unenrolled_owner.id)
    unenrolled_owner.totp_confirmed_at = clock.now
    session.commit()
    return unenrolled_owner


def totp_code(clock: Clock) -> str:
    return hotp(TOTP_SECRET, int(clock.now.timestamp()) // STEP)


def csrf(client: TestClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies["kwak_csrf"]}


def log_in(client: TestClient, clock: Clock, email: str = "owner@example.com") -> None:
    """Password then TOTP. Advances the clock one step so codes are never replays."""
    clock.advance(timedelta(seconds=STEP))
    client.cookies.clear()
    response = client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    response = client.post(
        "/api/auth/totp/verify", json={"code": totp_code(clock)}, headers=csrf(client)
    )
    assert response.status_code == 200, response.text


@pytest.fixture
def member(owner: User, session: Session, clock: Clock) -> User:
    """A household member with TOTP enrolled on TOTP_SECRET."""
    user = User(
        household_id=owner.household_id,
        email="member@example.com",
        display_name="Member",
        password_hash=hash_password(PASSWORD),
        role=Role.MEMBER,
    )
    session.add(user)
    session.flush()
    user.totp_secret_enc = SecretBox(Settings().encryption_key).encrypt(TOTP_SECRET, user.id)
    user.totp_confirmed_at = clock.now
    session.commit()
    return user
