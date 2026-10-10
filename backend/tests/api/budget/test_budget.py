from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.api.conftest import Clock, csrf, log_in

CHECKING_CSV = (
    Path(__file__).parents[2] / "fixtures" / "import" / "societe_generale" / "checking.csv"
).read_bytes()
MARCH = {"start": "2026-02", "end": "2026-03"}


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


def _import_and_categorise(client: TestClient) -> str:
    account = _account(client)
    files = {"file": ("export.csv", CHECKING_CSV, "text/csv")}
    client.post(f"/api/accounts/{account}/imports", files=files, headers=csrf(client))
    items = client.get("/api/transactions").json()["items"]
    bakery = _category(client, "Bakery and coffee")
    ids = [t["id"] for t in items if "BOULANGERIE" in t["label"] or "CAFE" in t["label"]]
    client.post(
        "/api/transactions/categorise",
        json={"transaction_ids": ids, "category_id": bakery},
        headers=csrf(client),
    )
    salary = [t["id"] for t in items if "SALAIRE" in t["label"]]
    client.post(
        "/api/transactions/categorise",
        json={"transaction_ids": salary, "category_id": _category(client, "Salary")},
        headers=csrf(client),
    )
    return account


def _target(client: TestClient, name: str, amount: str | None, period: str = "2026-Q1") -> Any:
    """Set the category's monthly target in the plan over `period`, creating it if needed."""
    plan = (
        next((p for p in client.get("/api/budget/plans").json() if p["period"] == period), None)
        or client.post("/api/budget/plans", json={"period": period}, headers=csrf(client)).json()
    )
    return client.put(
        f"/api/budget/plans/{plan['id']}/targets/{_category(client, name)}",
        json={"amount": amount},
        headers=csrf(client),
    )


def _matrix(client: TestClient, **params: str) -> Any:
    response = client.get("/api/budget/matrix", params=params or MARCH)
    assert response.status_code == 200, response.text
    return response.json()


def _row(matrix: Any, name: str) -> Any:
    return next(r for r in matrix["rows"] if r["name"] == name)


def test_a_cell_compares_the_months_spending_with_its_target(owner_client: TestClient) -> None:
    _import_and_categorise(owner_client)
    assert _target(owner_client, "Bakery and coffee", "6.00").status_code == 200

    matrix = _matrix(owner_client)

    assert matrix["months"] == ["2026-02", "2026-03"]
    bakery = _row(matrix, "Bakery and coffee")
    assert bakery["target"] == "6.00"
    assert bakery["level"] == 1
    assert bakery["cells"][1] == {
        "month": "2026-03",
        "spent": "6.40",
        "target": "6.00",
        "gap": "0.40",
        "gap_ratio": "0.0667",
        "status": "over",
    }
    assert bakery["cells"][0]["status"] == "under"  # nothing spent in February


def test_parents_add_their_subcategories(owner_client: TestClient) -> None:
    _import_and_categorise(owner_client)
    food = _row(_matrix(owner_client), "Food")
    assert food["level"] == 0
    assert food["cells"][1]["spent"] == "6.40"


def test_refunds_reduce_a_categorys_spending(owner_client: TestClient) -> None:
    account = _import_and_categorise(owner_client)
    owner_client.post(
        "/api/transactions",
        json={
            "account_id": account,
            "booked_on": "2026-03-20",
            "amount": "1.10",
            "label": "Coffee refund",
        },
        headers=csrf(owner_client),
    )
    refund = next(
        t
        for t in owner_client.get("/api/transactions").json()["items"]
        if t["label"] == "Coffee refund"
    )
    owner_client.patch(
        f"/api/transactions/{refund['id']}",
        json={"category_id": _category(owner_client, "Bakery and coffee")},
        headers=csrf(owner_client),
    )
    assert _row(_matrix(owner_client), "Bakery and coffee")["cells"][1]["spent"] == "5.30"


def test_income_stays_out_and_uncategorised_spending_has_its_row(owner_client: TestClient) -> None:
    _import_and_categorise(owner_client)
    matrix = _matrix(owner_client)

    assert all(r["name"] not in {"Income", "Salary"} for r in matrix["rows"])
    # Every outflow of the fixture: 1 621.04 €, of which 6.40 € is categorised.
    assert matrix["uncategorised"]["cells"][1]["spent"] == "1614.64"
    assert matrix["total"]["cells"][1]["spent"] == "1621.04"


def test_the_band_is_a_parameter(owner_client: TestClient) -> None:
    _import_and_categorise(owner_client)
    _target(owner_client, "Bakery and coffee", "6.00")
    wide = _matrix(owner_client, **MARCH, band="0.10")
    assert _row(wide, "Bakery and coffee")["cells"][1]["status"] == "on"


def test_the_default_range_is_the_last_12_months(owner_client: TestClient) -> None:
    months = _matrix(owner_client, scope="household")["months"]  # the test clock is in January 2026
    assert months[0] == "2025-02"
    assert months[-1] == "2026-01"
    assert len(months) == 12


@pytest.mark.parametrize(
    "params",
    [
        {"start": "2026-03", "end": "2026-02"},
        {"start": "2023-01", "end": "2026-03"},
        {"start": "March", "end": "2026-03"},
    ],
)
def test_invalid_ranges_are_rejected(owner_client: TestClient, params: dict[str, str]) -> None:
    assert owner_client.get("/api/budget/matrix", params=params).status_code == 422


@pytest.mark.usefixtures("member")
def test_scope_mine_keeps_only_my_accounts(client: TestClient, clock: Clock) -> None:
    log_in(client, clock)
    _import_and_categorise(client)  # the owner's shared account

    log_in(client, clock, "member@example.com")
    assert _matrix(client, **MARCH)["total"]["cells"][1]["spent"] == "1621.04"
    assert _matrix(client, **MARCH, scope="mine")["total"]["cells"][1]["spent"] == "0.00"


def test_budget_requires_a_full_sign_in(client: TestClient) -> None:
    assert client.get("/api/budget/matrix").status_code == 401
