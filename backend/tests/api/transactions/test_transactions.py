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


def _account(client: TestClient, **changes: Any) -> str:
    body = {
        "name": "Compte courant",
        "institution_name": "Société Générale",
        "type": "checking",
        "visibility": "shared",
        "opening_balance": "100.00",
        "opening_date": "2026-03-01",
        **changes,
    }
    response = client.post("/api/accounts", json=body, headers=csrf(client))
    assert response.status_code == 201, response.text
    account_id: str = response.json()["id"]
    return account_id


def _import(client: TestClient, account_id: str) -> None:
    files = {"file": ("export.csv", CHECKING_CSV, "text/csv")}
    response = client.post(f"/api/accounts/{account_id}/imports", files=files, headers=csrf(client))
    assert response.status_code == 201


def _manual(client: TestClient, account_id: str, **changes: Any) -> Any:
    body = {
        "account_id": account_id,
        "booked_on": "2026-03-20",
        "amount": "-12.50",
        "label": "Market",
        **changes,
    }
    return client.post("/api/transactions", json=body, headers=csrf(client))


def _list(client: TestClient, **params: Any) -> Any:
    response = client.get("/api/transactions", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def test_transactions_are_listed_newest_first_with_their_account(owner_client: TestClient) -> None:
    account = _account(owner_client)
    _import(owner_client, account)

    page = _list(owner_client)

    assert page["total"] == 14
    first = page["items"][0]
    assert first["booked_on"] == "2026-03-14"
    assert first["account_name"] == "Compte courant"
    assert first["source"] == "import"
    assert [t["booked_on"] for t in page["items"]] == sorted(
        (t["booked_on"] for t in page["items"]), reverse=True
    )


def test_the_list_is_paginated(owner_client: TestClient) -> None:
    _import(owner_client, _account(owner_client))
    first = _list(owner_client, limit=5)
    second = _list(owner_client, limit=5, offset=5)
    assert len(first["items"]) == 5
    assert first["total"] == 14
    assert {t["id"] for t in first["items"]}.isdisjoint(t["id"] for t in second["items"])


def test_filters_by_account_period_and_text(owner_client: TestClient) -> None:
    checking = _account(owner_client)
    savings = _account(owner_client, name="Livret A", type="savings")
    _import(owner_client, checking)
    _manual(owner_client, savings, label="Transfer to savings", amount="200")

    assert _list(owner_client, account_id=savings)["total"] == 1
    assert _list(owner_client, date_from="2026-03-13", date_to="2026-03-14")["total"] == 3
    # Case, spacing and accents do not matter.
    assert _list(owner_client, q="  Café de la  gare ")["total"] == 2
    assert _list(owner_client, q="eglise")["total"] == 1


def test_add_a_manual_transaction(owner_client: TestClient) -> None:
    account = _account(owner_client)

    response = _manual(owner_client, account, amount="-12.5")

    assert response.status_code == 201
    created = response.json()
    assert created["amount"] == "-12.50"
    assert created["source"] == "manual"
    assert owner_client.get("/api/accounts").json()[0]["balance"] == "87.50"


@pytest.mark.parametrize(
    "changes",
    [{"amount": "0"}, {"amount": "1.234"}, {"label": "   "}, {"booked_on": "2026-02-28"}],
)
def test_invalid_manual_transactions_are_rejected(
    owner_client: TestClient, changes: dict[str, str]
) -> None:
    account = _account(owner_client)
    body = {"amount": "-12.50", **changes}
    assert _manual(owner_client, account, **body).status_code == 422


def test_manual_entries_need_an_open_cash_account(owner_client: TestClient) -> None:
    pea = _account(owner_client, name="PEA", type="brokerage")
    assert _manual(owner_client, pea, amount="-1.00").status_code == 422
    checking = _account(owner_client)
    owner_client.patch(
        f"/api/accounts/{checking}", json={"closed_on": "2026-06-30"}, headers=csrf(owner_client)
    )
    assert _manual(owner_client, checking, amount="-1.00").status_code == 422


def test_a_manual_transaction_can_be_edited_and_deleted(owner_client: TestClient) -> None:
    account = _account(owner_client)
    created = _manual(owner_client, account, amount="-12.50").json()

    response = owner_client.patch(
        f"/api/transactions/{created['id']}",
        json={"amount": "-15.00", "label": "Market (fruit)"},
        headers=csrf(owner_client),
    )
    assert response.status_code == 200
    assert response.json()["amount"] == "-15.00"
    assert response.json()["label"] == "Market (fruit)"

    assert (
        owner_client.delete(
            f"/api/transactions/{created['id']}", headers=csrf(owner_client)
        ).status_code
        == 204
    )
    assert _list(owner_client)["total"] == 0


def test_imported_transactions_are_read_only(owner_client: TestClient) -> None:
    account = _account(owner_client)
    _import(owner_client, account)
    imported = _list(owner_client, limit=1)["items"][0]

    patch = owner_client.patch(
        f"/api/transactions/{imported['id']}", json={"amount": "-1.00"}, headers=csrf(owner_client)
    )
    assert patch.status_code == 409
    assert "roll back" in patch.json()["detail"]
    delete = owner_client.delete(f"/api/transactions/{imported['id']}", headers=csrf(owner_client))
    assert delete.status_code == 409


@pytest.mark.usefixtures("member")
def test_transactions_of_someone_elses_private_account_stay_hidden(
    client: TestClient, clock: Clock
) -> None:
    log_in(client, clock)
    private = _account(client, visibility="private")
    created = _manual(client, private, amount="-5.00").json()

    log_in(client, clock, "member@example.com")
    assert _list(client)["total"] == 0
    assert _list(client, account_id=private)["total"] == 0
    assert _manual(client, private, amount="-1.00").status_code == 404
    patch = client.patch(
        f"/api/transactions/{created['id']}", json={"label": "x"}, headers=csrf(client)
    )
    assert patch.status_code == 404


def test_transactions_require_a_full_sign_in(client: TestClient) -> None:
    assert client.get("/api/transactions").status_code == 401
