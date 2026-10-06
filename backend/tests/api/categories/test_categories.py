from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from kwak_api.models import User

from tests.api.conftest import Clock, csrf, log_in

CHECKING_CSV = (
    Path(__file__).parents[2] / "fixtures" / "import" / "societe_generale" / "checking.csv"
).read_bytes()


@pytest.fixture
def owner_client(client: TestClient, clock: Clock, owner: User) -> TestClient:
    log_in(client, clock)
    return client


def _categories(client: TestClient) -> list[dict[str, Any]]:
    response = client.get("/api/categories")
    assert response.status_code == 200
    categories: list[dict[str, Any]] = response.json()
    return categories


def _by_name(client: TestClient, name: str) -> dict[str, Any]:
    return next(c for c in _categories(client) if c["name"] == name)


def _create(client: TestClient, **body: Any) -> Any:
    return client.post("/api/categories", json=body, headers=csrf(client))


def _patch(client: TestClient, category_id: str, **body: Any) -> Any:
    return client.patch(f"/api/categories/{category_id}", json=body, headers=csrf(client))


def _imported_transactions(client: TestClient) -> list[dict[str, Any]]:
    account = client.post(
        "/api/accounts",
        json={
            "name": "Compte courant",
            "institution_name": "SG",
            "type": "checking",
            "visibility": "shared",
            "opening_balance": "0",
            "opening_date": "2026-03-01",
        },
        headers=csrf(client),
    ).json()["id"]
    files = {"file": ("export.csv", CHECKING_CSV, "text/csv")}
    client.post(f"/api/accounts/{account}/imports", files=files, headers=csrf(client))
    items: list[dict[str, Any]] = client.get("/api/transactions").json()["items"]
    return items


def test_a_new_household_starts_with_the_default_tree(owner_client: TestClient) -> None:
    categories = _categories(owner_client)
    food = next(c for c in categories if c["name"] == "Food")
    groceries = next(c for c in categories if c["name"] == "Groceries")

    assert food["parent_id"] is None
    assert food["kind"] == "expense"
    assert groceries["parent_id"] == food["id"]
    assert _by_name(owner_client, "Salary")["kind"] == "income"
    # Parents first, each followed by its children.
    assert categories.index(food) < categories.index(groceries)


def test_create_a_category_and_a_subcategory(owner_client: TestClient) -> None:
    pets = _create(owner_client, name="Pets", kind="expense")
    assert pets.status_code == 201
    vet = _create(owner_client, name="Vet", parent_id=pets.json()["id"], kind="income")

    assert vet.status_code == 201
    assert vet.json()["kind"] == "expense"  # inherited from the parent


def test_sibling_names_are_unique_whatever_the_case(owner_client: TestClient) -> None:
    food = _by_name(owner_client, "Food")["id"]
    assert _create(owner_client, name="groceries", parent_id=food).status_code == 409
    assert _create(owner_client, name="FOOD", kind="expense").status_code == 409
    transport = _by_name(owner_client, "Transport")["id"]
    assert _create(owner_client, name="Groceries", parent_id=transport).status_code == 201


def test_the_tree_keeps_two_levels(owner_client: TestClient) -> None:
    food = _by_name(owner_client, "Food")["id"]
    groceries = _by_name(owner_client, "Groceries")["id"]
    transport = _by_name(owner_client, "Transport")["id"]
    salary_parent = _by_name(owner_client, "Income")["id"]

    assert _create(owner_client, name="Organic", parent_id=groceries).status_code == 422
    assert _patch(owner_client, food, parent_id=transport).status_code == 422
    assert _patch(owner_client, groceries, parent_id=salary_parent).status_code == 422
    moved = _patch(owner_client, groceries, parent_id=transport)
    assert moved.status_code == 200
    assert moved.json()["parent_id"] == transport


def test_rename_a_category(owner_client: TestClient) -> None:
    food = _by_name(owner_client, "Food")["id"]
    response = _patch(owner_client, food, name="Food and drinks")
    assert response.status_code == 200
    assert response.json()["name"] == "Food and drinks"


def test_a_parent_with_subcategories_cannot_be_deleted(owner_client: TestClient) -> None:
    food = _by_name(owner_client, "Food")["id"]
    assert (
        owner_client.delete(f"/api/categories/{food}", headers=csrf(owner_client)).status_code
        == 409
    )


def test_deleting_a_category_uncategorises_its_transactions(owner_client: TestClient) -> None:
    transactions = _imported_transactions(owner_client)
    bakery = _by_name(owner_client, "Bakery and coffee")["id"]
    owner_client.patch(
        f"/api/transactions/{transactions[0]['id']}",
        json={"category_id": bakery},
        headers=csrf(owner_client),
    )

    assert (
        owner_client.delete(f"/api/categories/{bakery}", headers=csrf(owner_client)).status_code
        == 204
    )

    assert (
        owner_client.get("/api/transactions", params={"uncategorised": True}).json()["total"] == 14
    )


def test_imported_transactions_can_be_categorised(owner_client: TestClient) -> None:
    transaction = _imported_transactions(owner_client)[0]
    bakery = _by_name(owner_client, "Bakery and coffee")

    response = owner_client.patch(
        f"/api/transactions/{transaction['id']}",
        json={"category_id": bakery["id"]},
        headers=csrf(owner_client),
    )
    assert response.status_code == 200
    assert response.json()["category_id"] == bakery["id"]
    assert response.json()["category_name"] == "Bakery and coffee"

    cleared = owner_client.patch(
        f"/api/transactions/{transaction['id']}",
        json={"category_id": None},
        headers=csrf(owner_client),
    )
    assert cleared.json()["category_id"] is None


def test_imported_amounts_stay_read_only_even_with_a_category(owner_client: TestClient) -> None:
    transaction = _imported_transactions(owner_client)[0]
    bakery = _by_name(owner_client, "Bakery and coffee")["id"]
    response = owner_client.patch(
        f"/api/transactions/{transaction['id']}",
        json={"category_id": bakery, "amount": "-1.00"},
        headers=csrf(owner_client),
    )
    assert response.status_code == 409


def test_an_unknown_category_is_rejected(owner_client: TestClient) -> None:
    transaction = _imported_transactions(owner_client)[0]
    response = owner_client.patch(
        f"/api/transactions/{transaction['id']}",
        json={"category_id": "01a11164-9486-75bf-a85a-01b66cd50ebe"},
        headers=csrf(owner_client),
    )
    assert response.status_code == 422


def test_bulk_categorisation_and_filters(owner_client: TestClient) -> None:
    transactions = _imported_transactions(owner_client)
    cafe = [t["id"] for t in transactions if "CAFE" in t["label"]]
    bakery = _by_name(owner_client, "Bakery and coffee")["id"]

    response = owner_client.post(
        "/api/transactions/categorise",
        json={"transaction_ids": cafe, "category_id": bakery},
        headers=csrf(owner_client),
    )

    assert response.status_code == 200
    assert response.json() == {"updated": 2}
    assert (
        owner_client.get("/api/transactions", params={"category_id": bakery}).json()["total"] == 2
    )
    assert (
        owner_client.get("/api/transactions", params={"uncategorised": True}).json()["total"] == 12
    )


@pytest.mark.usefixtures("member")
def test_bulk_categorisation_skips_what_the_member_cannot_see(
    client: TestClient, clock: Clock
) -> None:
    log_in(client, clock)
    transactions = _imported_transactions(client)
    client.patch(
        f"/api/accounts/{transactions[0]['account_id']}",
        json={"visibility": "private"},
        headers=csrf(client),
    )
    bakery = _by_name(client, "Bakery and coffee")["id"]

    log_in(client, clock, "member@example.com")
    response = client.post(
        "/api/transactions/categorise",
        json={"transaction_ids": [t["id"] for t in transactions], "category_id": bakery},
        headers=csrf(client),
    )
    assert response.json() == {"updated": 0}


def test_categories_require_a_full_sign_in(client: TestClient) -> None:
    assert client.get("/api/categories").status_code == 401
