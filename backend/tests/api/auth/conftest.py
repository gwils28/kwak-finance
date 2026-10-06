from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from kwak_api.auth.crypto import SecretBox
from kwak_api.deps import get_db, get_now, request_scope
from kwak_api.main import create_app
from kwak_api.models import User
from kwak_api.services.households import create_household
from kwak_api.settings import Settings
from kwak_core.totp import STEP, hotp
from sqlalchemy.orm import Session

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


def log_in(client: TestClient, clock: Clock) -> None:
    """Password then TOTP. Advances the clock one step so codes are never replays."""
    clock.advance(timedelta(seconds=STEP))
    response = client.post(
        "/api/auth/login", json={"email": "owner@example.com", "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    response = client.post(
        "/api/auth/totp/verify", json={"code": totp_code(clock)}, headers=csrf(client)
    )
    assert response.status_code == 200, response.text
