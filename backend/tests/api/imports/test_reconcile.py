"""Reconciling manual entries with a statement (F-TX-8, invariant §8.17)."""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from kwak_api.models import User

from tests.api.budget.test_budget_month import _add, _category
from tests.api.conftest import Clock, csrf, log_in
from tests.api.imports.test_imports import CHECKING_CSV, _account, _send

# Lines of the synthetic checking statement (1 March to 14 March 2026).
COFFEE, RENT, ELECTRICITY = 5, 10, 11


@pytest.fixture
def owner_client(client: TestClient, clock: Clock, owner: User) -> TestClient:
    log_in(client, clock)
    return client


def _entries(client: TestClient, account: str) -> dict[str, str]:
    """What was entered by hand during March, before the statement came."""
    return {
        "electricity": _add(client, account, "2026-03-03", "-78.45", "EDF", "Utilities"),
        "rent": _add(client, account, "2026-03-08", "-1250.00", "LOYER", "Rent or mortgage"),
        "coffee": _add(client, account, "2026-03-13", "-1.10", "CAFE", "Bakery and coffee"),
        "typo": _add(client, account, "2026-03-07", "-42.00", "PHARMACIE", "Pharmacy"),
        "later": _add(client, account, "2026-03-25", "-9.99", "STREAMING", "Streaming"),
    }


def _transactions(client: TestClient) -> dict[str, Any]:
    items = client.get("/api/transactions", params={"limit": 200}).json()["items"]
    return {t["id"]: t for t in items}


def test_the_preview_shows_the_rows_already_entered(owner_client: TestClient) -> None:
    account = _account(owner_client)
    entries = _entries(owner_client, account)

    preview = _send(owner_client, account, CHECKING_CSV, preview=True).json()

    assert preview["counts"] == {
        "new": 11,
        "already_entered": 3,
        "duplicate": 0,
        "before_opening": 0,
        "error": 0,
    }
    rows = {r["line"]: r for r in preview["rows"]}
    assert rows[ELECTRICITY]["status"] == "already_entered"
    assert rows[ELECTRICITY]["entry"] == {
        "id": entries["electricity"],
        "booked_on": "2026-03-03",
        "label": "EDF",
        "amount": "-78.45",
    }
    assert rows[RENT]["entry"]["id"] == entries["rent"]
    assert rows[COFFEE]["entry"]["id"] == entries["coffee"]  # the first of two equal coffees
    assert rows[COFFEE + 1]["status"] == "new"
    assert rows[4]["entry"] is None
    # Entered by hand within the statement's dates, but in no row; the 25th is after it.
    assert [e["id"] for e in preview["unmatched_entries"]] == [entries["typo"]]


def test_importing_takes_the_entries_over_instead_of_adding_them_twice(
    owner_client: TestClient,
) -> None:
    account = _account(owner_client)
    entries = _entries(owner_client, account)

    response = _send(owner_client, account, CHECKING_CSV)
    assert response.status_code == 201, response.text
    batch = response.json()
    assert (batch["imported_count"], batch["reconciled_count"]) == (11, 3)

    listed = _transactions(owner_client)
    assert len(listed) == 14 + 2  # every row once, plus the two entries no row took
    electricity = listed[entries["electricity"]]
    assert electricity["booked_on"] == "2026-03-05"  # the bank's date
    assert electricity["label"] == "EDF"  # the user's label and category stay
    assert electricity["category_id"] == _category(owner_client, "Utilities")
    assert electricity["bank_label"].startswith("PRELEVEMENT EUROPEEN")
    assert electricity["source"] == "import"
    assert listed[entries["typo"]]["source"] == "manual"
    # Balance as if only the statement had been imported, plus the entries no row took.
    check = batch["balance_check"]
    assert check["difference"] == "-42.00"

    again = _send(owner_client, account, CHECKING_CSV, preview=True).json()
    assert again["counts"]["duplicate"] == 14


def test_a_match_undone_in_the_preview_imports_the_row_as_new(owner_client: TestClient) -> None:
    account = _account(owner_client)
    entries = _entries(owner_client, account)
    refused = {"refused": f"{RENT}:{entries['rent']}"}

    preview = owner_client.post(
        f"/api/accounts/{account}/imports/preview",
        files={"file": ("export.csv", CHECKING_CSV, "text/csv")},
        data=refused,
        headers=csrf(owner_client),
    ).json()
    rows = {r["line"]: r for r in preview["rows"]}
    assert (rows[RENT]["status"], rows[RENT]["entry"]) == ("new", None)
    assert entries["rent"] in [e["id"] for e in preview["unmatched_entries"]]

    response = owner_client.post(
        f"/api/accounts/{account}/imports",
        files={"file": ("export.csv", CHECKING_CSV, "text/csv")},
        data=refused,
        headers=csrf(owner_client),
    )
    assert response.json()["reconciled_count"] == 2
    assert _transactions(owner_client)[entries["rent"]]["source"] == "manual"


def test_a_malformed_refusal_is_rejected(owner_client: TestClient) -> None:
    account = _account(owner_client)
    response = owner_client.post(
        f"/api/accounts/{account}/imports/preview",
        files={"file": ("export.csv", CHECKING_CSV, "text/csv")},
        data={"refused": "ten:nobody"},
        headers=csrf(owner_client),
    )
    assert response.status_code == 422


def test_rolling_back_gives_the_entries_back(owner_client: TestClient) -> None:
    account = _account(owner_client)
    entries = _entries(owner_client, account)
    before = _transactions(owner_client)
    batch = _send(owner_client, account, CHECKING_CSV).json()

    response = owner_client.delete(f"/api/imports/{batch['id']}", headers=csrf(owner_client))
    assert response.status_code == 204

    after = _transactions(owner_client)
    assert set(after) == set(entries.values())
    for key in ("booked_on", "label", "category_id", "source", "bank_label"):
        assert {i: t[key] for i, t in after.items()} == {i: t[key] for i, t in before.items()}
