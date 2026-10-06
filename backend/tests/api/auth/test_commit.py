from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from kwak_api.db import Base
from kwak_api.main import create_app
from kwak_api.services.households import create_household
from kwak_api.settings import Settings
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from tests.api.conftest import PASSWORD


@pytest.fixture
def committed_owner(engine: Engine) -> Iterator[None]:
    """Unlike the other tests, this one commits: it cleans up after itself."""
    with Session(engine) as session:
        create_household(
            session,
            household_name="Home",
            email="owner@example.com",
            display_name="O",
            password=PASSWORD,
        )
        session.commit()
    yield
    with engine.begin() as conn:
        tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
        conn.execute(text(f"TRUNCATE {tables}"))


@pytest.mark.usefixtures("committed_owner")
def test_sessions_are_committed_by_the_real_request_scope(database_url: str) -> None:
    app = create_app(Settings(database_url=database_url))
    with TestClient(app, base_url="https://testserver") as client:
        login = client.post(
            "/api/auth/login", json={"email": "owner@example.com", "password": PASSWORD}
        )
        assert login.status_code == 200
        # "second factor required", not "not authenticated": the session row was committed.
        assert client.get("/api/auth/me").json() == {"detail": "second factor required"}


@pytest.mark.usefixtures("committed_owner")
def test_failed_logins_are_kept_although_the_request_fails(database_url: str) -> None:
    app = create_app(Settings(database_url=database_url))
    with TestClient(app, base_url="https://testserver") as client:
        for _ in range(5):
            wrong = {"email": "owner@example.com", "password": "wrong password!"}
            assert client.post("/api/auth/login", json=wrong).status_code == 401
        right = {"email": "owner@example.com", "password": PASSWORD}
        assert client.post("/api/auth/login", json=right).status_code == 429
