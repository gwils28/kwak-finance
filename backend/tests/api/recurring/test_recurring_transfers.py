"""Recurring transfers: a member's monthly share paid into the joint account (F-REC, F-TX-9)."""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from kwak_api.models import User

from tests.api.budget.test_budget_month import _account, _add, _category
from tests.api.conftest import Clock, csrf, log_in
from tests.api.recurring.test_recurring import TODAY, _upcoming


@pytest.fixture
def owner_client(client: TestClient, clock: Clock, owner: User) -> TestClient:
    clock.now = TODAY
    log_in(client, clock)
    return client


def _accounts(client: TestClient) -> tuple[str, str]:
    mine, joint = _account(client, "Mine"), _account(client, "Joint")
    client.patch(f"/api/accounts/{joint}", json={"visibility": "joint"}, headers=csrf(client))
    return mine, joint


def _share(client: TestClient, mine: str, joint: str, **changes: Any) -> Any:
    body = {
        "account_id": mine,
        "destination_account_id": joint,
        "label": "",
        "amount": "-500.00",
        "frequency": "monthly",
        "day": 5,
        "start_on": "2026-02-01",
        **changes,
    }
    return client.post("/api/recurring", json=body, headers=csrf(client))


def _transfer(client: TestClient, source: str, destination: str, day: str, amount: str) -> None:
    body = {
        "source_account_id": source,
        "destination_account_id": destination,
        "booked_on": day,
        "amount": amount,
        "outflow_label": "Virement vers Joint",
        "inflow_label": "Virement depuis Mine",
    }
    response = client.post("/api/transfers/entries", json=body, headers=csrf(client))
    assert response.status_code == 201, response.text


def test_a_transfer_item_is_fulfilled_by_a_transfer_to_its_destination(
    owner_client: TestClient,
) -> None:
    mine, joint = _accounts(owner_client)
    response = _share(owner_client, mine, joint)
    assert response.status_code == 201, response.text
    _transfer(owner_client, mine, joint, "2026-02-06", "500.00")
    _add(owner_client, mine, "2026-03-05", "-500.00", "VIREMENT", None)  # not a transfer

    [listed] = owner_client.get("/api/recurring").json()

    assert listed["destination_account_id"] == joint
    assert listed["destination_account_name"] == "Joint"
    assert listed["category_id"] is None
    assert [(o["due"], o["status"]) for o in listed["recent"]] == [
        ("2026-03-05", "late"),
        ("2026-02-05", "fulfilled"),
    ]


@pytest.mark.parametrize(
    "changes",
    [{"destination_account_id": "same"}, {"amount": "500.00"}, {"category_id": "rent"}],
)
def test_an_invalid_transfer_item_is_refused(
    owner_client: TestClient, changes: dict[str, Any]
) -> None:
    mine, joint = _accounts(owner_client)
    if changes.get("destination_account_id") == "same":
        changes["destination_account_id"] = mine
    if changes.get("category_id") == "rent":
        changes["category_id"] = _category(owner_client, "Rent or mortgage")

    body = {"label": "Quote-part", **changes}
    assert _share(owner_client, mine, joint, **body).status_code == 422


def test_a_transfer_item_counts_on_each_side_of_the_scopes(owner_client: TestClient) -> None:
    mine, joint = _accounts(owner_client)
    _add(owner_client, mine, "2026-03-01", "2000.00", "SALAIRE", None)
    _share(owner_client, mine, joint, day=20, start_on="2026-03-01")

    def share_in(scope: str) -> tuple[str, str]:
        upcoming = _upcoming(owner_client, scope=scope)
        [occurrence] = upcoming["occurrences"]
        assert occurrence["destination_account_name"] == "Joint"
        return occurrence["amount_in_scope"], upcoming["projected_balance"]

    assert share_in("mine") == ("-500.00", "1500.00")
    assert share_in("joint") == ("500.00", "500.00")
    assert share_in("household") == ("0.00", "2000.00")


def test_a_member_does_not_see_a_share_paid_from_a_private_account(
    client: TestClient, clock: Clock, member: User
) -> None:
    clock.now = TODAY
    log_in(client, clock)
    mine, joint = _accounts(client)
    client.patch(f"/api/accounts/{mine}", json={"visibility": "private"}, headers=csrf(client))
    item = _share(client, mine, joint).json()

    log_in(client, clock, "member@example.com")
    assert client.get("/api/recurring").json() == []
    assert _upcoming(client, scope="joint")["occurrences"] == []
    response = client.patch(
        f"/api/recurring/{item['id']}", json={"paused": True}, headers=csrf(client)
    )
    assert response.status_code == 404
    other = _account(client, "Member's")
    assert _share(client, other, mine).status_code == 422


def test_a_member_does_not_see_a_share_paid_into_a_private_account(
    client: TestClient, clock: Clock, member: User
) -> None:
    clock.now = TODAY
    log_in(client, clock)
    shared, private = _accounts(client)
    client.patch(f"/api/accounts/{private}", json={"visibility": "private"}, headers=csrf(client))
    item = _share(client, shared, private).json()

    log_in(client, clock, "member@example.com")
    assert client.get("/api/recurring").json() == []
    assert _upcoming(client)["occurrences"] == []
    path = f"/api/recurring/{item['id']}"
    assert client.patch(path, json={"paused": True}, headers=csrf(client)).status_code == 404
    assert client.put(f"{path}/skips/2026-03-05", headers=csrf(client)).status_code == 404
    assert client.delete(path, headers=csrf(client)).status_code == 404
