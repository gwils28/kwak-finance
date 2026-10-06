from typing import Any

import pytest
from fastapi.testclient import TestClient
from kwak_api.models import User

from tests.api.conftest import Clock, csrf, log_in

CHECKING = {
    "name": "Compte courant",
    "institution_name": "Société Générale",
    "type": "checking",
    "visibility": "shared",
    "opening_balance": "1234.56",
    "opening_date": "2026-01-01",
}


@pytest.fixture
def owner_client(client: TestClient, clock: Clock, owner: User) -> TestClient:
    log_in(client, clock)
    return client


def _create(client: TestClient, **changes: Any) -> dict[str, Any]:
    response = client.post("/api/accounts", json={**CHECKING, **changes}, headers=csrf(client))
    assert response.status_code == 201, response.text
    account: dict[str, Any] = response.json()
    return account


def _patch(client: TestClient, account_id: str, **changes: Any) -> int:
    return client.patch(
        f"/api/accounts/{account_id}", json=changes, headers=csrf(client)
    ).status_code


def test_create_an_account(owner_client: TestClient) -> None:
    account = _create(owner_client)

    assert account["name"] == "Compte courant"
    assert account["institution"] == "Société Générale"
    assert account["type"] == "checking"
    assert account["opening_balance"] == "1234.56"
    assert account["opening_date"] == "2026-01-01"
    assert account["owner_name"] == "Owner"
    assert account["closed_on"] is None
    assert owner_client.get("/api/accounts").json() == [account]


def test_institutions_are_reused_whatever_the_case_or_spacing(owner_client: TestClient) -> None:
    first = _create(owner_client)
    second = _create(
        owner_client, name="Livret A", type="savings", institution_name=" société générale "
    )

    assert second["institution"] == first["institution"] == "Société Générale"
    assert owner_client.get("/api/institutions").json() == ["Société Générale"]


def test_account_names_are_unique_per_institution(owner_client: TestClient) -> None:
    _create(owner_client)
    duplicate = owner_client.post("/api/accounts", json=CHECKING, headers=csrf(owner_client))
    assert duplicate.status_code == 409
    _create(owner_client, institution_name="Fortuneo")


@pytest.mark.parametrize(
    "changes",
    [
        {"opening_balance": "12.345"},
        {"opening_balance": "abc"},
        {"type": "piggy_bank"},
        {"visibility": "public"},
        {"name": "   "},
        {"institution_name": ""},
    ],
)
def test_invalid_accounts_are_rejected(owner_client: TestClient, changes: dict[str, str]) -> None:
    response = owner_client.post(
        "/api/accounts", json={**CHECKING, **changes}, headers=csrf(owner_client)
    )
    assert response.status_code == 422


@pytest.mark.usefixtures("member")
def test_members_see_shared_accounts_and_their_own_only(client: TestClient, clock: Clock) -> None:
    log_in(client, clock)
    _create(client, name="Joint", visibility="shared")
    _create(client, name="Owner savings", type="savings", visibility="private")

    log_in(client, clock, "member@example.com")
    _create(client, name="Member private", visibility="private")

    names = [a["name"] for a in client.get("/api/accounts").json()]
    assert names == ["Joint", "Member private"]


@pytest.mark.usefixtures("member")
def test_a_private_account_of_someone_else_is_not_found(client: TestClient, clock: Clock) -> None:
    log_in(client, clock)
    private = _create(client, visibility="private")

    log_in(client, clock, "member@example.com")
    assert _patch(client, private["id"], name="Mine now") == 404


@pytest.mark.usefixtures("member")
def test_members_can_edit_a_shared_account_but_only_its_owner_changes_visibility(
    client: TestClient, clock: Clock
) -> None:
    log_in(client, clock)
    shared = _create(client)

    log_in(client, clock, "member@example.com")
    assert _patch(client, shared["id"], name="Joint account") == 200
    assert _patch(client, shared["id"], visibility="private") == 403


def test_edit_an_account(owner_client: TestClient) -> None:
    account = _create(owner_client)
    response = owner_client.patch(
        f"/api/accounts/{account['id']}",
        json={"name": "Main", "opening_balance": "-10", "institution_name": "SG"},
        headers=csrf(owner_client),
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Main"
    assert response.json()["opening_balance"] == "-10.00"
    assert response.json()["institution"] == "SG"


def test_closed_accounts_leave_the_default_list(owner_client: TestClient) -> None:
    account = _create(owner_client)

    assert _patch(owner_client, account["id"], closed_on="2026-06-30") == 200
    assert owner_client.get("/api/accounts").json() == []
    closed = owner_client.get("/api/accounts", params={"include_closed": True}).json()
    assert [a["closed_on"] for a in closed] == ["2026-06-30"]

    assert _patch(owner_client, account["id"], closed_on=None) == 200
    assert len(owner_client.get("/api/accounts").json()) == 1


def test_an_account_cannot_close_before_it_opened(owner_client: TestClient) -> None:
    account = _create(owner_client)
    assert _patch(owner_client, account["id"], closed_on="2025-12-31") == 422


def test_accounts_require_a_full_sign_in(client: TestClient) -> None:
    assert client.get("/api/accounts").status_code == 401


def test_account_name_uniqueness_ignores_case(owner_client: TestClient) -> None:
    _create(owner_client)
    _create(owner_client, name="Livret A", type="savings")
    duplicate = owner_client.post(
        "/api/accounts", json={**CHECKING, "name": "COMPTE COURANT"}, headers=csrf(owner_client)
    )
    assert duplicate.status_code == 409
