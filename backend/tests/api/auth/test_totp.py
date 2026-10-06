import base64
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from kwak_api.models import User
from kwak_core.totp import STEP, hotp
from sqlalchemy.orm import Session

from .conftest import PASSWORD, Clock, csrf, totp_code


def _password_step(client: TestClient) -> str:
    response = client.post(
        "/api/auth/login", json={"email": "owner@example.com", "password": PASSWORD}
    )
    assert response.status_code == 200
    next_step: str = response.json()["next_step"]
    return next_step


def _decode(secret_b32: str) -> bytes:
    return base64.b32decode(secret_b32 + "=" * (-len(secret_b32) % 8))


def _code_for(secret_b32: str, clock: Clock) -> str:
    return hotp(_decode(secret_b32), int(clock.now.timestamp()) // STEP)


@pytest.mark.usefixtures("unenrolled_owner")
def test_first_login_enrolls_totp(client: TestClient, clock: Clock, session: Session) -> None:
    assert _password_step(client) == "totp_setup"

    setup = client.post("/api/auth/totp/setup", headers=csrf(client))
    assert setup.status_code == 200
    secret = setup.json()["secret"]
    assert setup.json()["uri"].startswith("otpauth://totp/Kwak%20Finance:owner%40example.com?")
    assert client.get("/api/auth/me").status_code == 401

    confirm = client.post(
        "/api/auth/totp/confirm", json={"code": _code_for(secret, clock)}, headers=csrf(client)
    )
    assert confirm.status_code == 200
    assert client.get("/api/auth/me").status_code == 200


def test_the_secret_is_stored_encrypted(client: TestClient, unenrolled_owner: User) -> None:
    _password_step(client)
    secret = client.post("/api/auth/totp/setup", headers=csrf(client)).json()["secret"]
    assert unenrolled_owner.totp_secret_enc is not None
    assert _decode(secret) not in unenrolled_owner.totp_secret_enc


@pytest.mark.usefixtures("unenrolled_owner")
def test_confirm_rejects_a_wrong_code(client: TestClient) -> None:
    _password_step(client)
    client.post("/api/auth/totp/setup", headers=csrf(client))
    response = client.post("/api/auth/totp/confirm", json={"code": "000000"}, headers=csrf(client))
    assert response.status_code == 400
    assert client.get("/api/auth/me").status_code == 401


@pytest.mark.usefixtures("unenrolled_owner")
def test_confirm_needs_a_setup_first(client: TestClient) -> None:
    _password_step(client)
    response = client.post("/api/auth/totp/confirm", json={"code": "000000"}, headers=csrf(client))
    assert response.status_code == 409


@pytest.mark.usefixtures("owner")
def test_an_enrolled_user_cannot_set_up_again(client: TestClient) -> None:
    """Otherwise a stolen password alone would replace the second factor."""
    assert _password_step(client) == "totp_verify"
    assert client.post("/api/auth/totp/setup", headers=csrf(client)).status_code == 409


@pytest.mark.usefixtures("owner")
def test_verify_accepts_the_current_code(client: TestClient, clock: Clock) -> None:
    _password_step(client)
    response = client.post(
        "/api/auth/totp/verify", json={"code": totp_code(clock)}, headers=csrf(client)
    )
    assert response.status_code == 200
    assert response.json()["email"] == "owner@example.com"
    assert client.get("/api/auth/me").status_code == 200


@pytest.mark.usefixtures("owner")
def test_verify_rejects_a_wrong_code(client: TestClient) -> None:
    _password_step(client)
    response = client.post("/api/auth/totp/verify", json={"code": "000000"}, headers=csrf(client))
    assert response.status_code == 400
    assert response.json() == {"detail": "invalid code"}


@pytest.mark.usefixtures("owner")
def test_a_code_cannot_be_used_twice(client: TestClient, clock: Clock) -> None:
    code = totp_code(clock)
    _password_step(client)
    assert (
        client.post("/api/auth/totp/verify", json={"code": code}, headers=csrf(client)).status_code
        == 200
    )

    client.cookies.clear()
    clock.advance(timedelta(seconds=1))
    _password_step(client)
    assert (
        client.post("/api/auth/totp/verify", json={"code": code}, headers=csrf(client)).status_code
        == 400
    )


@pytest.mark.usefixtures("unenrolled_owner")
def test_verify_is_refused_before_enrollment(client: TestClient) -> None:
    _password_step(client)
    assert (
        client.post(
            "/api/auth/totp/verify", json={"code": "000000"}, headers=csrf(client)
        ).status_code
        == 409
    )


@pytest.mark.usefixtures("owner")
def test_totp_endpoints_require_the_csrf_token(client: TestClient, clock: Clock) -> None:
    _password_step(client)
    assert client.post("/api/auth/totp/verify", json={"code": totp_code(clock)}).status_code == 403


def test_totp_endpoints_require_the_password_step(client: TestClient) -> None:
    assert client.post("/api/auth/totp/setup").status_code == 401
