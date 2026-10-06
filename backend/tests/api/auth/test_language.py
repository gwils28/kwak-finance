import pytest
from fastapi.testclient import TestClient
from kwak_api.models import User

from tests.api.conftest import Clock, csrf, log_in


@pytest.fixture
def owner_client(client: TestClient, clock: Clock, owner: User) -> TestClient:
    log_in(client, clock)
    return client


def test_no_language_is_chosen_at_first(owner_client: TestClient) -> None:
    assert owner_client.get("/api/auth/me").json()["language"] is None


def test_the_language_is_saved_with_the_account(owner_client: TestClient, clock: Clock) -> None:
    response = owner_client.patch(
        "/api/auth/me", json={"language": "fr"}, headers=csrf(owner_client)
    )
    assert response.status_code == 200
    assert response.json()["language"] == "fr"

    log_in(owner_client, clock)  # a new session, as on another device
    assert owner_client.get("/api/auth/me").json()["language"] == "fr"


def test_only_supported_languages_are_accepted(owner_client: TestClient) -> None:
    response = owner_client.patch(
        "/api/auth/me", json={"language": "de"}, headers=csrf(owner_client)
    )
    assert response.status_code == 422


def test_changing_the_language_needs_the_csrf_token(owner_client: TestClient) -> None:
    assert owner_client.patch("/api/auth/me", json={"language": "fr"}).status_code == 403
