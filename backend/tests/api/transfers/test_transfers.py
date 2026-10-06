from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from kwak_api.models import User

from tests.api.conftest import Clock, csrf, log_in

CHECKING_CSV = (
    Path(__file__).parents[2] / "fixtures" / "import" / "societe_generale" / "checking.csv"
).read_bytes()
MARCH = {"start": "2026-03", "end": "2026-03"}


@pytest.fixture
def owner_client(client: TestClient, clock: Clock, owner: User) -> TestClient:
    log_in(client, clock)
    return client


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


def _setup(client: TestClient, savings_visibility: str = "shared") -> tuple[str, str]:
    """Checking (the fixture, with a 150 € standing order) and a Livret A receiving it."""
    checking = _account(client)
    files = {"file": ("export.csv", CHECKING_CSV, "text/csv")}
    client.post(f"/api/accounts/{checking}/imports", files=files, headers=csrf(client))
    savings = _account(client, name="Livret A", type="savings", visibility=savings_visibility)
    client.post(
        "/api/transactions",
        json={
            "account_id": savings,
            "booked_on": "2026-03-11",
            "amount": "150.00",
            "label": "VIR RECU EPARGNE",
        },
        headers=csrf(client),
    )
    return checking, savings


def _suggestions(client: TestClient) -> list[dict[str, Any]]:
    response = client.get("/api/transfers/suggestions")
    assert response.status_code == 200
    suggestions: list[dict[str, Any]] = response.json()
    return suggestions


def _link(client: TestClient, suggestion: dict[str, Any]) -> Any:
    return client.post(
        "/api/transfers",
        json={"outflow_id": suggestion["outflow"]["id"], "inflow_id": suggestion["inflow"]["id"]},
        headers=csrf(client),
    )


def _uncategorised(client: TestClient) -> int:
    total: int = client.get("/api/transactions", params={"uncategorised": True}).json()["total"]
    return total


def test_a_transfer_between_two_accounts_is_suggested(owner_client: TestClient) -> None:
    _setup(owner_client)

    [suggestion] = _suggestions(owner_client)

    assert suggestion["outflow"]["account_name"] == "Compte courant"
    assert suggestion["outflow"]["amount"] == "-150.00"
    assert suggestion["inflow"]["account_name"] == "Livret A"
    assert suggestion["inflow"]["booked_on"] == "2026-03-11"


def test_linking_marks_both_sides_and_drops_their_category(owner_client: TestClient) -> None:
    _setup(owner_client)
    [suggestion] = _suggestions(owner_client)
    bakery = next(
        c["id"]
        for c in owner_client.get("/api/categories").json()
        if c["name"] == "Bakery and coffee"
    )
    owner_client.patch(
        f"/api/transactions/{suggestion['outflow']['id']}",
        json={"category_id": bakery},
        headers=csrf(owner_client),
    )

    response = _link(owner_client, suggestion)

    assert response.status_code == 201
    group = response.json()["group_id"]
    items = {t["id"]: t for t in owner_client.get("/api/transactions").json()["items"]}
    out, inn = items[suggestion["outflow"]["id"]], items[suggestion["inflow"]["id"]]
    assert out["transfer_group_id"] == inn["transfer_group_id"] == group
    assert out["transfer_account_name"] == "Livret A"
    assert inn["transfer_account_name"] == "Compte courant"
    assert out["category_id"] is None
    assert _suggestions(owner_client) == []


def test_a_transfer_is_neither_spending_nor_to_categorise(owner_client: TestClient) -> None:
    """Invariant §8.3."""
    _setup(owner_client)
    before = owner_client.get("/api/budget/matrix", params=MARCH).json()
    uncategorised_before = _uncategorised(owner_client)

    _link(owner_client, _suggestions(owner_client)[0])

    after = owner_client.get("/api/budget/matrix", params=MARCH).json()
    spent = lambda m: float(m["total"]["cells"][0]["spent"])  # noqa: E731
    assert spent(before) - spent(after) == 150
    assert _uncategorised(owner_client) == uncategorised_before - 2


def test_transfers_cannot_be_categorised_until_unlinked(owner_client: TestClient) -> None:
    _setup(owner_client)
    suggestion = _suggestions(owner_client)[0]
    group = _link(owner_client, suggestion).json()["group_id"]
    groceries = next(
        c["id"] for c in owner_client.get("/api/categories").json() if c["name"] == "Groceries"
    )
    out_id = suggestion["outflow"]["id"]

    patch = owner_client.patch(
        f"/api/transactions/{out_id}", json={"category_id": groceries}, headers=csrf(owner_client)
    )
    assert patch.status_code == 409
    bulk = owner_client.post(
        "/api/transactions/categorise",
        json={"transaction_ids": [out_id], "category_id": groceries},
        headers=csrf(owner_client),
    )
    assert bulk.json() == {"updated": 0}
    owner_client.post(
        "/api/rules",
        json={"category_id": groceries, "label_contains": "VIR PERM"},
        headers=csrf(owner_client),
    )
    assert owner_client.post(
        "/api/rules/apply", json={"only_uncategorised": False}, headers=csrf(owner_client)
    ).json() == {"updated": 0}

    assert (
        owner_client.delete(f"/api/transfers/{group}", headers=csrf(owner_client)).status_code
        == 204
    )
    assert (
        owner_client.patch(
            f"/api/transactions/{out_id}",
            json={"category_id": groceries},
            headers=csrf(owner_client),
        ).status_code
        == 200
    )


def test_unlinking_brings_the_suggestion_back(owner_client: TestClient) -> None:
    _setup(owner_client)
    group = _link(owner_client, _suggestions(owner_client)[0]).json()["group_id"]
    assert (
        owner_client.delete(f"/api/transfers/{group}", headers=csrf(owner_client)).status_code
        == 204
    )
    assert len(_suggestions(owner_client)) == 1
    assert (
        owner_client.delete(f"/api/transfers/{group}", headers=csrf(owner_client)).status_code
        == 404
    )


def test_every_suggestion_can_be_accepted_at_once(owner_client: TestClient) -> None:
    _setup(owner_client)
    response = owner_client.post(
        "/api/transfers/accept-suggestions", json={}, headers=csrf(owner_client)
    )
    assert response.json() == {"linked": 1}
    assert _suggestions(owner_client) == []


def test_invalid_links_are_refused(owner_client: TestClient) -> None:
    checking, _ = _setup(owner_client)
    items = owner_client.get("/api/transactions", params={"account_id": checking}).json()["items"]
    outflows = [t for t in items if t["amount"].startswith("-")]
    same_account = owner_client.post(
        "/api/transfers",
        json={"outflow_id": outflows[0]["id"], "inflow_id": outflows[1]["id"]},
        headers=csrf(owner_client),
    )
    assert same_account.status_code == 422
    suggestion = _suggestions(owner_client)[0]
    swapped = owner_client.post(
        "/api/transfers",
        json={"outflow_id": suggestion["inflow"]["id"], "inflow_id": suggestion["outflow"]["id"]},
        headers=csrf(owner_client),
    )
    assert swapped.status_code == 422
    assert _link(owner_client, suggestion).status_code == 201
    assert _link(owner_client, suggestion).status_code == 409


@pytest.mark.usefixtures("member")
def test_transfers_only_involve_accounts_the_member_can_see(
    client: TestClient, clock: Clock
) -> None:
    log_in(client, clock)
    _setup(client, savings_visibility="private")
    log_in(client, clock, "member@example.com")
    assert _suggestions(client) == []


def test_transfers_require_a_full_sign_in(client: TestClient) -> None:
    assert client.get("/api/transfers/suggestions").status_code == 401
