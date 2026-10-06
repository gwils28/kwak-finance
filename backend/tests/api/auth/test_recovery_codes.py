import base64

import pytest
from fastapi.testclient import TestClient
from kwak_api.models import RecoveryCode, User
from kwak_core.totp import STEP, hotp
from sqlalchemy import select
from sqlalchemy.orm import Session

from tests.api.conftest import PASSWORD, Clock, csrf, log_in


def _password_step(client: TestClient) -> None:
    client.cookies.clear()
    response = client.post(
        "/api/auth/login", json={"email": "owner@example.com", "password": PASSWORD}
    )
    assert response.status_code == 200


def _use(client: TestClient, code: str) -> int:
    return client.post("/api/auth/recovery", json={"code": code}, headers=csrf(client)).status_code


def _regenerate(client: TestClient, password: str = PASSWORD) -> list[str]:
    response = client.post(
        "/api/auth/recovery-codes", json={"password": password}, headers=csrf(client)
    )
    assert response.status_code == 200, response.text
    codes: list[str] = response.json()["recovery_codes"]
    return codes


@pytest.fixture
def codes(client: TestClient, clock: Clock, owner: User) -> list[str]:
    log_in(client, clock)
    return _regenerate(client)


@pytest.mark.usefixtures("unenrolled_owner")
def test_confirming_totp_hands_out_ten_codes_stored_hashed(
    client: TestClient, clock: Clock, session: Session
) -> None:
    _password_step(client)
    secret = client.post("/api/auth/totp/setup", headers=csrf(client)).json()["secret"]
    code = hotp(base64.b32decode(secret), int(clock.now.timestamp()) // STEP)

    response = client.post("/api/auth/totp/confirm", json={"code": code}, headers=csrf(client))

    assert response.status_code == 200
    assert response.json()["user"]["email"] == "owner@example.com"
    handed_out = response.json()["recovery_codes"]
    assert len(handed_out) == 10
    stored = session.scalars(select(RecoveryCode.code_hash)).all()
    assert len(stored) == 10
    assert not any(c.replace("-", "") in h for c in handed_out for h in stored)


def test_a_recovery_code_replaces_the_totp_code_once(client: TestClient, codes: list[str]) -> None:
    _password_step(client)
    assert _use(client, codes[0].upper().replace("-", " ")) == 200
    assert client.get("/api/auth/me").status_code == 200

    _password_step(client)
    assert _use(client, codes[0]) == 400
    assert _use(client, codes[1]) == 200


def test_a_wrong_recovery_code_is_rejected(client: TestClient, codes: list[str]) -> None:
    _password_step(client)
    assert _use(client, "aaaa-aaaa-aaaa-aaaa") == 400
    assert _use(client, "not a code") == 400
    assert client.get("/api/auth/me").status_code == 401


def test_recovery_attempts_count_towards_the_second_factor_limit(
    client: TestClient, codes: list[str]
) -> None:
    _password_step(client)
    for _ in range(5):
        assert _use(client, "aaaa-aaaa-aaaa-aaaa") == 400
    assert _use(client, codes[0]) == 429


@pytest.mark.usefixtures("unenrolled_owner")
def test_recovery_is_refused_before_enrollment(client: TestClient) -> None:
    _password_step(client)
    assert _use(client, "aaaa-aaaa-aaaa-aaaa") == 409


def test_regenerating_replaces_every_code(client: TestClient, codes: list[str]) -> None:
    fresh = _regenerate(client)
    assert set(fresh).isdisjoint(codes)

    _password_step(client)
    assert _use(client, codes[2]) == 400
    assert _use(client, fresh[0]) == 200


def test_regenerating_requires_the_password(client: TestClient, codes: list[str]) -> None:
    response = client.post(
        "/api/auth/recovery-codes", json={"password": "wrong password!"}, headers=csrf(client)
    )
    assert response.status_code == 403
    _password_step(client)
    assert _use(client, codes[0]) == 200


@pytest.mark.usefixtures("owner")
def test_regenerating_requires_a_full_login(client: TestClient) -> None:
    _password_step(client)
    response = client.post(
        "/api/auth/recovery-codes", json={"password": PASSWORD}, headers=csrf(client)
    )
    assert response.status_code == 401
