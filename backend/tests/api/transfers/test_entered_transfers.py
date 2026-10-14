"""Transfers entered by hand, edited side by side, and linked by hand (F-TX-5, F-TX-9)."""

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
        "name": "Compte perso",
        "institution_name": "SG",
        "type": "checking",
        "visibility": "shared",
        "opening_balance": "0",
        "opening_date": "2026-03-01",
        **changes,
    }
    account_id: str = client.post("/api/accounts", json=body, headers=csrf(client)).json()["id"]
    return account_id


def _enter(client: TestClient, source: str, destination: str, **changes: Any) -> Any:
    body = {
        "source_account_id": source,
        "destination_account_id": destination,
        "booked_on": "2026-03-10",
        "amount": "500.00",
        "outflow_label": "Virement vers Compte commun",
        "inflow_label": "Virement depuis Compte perso",
        **changes,
    }
    return client.post("/api/transfers/entries", json=body, headers=csrf(client))


def _items(client: TestClient) -> dict[str, dict[str, Any]]:
    return {t["id"]: t for t in client.get("/api/transactions").json()["items"]}


def _two_accounts(client: TestClient) -> tuple[str, str]:
    return _account(client), _account(client, name="Compte commun", visibility="joint")


def test_entering_a_transfer_creates_both_sides_already_linked(owner_client: TestClient) -> None:
    mine, joint = _two_accounts(owner_client)

    response = _enter(owner_client, mine, joint)

    assert response.status_code == 201
    entry = response.json()
    assert entry["outflow"]["amount"] == "-500.00"
    assert entry["outflow"]["account_name"] == "Compte perso"
    assert entry["inflow"]["amount"] == "500.00"
    assert entry["inflow"]["label"] == "Virement depuis Compte perso"
    items = _items(owner_client)
    out, inn = items[entry["outflow"]["id"]], items[entry["inflow"]["id"]]
    assert out["transfer_group_id"] == inn["transfer_group_id"] == entry["group_id"]
    assert out["source"] == inn["source"] == "manual"
    assert out["transfer_account_name"] == "Compte commun"
    assert out["category_id"] is None
    to_categorise = owner_client.get("/api/transactions", params={"uncategorised": True})
    assert to_categorise.json()["total"] == 0
    assert owner_client.get("/api/transfers/suggestions").json() == []


def test_invalid_transfers_are_refused(owner_client: TestClient) -> None:
    mine, joint = _two_accounts(owner_client)
    pea = _account(owner_client, name="PEA", type="brokerage")

    assert _enter(owner_client, mine, mine).status_code == 422
    assert _enter(owner_client, mine, pea).status_code == 422
    assert _enter(owner_client, mine, joint, amount="-500.00").status_code == 422
    assert _enter(owner_client, mine, joint, amount="0").status_code == 422
    assert _enter(owner_client, mine, joint, booked_on="2026-02-01").status_code == 422
    assert _enter(owner_client, mine, joint, inflow_label=" ").status_code == 422
    assert owner_client.get("/api/transactions").json()["total"] == 0


@pytest.mark.usefixtures("member")
def test_a_transfer_only_involves_accounts_the_member_can_see(
    client: TestClient, clock: Clock
) -> None:
    log_in(client, clock)
    private = _account(client, name="Livret du propriétaire", visibility="private")
    log_in(client, clock, "member@example.com")
    joint = _account(client, name="Compte commun", visibility="joint")

    assert _enter(client, joint, private).status_code == 404


def test_editing_a_side_moves_the_other_manual_side(owner_client: TestClient) -> None:
    mine, joint = _two_accounts(owner_client)
    entry = _enter(owner_client, mine, joint).json()

    response = owner_client.patch(
        f"/api/transactions/{entry['inflow']['id']}",
        json={"amount": "550.00", "booked_on": "2026-03-12", "label": "Quote-part mars"},
        headers=csrf(owner_client),
    )

    assert response.status_code == 200
    out = _items(owner_client)[entry["outflow"]["id"]]
    assert out["amount"] == "-550.00"
    assert out["booked_on"] == "2026-03-12"
    assert out["label"] == "Virement vers Compte commun"  # a label is one side's


def test_a_side_cannot_change_direction(owner_client: TestClient) -> None:
    mine, joint = _two_accounts(owner_client)
    entry = _enter(owner_client, mine, joint).json()

    response = owner_client.patch(
        f"/api/transactions/{entry['outflow']['id']}",
        json={"amount": "500.00"},
        headers=csrf(owner_client),
    )

    assert response.status_code == 422
    assert _items(owner_client)[entry["inflow"]["id"]]["amount"] == "500.00"


def _half_imported(client: TestClient) -> tuple[str, str]:
    """The fixture's imported -150 € standing order, linked to a Livret A entered by hand."""
    checking = _account(client, name="Compte courant")
    files = {"file": ("export.csv", CHECKING_CSV, "text/csv")}
    client.post(f"/api/accounts/{checking}/imports", files=files, headers=csrf(client))
    savings = _account(client, name="Livret A", type="savings")
    inflow = client.post(
        "/api/transactions",
        json={
            "account_id": savings,
            "booked_on": "2026-03-11",
            "amount": "150.00",
            "label": "VIR RECU",
        },
        headers=csrf(client),
    ).json()["id"]
    [suggestion] = client.get("/api/transfers/suggestions").json()
    client.post(
        "/api/transfers",
        json={"outflow_id": suggestion["outflow"]["id"], "inflow_id": inflow},
        headers=csrf(client),
    )
    return suggestion["outflow"]["id"], inflow


def test_a_side_from_a_statement_locks_the_amount(owner_client: TestClient) -> None:
    imported, manual = _half_imported(owner_client)

    locked = owner_client.patch(
        f"/api/transactions/{manual}", json={"amount": "160.00"}, headers=csrf(owner_client)
    )
    moved = owner_client.patch(
        f"/api/transactions/{manual}", json={"booked_on": "2026-03-13"}, headers=csrf(owner_client)
    )

    assert locked.status_code == 422
    assert "locked" in locked.json()["detail"]
    assert moved.status_code == 200
    items = _items(owner_client)
    assert items[manual]["amount"] == "150.00"
    assert items[manual]["booked_on"] == "2026-03-13"
    assert items[imported]["booked_on"] == "2026-03-10"


def test_deleting_a_side_deletes_the_other_manual_side(owner_client: TestClient) -> None:
    mine, joint = _two_accounts(owner_client)
    entry = _enter(owner_client, mine, joint).json()

    response = owner_client.delete(
        f"/api/transactions/{entry['outflow']['id']}", headers=csrf(owner_client)
    )

    assert response.status_code == 204
    assert owner_client.get("/api/transactions").json()["total"] == 0


def test_deleting_the_manual_side_only_unlinks_a_side_from_a_statement(
    owner_client: TestClient,
) -> None:
    imported, manual = _half_imported(owner_client)

    owner_client.delete(f"/api/transactions/{manual}", headers=csrf(owner_client))

    items = _items(owner_client)
    assert manual not in items
    assert items[imported]["transfer_group_id"] is None


def test_link_candidates_list_the_opposite_amount_within_31_days(
    owner_client: TestClient,
) -> None:
    mine, joint = _two_accounts(owner_client)
    savings = _account(owner_client, name="Livret A", type="savings")

    def entry(account: str, booked_on: str, amount: str) -> str:
        body = {"account_id": account, "booked_on": booked_on, "amount": amount, "label": "VIR"}
        response = owner_client.post("/api/transactions", json=body, headers=csrf(owner_client))
        transaction_id: str = response.json()["id"]
        return transaction_id

    outflow = entry(mine, "2026-03-01", "-500.00")
    near = entry(joint, "2026-03-08", "500.00")
    far = entry(savings, "2026-03-20", "500.00")
    entry(savings, "2026-04-05", "500.00")  # 35 days later
    entry(joint, "2026-03-02", "499.00")
    entry(mine, "2026-03-02", "500.00")  # same account

    response = owner_client.get(f"/api/transfers/candidates/{outflow}")

    assert response.status_code == 200
    assert [c["id"] for c in response.json()] == [near, far]
    assert response.json()[0]["account_name"] == "Compte commun"
    linked = owner_client.post(
        "/api/transfers", json={"outflow_id": outflow, "inflow_id": far}, headers=csrf(owner_client)
    )
    assert linked.status_code == 201
    assert owner_client.get(f"/api/transfers/candidates/{near}").json() == []
    assert owner_client.get(f"/api/transfers/candidates/{outflow}").status_code == 409


@pytest.mark.usefixtures("member")
def test_link_candidates_skip_accounts_the_member_cannot_see(
    client: TestClient, clock: Clock
) -> None:
    log_in(client, clock)
    private = _account(client, name="Livret du propriétaire", visibility="private")
    hidden = client.post(
        "/api/transactions",
        json={"account_id": private, "booked_on": "2026-03-02", "amount": "80.00", "label": "VIR"},
        headers=csrf(client),
    ).json()["id"]
    log_in(client, clock, "member@example.com")
    joint = _account(client, name="Compte commun", visibility="joint")
    outflow = client.post(
        "/api/transactions",
        json={"account_id": joint, "booked_on": "2026-03-01", "amount": "-80.00", "label": "VIR"},
        headers=csrf(client),
    ).json()["id"]

    assert client.get(f"/api/transfers/candidates/{outflow}").json() == []
    assert client.get(f"/api/transfers/candidates/{hidden}").status_code == 404


def _owner_share(client: TestClient, clock: Clock) -> dict[str, Any]:
    """The owner pays 500 € from their private account into the joint one; the member signs in."""
    log_in(client, clock)
    private = _account(
        client,
        name="Livret du propriétaire",
        type="savings",
        visibility="private",
        opening_date="2026-03-05",
    )
    joint = _account(client, name="Compte commun", visibility="joint")
    entry: dict[str, Any] = _enter(client, private, joint).json()
    log_in(client, clock, "member@example.com")
    return entry


@pytest.mark.usefixtures("member")
def test_a_member_cannot_move_a_side_they_cannot_see(client: TestClient, clock: Clock) -> None:
    entry = _owner_share(client, clock)
    joint_side = f"/api/transactions/{entry['inflow']['id']}"

    moved = client.patch(joint_side, json={"amount": "5.00"}, headers=csrf(client))
    too_early = client.patch(joint_side, json={"booked_on": "2026-03-02"}, headers=csrf(client))
    renamed = client.patch(joint_side, json={"label": "Quote-part"}, headers=csrf(client))
    deleted = client.delete(joint_side, headers=csrf(client))

    assert moved.status_code == too_early.status_code == deleted.status_code == 409
    # Valid for the joint account, before the private one opens: that must not show.
    assert moved.json() == too_early.json() == deleted.json()
    assert renamed.status_code == 200
    log_in(client, clock)
    items = _items(client)
    assert items[entry["outflow"]["id"]]["amount"] == "-500.00"
    assert items[entry["outflow"]["id"]]["booked_on"] == "2026-03-10"
    assert items[entry["inflow"]["id"]]["amount"] == "500.00"


def test_linking_drops_a_budget_month_set_by_hand(owner_client: TestClient) -> None:
    mine, joint = _two_accounts(owner_client)

    def entry(account: str, amount: str) -> str:
        body = {"account_id": account, "booked_on": "2026-03-10", "amount": amount, "label": "VIR"}
        response = owner_client.post("/api/transactions", json=body, headers=csrf(owner_client))
        transaction_id: str = response.json()["id"]
        return transaction_id

    outflow, inflow = entry(mine, "-80.00"), entry(joint, "80.00")
    owner_client.patch(
        f"/api/transactions/{outflow}", json={"budget_month": "2026-04"}, headers=csrf(owner_client)
    )

    owner_client.post(
        "/api/transfers",
        json={"outflow_id": outflow, "inflow_id": inflow},
        headers=csrf(owner_client),
    )

    out = _items(owner_client)[outflow]
    assert out["budget_month"] == "2026-03"
    assert out["budget_month_set"] is False


def test_rolling_back_an_import_unlinks_the_other_side(owner_client: TestClient) -> None:
    imported, manual = _half_imported(owner_client)
    checking = _items(owner_client)[imported]["account_id"]
    [batch] = owner_client.get(f"/api/accounts/{checking}/imports").json()

    owner_client.delete(f"/api/imports/{batch['id']}", headers=csrf(owner_client))

    items = _items(owner_client)
    assert imported not in items
    assert items[manual]["transfer_group_id"] is None
    assert items[manual]["transfer_account_name"] is None


@pytest.mark.usefixtures("member")
def test_a_member_rolling_back_an_import_only_unlinks_a_private_side(
    client: TestClient, clock: Clock
) -> None:
    log_in(client, clock)
    imported, manual = _half_imported(client)
    items = _items(client)
    client.patch(
        f"/api/accounts/{items[manual]['account_id']}",
        json={"visibility": "private"},
        headers=csrf(client),
    )
    checking = items[imported]["account_id"]
    [batch] = client.get(f"/api/accounts/{checking}/imports").json()

    log_in(client, clock, "member@example.com")
    assert manual not in _items(client)
    response = client.delete(f"/api/imports/{batch['id']}", headers=csrf(client))

    assert response.status_code == 204
    log_in(client, clock)
    private_side = _items(client)[manual]
    assert private_side["amount"] == "150.00"
    assert private_side["transfer_group_id"] is None
