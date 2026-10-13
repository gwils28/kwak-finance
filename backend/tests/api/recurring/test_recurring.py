"""Recurring items: definition, occurrences, suggestions and upcoming items (F-REC)."""

from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from kwak_api.models import User

from tests.api.budget.test_budget_month import _account, _add, _category
from tests.api.conftest import Clock, csrf, log_in

TODAY = datetime(2026, 3, 13, 12, tzinfo=UTC)


@pytest.fixture
def owner_client(client: TestClient, clock: Clock, owner: User) -> TestClient:
    clock.now = TODAY
    log_in(client, clock)
    return client


def _item(client: TestClient, account: str, **changes: Any) -> Any:
    body = {
        "account_id": account,
        "label": "LOYER",
        "amount": "-950.00",
        "frequency": "monthly",
        "day": 3,
        "start_on": "2026-01-01",
        "category_id": _category(client, "Rent or mortgage"),
        **changes,
    }
    response = client.post("/api/recurring", json=body, headers=csrf(client))
    assert response.status_code == 201, response.text
    return response.json()


def _items(client: TestClient) -> dict[str, Any]:
    response = client.get("/api/recurring")
    assert response.status_code == 200, response.text
    return {i["label"]: i for i in response.json()}


def _upcoming(client: TestClient, **params: str) -> Any:
    response = client.get("/api/recurring/upcoming", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def test_an_item_lists_its_next_and_past_occurrences(owner_client: TestClient) -> None:
    account = _account(owner_client)
    rent = _item(owner_client, account)
    january = _add(owner_client, account, "2026-01-05", "-950.00", "LOYER JANVIER", None)
    _add(owner_client, account, "2026-03-02", "-950.00", "LOYER MARS", None)

    listed = _items(owner_client)["LOYER"]
    assert listed["id"] == rent["id"]
    assert listed["account_name"] == "Checking"
    assert listed["category_name"] == "Rent or mortgage"
    assert listed["next"]["due"] == "2026-04-03"
    assert listed["next"]["status"] == "upcoming"
    # Newest first: March paid on the 2nd, February never came, January paid on the 5th.
    assert [(o["due"], o["status"]) for o in listed["recent"]] == [
        ("2026-03-03", "fulfilled"),
        ("2026-02-03", "late"),
        ("2026-01-03", "fulfilled"),
    ]
    assert listed["recent"][2]["transaction_id"] == january


@pytest.mark.parametrize(
    "changes",
    [{"label": " "}, {"amount": "0"}, {"frequency": "weekly", "day": 7}, {"end_on": "2025-12-31"}],
)
def test_an_invalid_item_is_refused(owner_client: TestClient, changes: dict[str, Any]) -> None:
    account = _account(owner_client)
    body = {
        "account_id": account,
        "label": "LOYER",
        "amount": "-950.00",
        "frequency": "monthly",
        "day": 3,
        "start_on": "2026-01-01",
        **changes,
    }
    response = owner_client.post("/api/recurring", json=body, headers=csrf(owner_client))
    assert response.status_code == 422


def test_an_item_can_be_paused_edited_and_deleted(owner_client: TestClient) -> None:
    rent = _item(owner_client, _account(owner_client))
    url = f"/api/recurring/{rent['id']}"

    paused = owner_client.patch(url, json={"paused": True}, headers=csrf(owner_client)).json()
    assert (paused["paused"], paused["next"]) == (True, None)
    edited = owner_client.patch(
        url, json={"paused": False, "amount": "-980.00", "day": 5}, headers=csrf(owner_client)
    ).json()
    assert (edited["amount"], edited["next"]["due"], edited["next"]["expected"]) == (
        "-980.00",
        "2026-04-05",
        "-980.00",
    )
    assert owner_client.delete(url, headers=csrf(owner_client)).status_code == 204
    assert _items(owner_client) == {}
    assert owner_client.delete(url, headers=csrf(owner_client)).status_code == 404


def test_an_occurrence_can_be_skipped_and_unskipped(owner_client: TestClient) -> None:
    rent = _item(owner_client, _account(owner_client))
    skip = f"/api/recurring/{rent['id']}/skips/2026-02-03"

    assert owner_client.put(skip, headers=csrf(owner_client)).status_code == 204
    february = _items(owner_client)["LOYER"]["recent"][1]
    assert (february["due"], february["status"]) == ("2026-02-03", "skipped")
    assert owner_client.delete(skip, headers=csrf(owner_client)).status_code == 204
    assert _items(owner_client)["LOYER"]["recent"][1]["status"] == "late"

    not_due = f"/api/recurring/{rent['id']}/skips/2026-02-04"
    assert owner_client.put(not_due, headers=csrf(owner_client)).status_code == 422


def test_upcoming_items_and_the_projected_balance(owner_client: TestClient) -> None:
    account = _account(owner_client)  # opened with 0
    _add(owner_client, account, "2026-03-01", "1000.00", "VIREMENT", None)
    _item(owner_client, account)  # due on the 3rd of each month since January
    march = {"start_on": "2026-03-01", "category_id": None}
    _item(owner_client, account, label="SALAIRE", amount="2500.00", day=28, **march)
    _item(owner_client, account, label="NETFLIX", amount="-15.99", day=10, **march)
    _add(owner_client, account, "2026-03-10", "-15.99", "NETFLIX.COM", None)
    _item(owner_client, account, label="EDF", amount="-80.00", day=20, estimated=True, **march)

    upcoming = _upcoming(owner_client)
    # February's rent, 38 days late, is no longer listed (31 days at most).
    assert [(o["label"], o["due"], o["status"]) for o in upcoming["occurrences"]] == [
        ("LOYER", "2026-03-03", "late"),
        ("EDF", "2026-03-20", "upcoming"),
        ("SALAIRE", "2026-03-28", "upcoming"),
    ]
    rent, edf, salary = upcoming["occurrences"]
    assert (rent["enter_on"], rent["expected"]) == ("2026-03-03", "-950.00")
    assert rent["category_id"] == _category(owner_client, "Rent or mortgage")
    assert (edf["estimated"], edf["expected"]) == (True, "-80.00")
    assert salary["enter_on"] == "2026-03-13"  # the 28th is still to come
    assert upcoming["current_balance"] == "984.01"
    assert upcoming["projected_balance"] == "2454.01"  # 984.01 - 950 - 80 + 2500


def test_upcoming_covers_the_scope_s_cash_accounts(owner_client: TestClient) -> None:
    mine = _account(owner_client)
    joint = _account(owner_client, "Joint")
    owner_client.patch(
        f"/api/accounts/{joint}", json={"visibility": "joint"}, headers=csrf(owner_client)
    )
    march = {"start_on": "2026-03-01"}
    _item(owner_client, mine, label="SALAIRE", amount="2500.00", day=28, category_id=None, **march)
    _item(owner_client, joint, day=20, **march)

    assert [o["label"] for o in _upcoming(owner_client, scope="joint")["occurrences"]] == ["LOYER"]
    assert [o["label"] for o in _upcoming(owner_client, scope="mine")["occurrences"]] == ["SALAIRE"]


def test_regular_payments_are_suggested_until_dismissed_or_followed(
    owner_client: TestClient,
) -> None:
    account = _account(owner_client)
    for day in ("2025-12-04", "2026-01-05", "2026-02-03", "2026-03-04"):
        _add(owner_client, account, day, "-15.99", "Netflix", "Streaming")
    for day in ("2026-01-10", "2026-02-10", "2026-03-10"):
        _add(owner_client, account, day, "-9.99", "Spotify", None)

    response = owner_client.get("/api/recurring/suggestions")
    assert response.status_code == 200, response.text
    netflix, spotify = response.json()
    assert netflix == {
        "account_id": account,
        "account_name": "Checking",
        "label": "NETFLIX",
        "amount": "-15.99",
        "estimated": False,
        "frequency": "monthly",
        "day": 4,
        "start_on": "2025-12-04",
        "category_id": _category(owner_client, "Streaming"),
        "count": 4,
    }
    assert spotify["label"] == "SPOTIFY"

    dismissed = owner_client.post(
        "/api/recurring/suggestions/dismiss",
        json={"account_id": account, "label": "SPOTIFY"},
        headers=csrf(owner_client),
    )
    assert dismissed.status_code == 204
    _item(owner_client, account, label="Netflix", amount="-15.99", day=4, start_on="2025-12-01")
    assert owner_client.get("/api/recurring/suggestions").json() == []


def test_entering_a_transaction_can_set_its_category(owner_client: TestClient) -> None:
    account = _account(owner_client)
    body = {
        "account_id": account,
        "booked_on": "2026-03-03",
        "amount": "-950.00",
        "label": "LOYER",
        "category_id": _category(owner_client, "Rent or mortgage"),
    }
    response = owner_client.post("/api/transactions", json=body, headers=csrf(owner_client))
    assert response.status_code == 201, response.text
    assert response.json()["category_name"] == "Rent or mortgage"


def test_a_member_does_not_see_items_of_a_private_account(
    client: TestClient, clock: Clock, member: User
) -> None:
    clock.now = TODAY
    log_in(client, clock)
    private = _account(client)
    client.patch(f"/api/accounts/{private}", json={"visibility": "private"}, headers=csrf(client))
    rent = _item(client, private)

    log_in(client, clock, "member@example.com")
    assert client.get("/api/recurring").json() == []
    assert _upcoming(client)["occurrences"] == []
    response = client.patch(
        f"/api/recurring/{rent['id']}", json={"paused": True}, headers=csrf(client)
    )
    assert response.status_code == 404
    body = {
        "account_id": private,
        "label": "X",
        "amount": "-1.00",
        "frequency": "monthly",
        "day": 1,
        "start_on": "2026-01-01",
    }
    assert client.post("/api/recurring", json=body, headers=csrf(client)).status_code == 422


def test_recurring_items_require_a_full_sign_in(client: TestClient) -> None:
    assert client.get("/api/recurring").status_code == 401
