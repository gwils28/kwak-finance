from datetime import timedelta

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from kwak_api.models import User, UserSession
from sqlalchemy import select
from sqlalchemy.orm import Session

from .conftest import PASSWORD, Clock, csrf, log_in

INVALID = {"detail": "invalid email or password"}


def _password_step(
    client: TestClient, email: str = "owner@example.com", password: str = PASSWORD
) -> int:
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    return response.status_code


@pytest.mark.usefixtures("owner")
def test_login_sets_a_hardened_session_cookie(client: TestClient, session: Session) -> None:
    response = client.post(
        "/api/auth/login", json={"email": "Owner@Example.com", "password": PASSWORD}
    )

    assert response.status_code == 200
    assert response.json()["user"]["email"] == "owner@example.com"
    assert response.json()["user"]["role"] == "owner"
    cookies = {c.split("=", 1)[0]: c.lower() for c in response.headers.get_list("set-cookie")}
    assert all(flag in cookies["kwak_session"] for flag in ("httponly", "secure", "samesite=lax"))
    assert "httponly" not in cookies["kwak_csrf"]
    stored = session.scalars(select(UserSession.token_hash)).one()
    assert client.cookies["kwak_session"] not in stored


@pytest.mark.usefixtures("owner")
@pytest.mark.parametrize(
    ("email", "password"),
    [("owner@example.com", "wrong password!"), ("nobody@example.com", PASSWORD)],
)
def test_login_failure_does_not_say_which_part_was_wrong(
    client: TestClient, email: str, password: str
) -> None:
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 401
    assert response.json() == INVALID
    assert "kwak_session" not in client.cookies


def test_inactive_user_cannot_log_in(client: TestClient, owner: User, session: Session) -> None:
    owner.is_active = False
    session.flush()
    assert _password_step(client) == 401


def test_login_upgrades_a_weak_password_hash(
    client: TestClient, owner: User, session: Session
) -> None:
    owner.password_hash = PasswordHasher(time_cost=1, memory_cost=8, parallelism=1).hash(PASSWORD)
    weak = owner.password_hash
    session.flush()

    assert _password_step(client) == 200
    session.refresh(owner)
    assert owner.password_hash != weak


@pytest.mark.usefixtures("owner")
def test_me_requires_both_factors(client: TestClient, clock: Clock) -> None:
    assert client.get("/api/auth/me").status_code == 401
    _password_step(client)
    response = client.get("/api/auth/me")
    assert response.status_code == 401
    assert response.json() == {"detail": "second factor required"}

    log_in(client, clock)
    response = client.get("/api/auth/me")
    assert response.status_code == 200
    assert response.json()["display_name"] == "Owner"


@pytest.mark.usefixtures("owner")
def test_logout_requires_the_csrf_token(client: TestClient, clock: Clock) -> None:
    log_in(client, clock)
    assert client.post("/api/auth/logout").status_code == 403
    assert client.post("/api/auth/logout", headers={"X-CSRF-Token": "forged"}).status_code == 403
    assert client.get("/api/auth/me").status_code == 200


@pytest.mark.usefixtures("owner")
def test_logout_revokes_the_session(client: TestClient, clock: Clock, session: Session) -> None:
    log_in(client, clock)
    token = client.cookies["kwak_session"]

    assert client.post("/api/auth/logout", headers=csrf(client)).status_code == 204
    assert session.scalars(select(UserSession.revoked_at)).one() is not None
    # Replaying the old cookie must not work.
    assert (
        client.get("/api/auth/me", headers={"Cookie": f"kwak_session={token}"}).status_code == 401
    )


@pytest.mark.usefixtures("owner")
def test_a_half_logged_in_session_can_log_out(client: TestClient) -> None:
    _password_step(client)
    assert client.post("/api/auth/logout", headers=csrf(client)).status_code == 204


@pytest.mark.usefixtures("owner")
def test_an_idle_session_expires(client: TestClient, clock: Clock) -> None:
    log_in(client, clock)
    clock.advance(timedelta(days=7))
    assert client.get("/api/auth/me").status_code == 401


@pytest.mark.usefixtures("owner")
def test_activity_keeps_the_session_alive_until_the_absolute_limit(
    client: TestClient, clock: Clock
) -> None:
    log_in(client, clock)
    for _ in range(4):
        clock.advance(timedelta(days=6))
        assert client.get("/api/auth/me").status_code == 200
    clock.advance(timedelta(days=6))  # 30 days after login
    assert client.get("/api/auth/me").status_code == 401
