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


def _category(client: TestClient, name: str) -> str:
    category_id: str = next(
        c["id"] for c in client.get("/api/categories").json() if c["name"] == name
    )
    return category_id


def _account(client: TestClient, **changes: Any) -> str:
    body = {
        "name": "Compte courant",
        "institution_name": "SG",
        "type": "checking",
        "visibility": "shared",
        "opening_balance": "0",
        "opening_date": "2026-03-01",
        **changes,
    }
    account_id: str = client.post("/api/accounts", json=body, headers=csrf(client)).json()["id"]
    return account_id


def _import(client: TestClient, account_id: str) -> None:
    files = {"file": ("export.csv", CHECKING_CSV, "text/csv")}
    assert (
        client.post(
            f"/api/accounts/{account_id}/imports", files=files, headers=csrf(client)
        ).status_code
        == 201
    )


def _rule(client: TestClient, **body: Any) -> Any:
    return client.post("/api/rules", json=body, headers=csrf(client))


def _in(client: TestClient, category_id: str) -> list[str]:
    items = client.get("/api/transactions", params={"category_id": category_id}).json()["items"]
    return [t["label"] for t in items]


def test_create_and_list_rules_in_priority_order(owner_client: TestClient) -> None:
    bakery = _category(owner_client, "Bakery and coffee")
    first = _rule(owner_client, category_id=bakery, label_contains="boulangerie")
    second = _rule(owner_client, category_id=bakery, label_contains="cafe")

    assert first.status_code == 201
    rules = owner_client.get("/api/rules").json()
    assert [r["label_contains"] for r in rules] == ["boulangerie", "cafe"]
    assert rules[0]["category_name"] == "Bakery and coffee"
    assert rules[0]["priority"] < second.json()["priority"]


@pytest.mark.parametrize(
    "conditions",
    [{}, {"label_contains": "  "}, {"amount_min": "10", "amount_max": "5"}, {"amount_min": "-1"}],
)
def test_invalid_rules_are_rejected(owner_client: TestClient, conditions: dict[str, str]) -> None:
    bakery = _category(owner_client, "Bakery and coffee")
    assert _rule(owner_client, category_id=bakery, **conditions).status_code == 422


def test_rules_need_a_known_category_and_account(owner_client: TestClient) -> None:
    unknown = "01a11164-9486-75bf-a85a-01b66cd50ebe"
    assert _rule(owner_client, category_id=unknown, label_contains="x").status_code == 422
    bakery = _category(owner_client, "Bakery and coffee")
    assert _rule(owner_client, category_id=bakery, account_id=unknown).status_code == 422


def test_imports_apply_the_rules(owner_client: TestClient) -> None:
    bakery = _category(owner_client, "Bakery and coffee")
    salary = _category(owner_client, "Salary")
    _rule(owner_client, category_id=bakery, label_contains="cafe de la gare")
    _rule(owner_client, category_id=salary, label_contains="salaire")

    _import(owner_client, _account(owner_client))

    assert len(_in(owner_client, bakery)) == 2
    assert len(_in(owner_client, salary)) == 1
    assert (
        owner_client.get("/api/transactions", params={"uncategorised": True}).json()["total"] == 11
    )


def test_manual_entries_apply_the_rules(owner_client: TestClient) -> None:
    groceries = _category(owner_client, "Groceries")
    _rule(owner_client, category_id=groceries, label_contains="market")
    account = _account(owner_client)

    created = owner_client.post(
        "/api/transactions",
        json={
            "account_id": account,
            "booked_on": "2026-03-20",
            "amount": "-12.50",
            "label": "Sunday market",
        },
        headers=csrf(owner_client),
    ).json()

    assert created["category_id"] == groceries


def test_rules_can_be_applied_to_past_transactions(owner_client: TestClient) -> None:
    _import(owner_client, _account(owner_client))
    bakery = _category(owner_client, "Bakery and coffee")
    restaurants = _category(owner_client, "Restaurants")
    first_cafe = next(
        t for t in owner_client.get("/api/transactions").json()["items"] if "CAFE" in t["label"]
    )
    owner_client.patch(
        f"/api/transactions/{first_cafe['id']}",
        json={"category_id": restaurants},
        headers=csrf(owner_client),
    )
    _rule(owner_client, category_id=bakery, label_contains="cafe")

    applied = owner_client.post("/api/rules/apply", json={}, headers=csrf(owner_client))
    assert applied.json() == {"updated": 1}  # the hand-categorised one is kept by default

    forced = owner_client.post(
        "/api/rules/apply", json={"only_uncategorised": False}, headers=csrf(owner_client)
    )
    assert forced.json() == {"updated": 1}
    assert len(_in(owner_client, bakery)) == 2


def test_preview_counts_what_a_rule_would_catch(owner_client: TestClient) -> None:
    _import(owner_client, _account(owner_client))
    bakery = _category(owner_client, "Bakery and coffee")

    preview = owner_client.post(
        "/api/rules/preview",
        json={"category_id": bakery, "label_contains": "carte"},
        headers=csrf(owner_client),
    ).json()

    assert preview["matching"] == 5
    assert preview["uncategorised"] == 5
    assert len(preview["examples"]) == 5
    assert all("CARTE" in e["label"] for e in preview["examples"])


def test_edit_and_delete_a_rule(owner_client: TestClient) -> None:
    bakery = _category(owner_client, "Bakery and coffee")
    rule = _rule(owner_client, category_id=bakery, label_contains="cafe").json()

    edited = owner_client.patch(
        f"/api/rules/{rule['id']}",
        json={"label_contains": None, "amount_max": "5"},
        headers=csrf(owner_client),
    )
    assert edited.status_code == 200
    assert edited.json()["label_contains"] is None
    assert edited.json()["amount_max"] == "5.00"
    emptied = owner_client.patch(
        f"/api/rules/{rule['id']}", json={"amount_max": None}, headers=csrf(owner_client)
    )
    assert emptied.status_code == 422

    assert (
        owner_client.delete(f"/api/rules/{rule['id']}", headers=csrf(owner_client)).status_code
        == 204
    )
    assert owner_client.get("/api/rules").json() == []


def test_deleting_a_category_deletes_its_rules(owner_client: TestClient) -> None:
    owner_client.post(
        "/api/categories", json={"name": "Pets", "kind": "expense"}, headers=csrf(owner_client)
    )
    pets = _category(owner_client, "Pets")
    _rule(owner_client, category_id=pets, label_contains="vet")
    owner_client.delete(f"/api/categories/{pets}", headers=csrf(owner_client))
    assert owner_client.get("/api/rules").json() == []


@pytest.mark.usefixtures("member")
def test_applying_rules_leaves_what_the_member_cannot_see(client: TestClient, clock: Clock) -> None:
    log_in(client, clock)
    _import(client, _account(client, visibility="private"))

    log_in(client, clock, "member@example.com")
    bakery = _category(client, "Bakery and coffee")
    _rule(client, category_id=bakery, label_contains="cafe")
    assert client.post("/api/rules/apply", json={}, headers=csrf(client)).json() == {"updated": 0}


def test_rules_require_a_full_sign_in(client: TestClient) -> None:
    assert client.get("/api/rules").status_code == 401
