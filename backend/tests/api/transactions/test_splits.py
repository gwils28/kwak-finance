"""Split transactions and notes (F-TX-4)."""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from kwak_api.models import User

from tests.api.budget.test_budget_month import _account, _add, _category
from tests.api.conftest import Clock, csrf, log_in

MARCH = {"start": "2026-03", "end": "2026-03"}


@pytest.fixture
def owner_client(client: TestClient, clock: Clock, owner: User) -> TestClient:
    log_in(client, clock)
    return client


def _split(client: TestClient, transaction: str, parts: list[tuple[str, str]], rest: str) -> Any:
    body = {
        "parts": [{"category_id": _category(client, c), "amount": a} for c, a in parts],
        "rest_category_id": _category(client, rest),
    }
    return client.put(f"/api/transactions/{transaction}/split", json=body, headers=csrf(client))


def _receipt(client: TestClient) -> tuple[str, str]:
    """A supermarket receipt: groceries, household supplies and the rest at the pharmacy."""
    account = _account(client)
    receipt = _add(client, account, "2026-03-14", "-84.30", "CARREFOUR", None)
    response = _split(
        client, receipt, [("Groceries", "-60.00"), ("Home and garden", "-15.50")], "Pharmacy"
    )
    assert response.status_code == 200, response.text
    return account, receipt


def _listed(client: TestClient, **params: Any) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = client.get("/api/transactions", params=params).json()["items"]
    return items


def _spent(client: TestClient, name: str) -> str:
    matrix = client.get("/api/budget/matrix", params=MARCH).json()
    row = next(r for r in matrix["rows"] if r["name"] == name)
    spent: str = row["cells"][0]["spent"]
    return spent


def test_a_split_transaction_counts_in_each_part_s_category(owner_client: TestClient) -> None:
    _, receipt = _receipt(owner_client)

    [listed] = _listed(owner_client)
    assert listed["id"] == receipt
    assert listed["category_id"] is None
    assert [(p["category_name"], p["amount"]) for p in listed["parts"]] == [
        ("Groceries", "-60.00"),
        ("Home and garden", "-15.50"),
        ("Pharmacy", "-8.80"),
    ]
    assert _spent(owner_client, "Groceries") == "60.00"
    assert _spent(owner_client, "Pharmacy") == "8.80"
    assert _spent(owner_client, "Food") == "60.00"
    total = owner_client.get("/api/budget/matrix", params=MARCH).json()["total"]
    assert total["cells"][0]["spent"] == "84.30"  # counted once (§8.2)
    dashboard = owner_client.get("/api/dashboard", params={"month": "2026-03"}).json()
    assert dashboard["kpis"]["spent"] == "84.30"
    assert dashboard["to_categorise"]["count"] == 0


def test_a_category_filter_finds_a_split_transaction_through_its_parts(
    owner_client: TestClient,
) -> None:
    _, receipt = _receipt(owner_client)

    pharmacy = _listed(owner_client, category_id=_category(owner_client, "Pharmacy"))
    doctors = _listed(owner_client, category_id=_category(owner_client, "Doctors"))

    assert [t["id"] for t in pharmacy] == [receipt]
    assert doctors == []
    assert _listed(owner_client, uncategorised=True) == []


def test_invalid_splits_are_refused(owner_client: TestClient) -> None:
    account = _account(owner_client)
    receipt = _add(owner_client, account, "2026-03-14", "-84.30", "CARREFOUR", None)

    assert _split(owner_client, receipt, [], "Pharmacy").status_code == 422
    assert _split(owner_client, receipt, [("Groceries", "-90.00")], "Pharmacy").status_code == 422
    assert _split(owner_client, receipt, [("Groceries", "10.00")], "Pharmacy").status_code == 422


def test_removing_the_split_brings_the_transaction_back_to_categorise(
    owner_client: TestClient,
) -> None:
    _, receipt = _receipt(owner_client)

    response = owner_client.delete(f"/api/transactions/{receipt}/split", headers=csrf(owner_client))

    assert response.status_code == 200
    assert response.json()["parts"] == []
    assert [t["id"] for t in _listed(owner_client, uncategorised=True)] == [receipt]


def test_a_new_amount_moves_the_last_part(owner_client: TestClient) -> None:
    _, receipt = _receipt(owner_client)
    path = f"/api/transactions/{receipt}"

    moved = owner_client.patch(path, json={"amount": "-90.00"}, headers=csrf(owner_client))
    refused = owner_client.patch(path, json={"amount": "-70.00"}, headers=csrf(owner_client))

    assert moved.status_code == 200
    assert [p["amount"] for p in moved.json()["parts"]] == ["-60.00", "-15.50", "-14.50"]
    assert refused.status_code == 422
    assert _listed(owner_client)[0]["amount"] == "-90.00"


def test_a_split_transaction_keeps_its_parts_against_rules_and_bulk_changes(
    owner_client: TestClient,
) -> None:
    _, receipt = _receipt(owner_client)
    groceries = _category(owner_client, "Groceries")
    owner_client.post(
        "/api/rules",
        json={"category_id": groceries, "label_contains": "CARREFOUR"},
        headers=csrf(owner_client),
    )

    owner_client.post(
        "/api/rules/apply", json={"only_uncategorised": False}, headers=csrf(owner_client)
    )
    bulk = owner_client.post(
        "/api/transactions/categorise",
        json={"transaction_ids": [receipt], "category_id": groceries},
        headers=csrf(owner_client),
    )
    single = owner_client.patch(
        f"/api/transactions/{receipt}", json={"category_id": groceries}, headers=csrf(owner_client)
    )

    assert bulk.json()["updated"] == 0
    assert single.status_code == 409
    [listed] = _listed(owner_client)
    assert listed["category_id"] is None
    assert len(listed["parts"]) == 3


def test_transfers_and_splits_do_not_mix(owner_client: TestClient) -> None:
    account = _account(owner_client)
    savings = _account(owner_client, "Savings")
    out = _add(owner_client, account, "2026-03-10", "-150.00", "VIR EPARGNE", None)
    inn = _add(owner_client, savings, "2026-03-10", "150.00", "VIR RECU", None)
    _split(owner_client, out, [("Groceries", "-100.00")], "Pharmacy")

    assert owner_client.get("/api/transfers/suggestions").json() == []
    linked = owner_client.post(
        "/api/transfers", json={"outflow_id": out, "inflow_id": inn}, headers=csrf(owner_client)
    )
    assert linked.status_code == 422

    owner_client.delete(f"/api/transactions/{out}/split", headers=csrf(owner_client))
    owner_client.post(
        "/api/transfers", json={"outflow_id": out, "inflow_id": inn}, headers=csrf(owner_client)
    )
    assert _split(owner_client, out, [("Groceries", "-100.00")], "Pharmacy").status_code == 409


def test_deleting_a_category_leaves_its_part_to_categorise(owner_client: TestClient) -> None:
    _, receipt = _receipt(owner_client)
    home = _category(owner_client, "Home and garden")

    owner_client.delete(f"/api/categories/{home}", headers=csrf(owner_client))

    [listed] = _listed(owner_client, uncategorised=True)
    assert listed["id"] == receipt
    assert [p["category_id"] for p in listed["parts"]][1] is None
    assert sum(float(p["amount"]) for p in listed["parts"]) == pytest.approx(-84.30)


def test_a_note_is_kept_and_searched(owner_client: TestClient) -> None:
    _, receipt = _receipt(owner_client)

    response = owner_client.patch(
        f"/api/transactions/{receipt}",
        json={"note": "Anniversaire de Léa"},
        headers=csrf(owner_client),
    )

    assert response.status_code == 200
    assert response.json()["note"] == "Anniversaire de Léa"
    assert [t["id"] for t in _listed(owner_client, q="anniversaire de lea")] == [receipt]
    cleared = owner_client.patch(
        f"/api/transactions/{receipt}", json={"note": None}, headers=csrf(owner_client)
    )
    assert cleared.json()["note"] is None


def test_an_imported_transaction_takes_a_note_and_a_split(owner_client: TestClient) -> None:
    from tests.api.transfers.test_transfers import CHECKING_CSV

    account = _account(owner_client)
    files = {"file": ("export.csv", CHECKING_CSV, "text/csv")}
    owner_client.post(f"/api/accounts/{account}/imports", files=files, headers=csrf(owner_client))
    rent = next(t for t in _listed(owner_client) if t["amount"] == "-1250.00")

    noted = owner_client.patch(
        f"/api/transactions/{rent['id']}", json={"note": "March"}, headers=csrf(owner_client)
    )
    split = _split(owner_client, rent["id"], [("Groceries", "-1000.00")], "Pharmacy")

    assert noted.status_code == 200
    assert split.status_code == 200
    assert split.json()["note"] == "March"


def test_a_split_has_at_most_twenty_parts_and_known_categories(owner_client: TestClient) -> None:
    account = _account(owner_client)
    big = _add(owner_client, account, "2026-03-14", "-1000.00", "TRAVAUX", None)
    groceries = _category(owner_client, "Groceries")
    path = f"/api/transactions/{big}/split"
    many = {
        "parts": [{"category_id": groceries, "amount": "-1.00"}] * 20,
        "rest_category_id": groceries,
    }
    unknown = {
        "parts": [{"category_id": "0192f0a0-0000-7000-8000-00000000dead", "amount": "-1.00"}],
        "rest_category_id": groceries,
    }

    assert owner_client.put(path, json=many, headers=csrf(owner_client)).status_code == 422
    assert owner_client.put(path, json=unknown, headers=csrf(owner_client)).status_code == 422
    assert _listed(owner_client)[0]["parts"] == []


def test_a_member_cannot_split_note_or_find_a_private_transaction(
    client: TestClient, clock: Clock, member: User
) -> None:
    log_in(client, clock)
    private = _account(client, "Private")
    client.patch(f"/api/accounts/{private}", json={"visibility": "private"}, headers=csrf(client))
    receipt = _add(client, private, "2026-03-14", "-84.30", "CARREFOUR", None)
    _split(client, receipt, [("Groceries", "-60.00")], "Pharmacy")
    client.patch(f"/api/transactions/{receipt}", json={"note": "Secret"}, headers=csrf(client))

    log_in(client, clock, "member@example.com")
    path = f"/api/transactions/{receipt}"
    assert _split(client, receipt, [("Groceries", "-10.00")], "Pharmacy").status_code == 404
    assert client.delete(f"{path}/split", headers=csrf(client)).status_code == 404
    assert client.patch(path, json={"note": "Mine"}, headers=csrf(client)).status_code == 404
    assert client.get("/api/transactions", params={"q": "secret"}).json()["total"] == 0
    groceries = {"category_id": _category(client, "Groceries")}
    assert client.get("/api/transactions", params=groceries).json()["total"] == 0
    matrix = client.get("/api/budget/matrix", params=MARCH).json()
    assert matrix["total"]["cells"][0]["spent"] == "0.00"


def test_a_split_transaction_follows_its_first_part_s_month_shift(
    owner_client: TestClient,
) -> None:
    from tests.api.budget.test_budget_month import _shift

    account = _account(owner_client)
    _shift(owner_client, "Salary", 25)
    pay = _add(owner_client, account, "2026-03-27", "3000.00", "SALAIRE", "Salary")

    _split(owner_client, pay, [("Salary", "2500.00")], "Other income")

    [listed] = _listed(owner_client)
    assert listed["id"] == pay
    assert listed["budget_month"] == "2026-04"
    assert [t["id"] for t in _listed(owner_client, budget_month="2026-04")] == [pay]


def test_a_split_transaction_counts_once_to_categorise(owner_client: TestClient) -> None:
    _, receipt = _receipt(owner_client)
    _split(owner_client, receipt, [("Home and garden", "-60.00")], "Home and garden")

    owner_client.delete(
        f"/api/categories/{_category(owner_client, 'Home and garden')}", headers=csrf(owner_client)
    )

    dashboard = owner_client.get("/api/dashboard", params={"month": "2026-03"}).json()
    assert dashboard["to_categorise"] == {"count": 1, "spent": "84.30"}


def test_a_rule_preview_leaves_split_transactions_out(owner_client: TestClient) -> None:
    _receipt(owner_client)
    preview = owner_client.post(
        "/api/rules/preview",
        json={"category_id": _category(owner_client, "Groceries"), "label_contains": "CARREFOUR"},
        headers=csrf(owner_client),
    ).json()
    assert (preview["matching"], preview["uncategorised"]) == (0, 0)


def test_reconciling_keeps_the_split_and_the_note_and_rolling_back_too(
    owner_client: TestClient,
) -> None:
    from tests.api.imports.test_imports import CHECKING_CSV, _send

    account = _account(owner_client)
    rent = _add(owner_client, account, "2026-03-08", "-1250.00", "LOYER", None)
    _split(owner_client, rent, [("Rent or mortgage", "-1000.00")], "Home insurance")
    owner_client.patch(
        f"/api/transactions/{rent}", json={"note": "Mars"}, headers=csrf(owner_client)
    )

    def rent_now() -> dict[str, Any]:
        return next(t for t in _listed(owner_client, limit=200) if t["id"] == rent)

    batch = _send(owner_client, account, CHECKING_CSV).json()
    reconciled = rent_now()
    owner_client.delete(f"/api/imports/{batch['id']}", headers=csrf(owner_client))
    restored = rent_now()

    for t in (reconciled, restored):
        assert t["note"] == "Mars"
        assert [p["amount"] for p in t["parts"]] == ["-1000.00", "-250.00"]
    assert (reconciled["source"], restored["source"]) == ("import", "manual")


def test_the_shift_preview_counts_a_split_transaction_by_its_first_part(
    owner_client: TestClient,
) -> None:
    account = _account(owner_client)
    pay = _add(owner_client, account, "2026-03-27", "3000.00", "SALAIRE", None)
    _split(owner_client, pay, [("Salary", "2500.00")], "Other income")

    salary = _category(owner_client, "Salary")
    preview = owner_client.get(f"/api/categories/{salary}/shift-preview", params={"day": 25})

    assert preview.status_code == 200, preview.text
    assert preview.json()["moved"] == 1
