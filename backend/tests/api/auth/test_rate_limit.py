from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from .conftest import PASSWORD, Clock, csrf, totp_code


def _login(client: TestClient, email: str = "owner@example.com", password: str = PASSWORD) -> int:
    return client.post("/api/auth/login", json={"email": email, "password": password}).status_code


def _fail_logins(client: TestClient, times: int, email: str = "owner@example.com") -> None:
    for _ in range(times):
        assert _login(client, email, "wrong password!") == 401


@pytest.mark.usefixtures("owner")
def test_five_wrong_passwords_block_the_account_for_15_minutes(
    client: TestClient, clock: Clock
) -> None:
    _fail_logins(client, 5)

    response = client.post(
        "/api/auth/login", json={"email": "owner@example.com", "password": PASSWORD}
    )
    assert response.status_code == 429
    assert response.headers["Retry-After"] == str(15 * 60)

    clock.advance(timedelta(minutes=15))
    assert _login(client) == 200


@pytest.mark.usefixtures("owner")
def test_the_limit_ignores_email_case(client: TestClient) -> None:
    _fail_logins(client, 5, "OWNER@example.com")
    assert _login(client) == 429


@pytest.mark.usefixtures("owner")
def test_unknown_emails_are_limited_the_same_way(client: TestClient) -> None:
    _fail_logins(client, 5, "nobody@example.com")
    assert _login(client, "nobody@example.com") == 429


@pytest.mark.usefixtures("owner")
def test_a_successful_login_resets_the_account_counter(client: TestClient, clock: Clock) -> None:
    _fail_logins(client, 4)
    assert _login(client) == 200
    _fail_logins(client, 4)
    assert _login(client) == 200


@pytest.mark.usefixtures("owner")
def test_spread_out_failures_hit_the_daily_limit(client: TestClient, clock: Clock) -> None:
    for _ in range(4):
        _fail_logins(client, 5)
        clock.advance(timedelta(minutes=15))
    assert _login(client) == 429


@pytest.mark.usefixtures("owner")
def test_one_address_trying_many_accounts_is_blocked(client: TestClient) -> None:
    for i in range(5):
        _fail_logins(client, 4, f"user{i}@example.com")
    assert _login(client) == 429


@pytest.mark.usefixtures("owner")
def test_five_wrong_totp_codes_block_the_second_factor(client: TestClient, clock: Clock) -> None:
    assert _login(client) == 200
    for _ in range(5):
        response = client.post(
            "/api/auth/totp/verify", json={"code": "000000"}, headers=csrf(client)
        )
        assert response.status_code == 400

    right = client.post(
        "/api/auth/totp/verify", json={"code": totp_code(clock)}, headers=csrf(client)
    )
    assert right.status_code == 429
    assert client.get("/api/auth/me").status_code == 401
