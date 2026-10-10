from typing import Any

import pytest
from fastapi.testclient import TestClient
from kwak_api.models import User

from tests.api.budget.test_budget import _account, _target
from tests.api.categories.test_categories import _by_name, _categories, _create
from tests.api.conftest import Clock, csrf, log_in

URL = "/api/categories/restore"


@pytest.fixture
def owner_client(client: TestClient, clock: Clock, owner: User) -> TestClient:
    log_in(client, clock)
    return client


def _spend(client: TestClient, account: str, category_id: str, amount: str = "-10.00") -> str:
    created = client.post(
        "/api/transactions",
        json={"account_id": account, "booked_on": "2026-03-10", "amount": amount, "label": "x"},
        headers=csrf(client),
    ).json()
    client.post(
        "/api/transactions/categorise",
        json={"transaction_ids": [created["id"]], "category_id": category_id},
        headers=csrf(client),
    )
    transaction_id: str = created["id"]
    return transaction_id


def _category_of(client: TestClient, transaction_id: str) -> Any:
    items = client.get("/api/transactions").json()["items"]
    return next(t for t in items if t["id"] == transaction_id)["category_id"]


def _rule(client: TestClient, category_id: str, text: str) -> None:
    response = client.post(
        "/api/rules",
        json={"category_id": category_id, "label_contains": text},
        headers=csrf(client),
    )
    assert response.status_code == 201, response.text


def _french(client: TestClient) -> None:
    client.patch("/api/auth/me", json={"language": "fr"}, headers=csrf(client))


@pytest.fixture
def messy(owner_client: TestClient) -> dict[str, str]:
    """Categories created by hand while testing, with transactions, a rule and a plan target."""
    account = _account(owner_client, opening_date="2026-01-01")
    pets = _create(owner_client, name="Pets").json()
    vet = _create(owner_client, name="Vet", parent_id=pets["id"]).json()
    food = _by_name(owner_client, "Food")
    mine = _create(owner_client, name="Courses", parent_id=food["id"]).json()
    _rule(owner_client, vet["id"], "VETO")
    _target(owner_client, "Vet", "50.00")
    return {
        "vet_spend": _spend(owner_client, account, vet["id"]),
        "courses_spend": _spend(owner_client, account, mine["id"]),
        "groceries_spend": _spend(owner_client, account, _by_name(owner_client, "Groceries")["id"]),
    }


def test_the_preview_says_what_will_go_and_changes_nothing(
    owner_client: TestClient, messy: dict[str, str]
) -> None:
    before = _categories(owner_client)
    _french(owner_client)
    response = owner_client.get(URL)

    assert response.status_code == 200, response.text
    preview = response.json()
    assert preview["language"] == "fr"
    assert sorted(preview["deleted"]) == ["Pets", "Vet"]
    assert {"from": "Food", "to": "Alimentation"} in preview["renamed"]
    # The "Courses" made by hand is the French Groceries: the seeded one merges into it.
    assert preview["merged"] == [{"from": "Groceries", "to": "Courses"}]
    assert preview["created"] == []
    assert (
        preview["transactions_to_categorise"],
        preview["rules_deleted"],
        preview["plan_targets_deleted"],
    ) == (1, 1, 1)
    assert _categories(owner_client) == before


def test_restoring_keeps_what_matches_the_defaults_and_deletes_the_rest(
    owner_client: TestClient, messy: dict[str, str]
) -> None:
    _french(owner_client)
    response = owner_client.post(URL, headers=csrf(owner_client))

    assert response.status_code == 200, response.text
    names = {c["name"] for c in _categories(owner_client)}
    assert {"Alimentation", "Courses", "Logement", "Revenus", "Salaire"} <= names
    assert not names & {"Pets", "Vet", "Food", "Groceries"}
    courses = _by_name(owner_client, "Courses")
    assert courses["parent_id"] == _by_name(owner_client, "Alimentation")["id"]
    # Both grocery transactions end up in the one "Courses"; the vet's goes back to categorise.
    assert _category_of(owner_client, messy["courses_spend"]) == courses["id"]
    assert _category_of(owner_client, messy["groceries_spend"]) == courses["id"]
    assert _category_of(owner_client, messy["vet_spend"]) is None
    assert owner_client.get("/api/rules").json() == []
    assert owner_client.get(URL).json()["deleted"] == []  # nothing left to restore


def test_a_merge_keeps_the_plan_targets(owner_client: TestClient, clock: Clock) -> None:
    log_in(owner_client, clock)
    food = _by_name(owner_client, "Food")
    _create(owner_client, name="courses", parent_id=food["id"])
    _target(owner_client, "Groceries", "300.00")
    _french(owner_client)
    owner_client.post(URL, headers=csrf(owner_client))

    (plan,) = owner_client.get("/api/budget/plans").json()
    assert plan["targets"] == [
        {"category_id": _by_name(owner_client, "Courses")["id"], "amount": "300.00"}
    ]


def test_only_the_owner_restores(
    client: TestClient, clock: Clock, owner: User, member: User
) -> None:
    log_in(client, clock, "member@example.com")
    assert client.get(URL).status_code == 403
    assert client.post(URL, headers=csrf(client)).status_code == 403
