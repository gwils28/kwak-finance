from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from kwak_api.deps import get_db, get_now
from kwak_api.main import create_app
from kwak_api.models import User
from kwak_api.services.households import create_household
from sqlalchemy.orm import Session

PASSWORD = "correct horse battery"


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
    app = create_app()
    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_now] = lambda: clock.now
    # Session cookies are Secure: the client must speak https to send them back.
    with TestClient(app, base_url="https://testserver") as client:
        yield client


@pytest.fixture
def owner(session: Session) -> User:
    return create_household(
        session,
        household_name="Home",
        email="owner@example.com",
        display_name="Owner",
        password=PASSWORD,
    )
