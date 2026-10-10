from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from kwak_api.models import User

from tests.api.budget.test_budget import _target
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


def _setup(client: TestClient) -> None:
    body = {
        "name": "Compte courant",
        "institution_name": "SG",
        "type": "checking",
        "visibility": "shared",
        "opening_balance": "0",
        "opening_date": "2026-03-01",
    }
    account = client.post("/api/accounts", json=body, headers=csrf(client)).json()["id"]
    files = {"file": ("export.csv", CHECKING_CSV, "text/csv")}
    client.post(f"/api/accounts/{account}/imports", files=files, headers=csrf(client))
    items = client.get("/api/transactions").json()["items"]
    for name, words in (("Bakery and coffee", ("BOULANGERIE", "CAFE")), ("Salary", ("SALAIRE",))):
        ids = [t["id"] for t in items if any(w in t["label"] for w in words)]
        client.post(
            "/api/transactions/categorise",
            json={"transaction_ids": ids, "category_id": _category(client, name)},
            headers=csrf(client),
        )


def _dashboard(client: TestClient, **params: str) -> Any:
    response = client.get("/api/dashboard", params={"month": "2026-03", **params})
    assert response.status_code == 200, response.text
    return response.json()


def test_the_months_kpis(owner_client: TestClient) -> None:
    _setup(owner_client)
    kpis = _dashboard(owner_client)["kpis"]

    assert kpis["spent"] == "1621.04"
    assert kpis["income"] == "2518.65"  # salary plus uncategorised inflows
    assert kpis["net"] == "897.61"  # = the sum of the month's transactions
    assert kpis["savings_rate"] == "0.3564"
    assert kpis["previous_spent"] == "0.00"
    assert kpis["spent_change_vs_previous"] is None  # nothing to compare with


def test_top_categories_and_what_is_left_to_categorise(owner_client: TestClient) -> None:
    _setup(owner_client)
    dashboard = _dashboard(owner_client)

    assert dashboard["top_categories"][0] == {
        "category_id": _category(owner_client, "Food"),
        "name": "Food",
        "spent": "6.40",
        "share": "0.0039",
    }
    assert dashboard["to_categorise"] == {"count": 10, "spent": "1614.64"}


def test_twelve_months_of_spending_by_category_and_income(owner_client: TestClient) -> None:
    _setup(owner_client)
    monthly = _dashboard(owner_client)["monthly"]

    assert [m["month"] for m in monthly][-2:] == ["2026-02", "2026-03"]
    assert len(monthly) == 12
    march = monthly[-1]
    assert (march["spent"], march["income"]) == ("1621.04", "2518.65")
    assert {"name": "Food", "spent": "6.40"} in [
        {"name": c["name"], "spent": c["spent"]} for c in march["by_category"]
    ]
    assert monthly[0]["spent"] == "0.00"


def test_cumulative_spending_through_the_month_against_the_target(owner_client: TestClient) -> None:
    _setup(owner_client)
    _target(owner_client, "Groceries", "400.00")
    dashboard = _dashboard(owner_client)
    cumulative = dashboard["cumulative"]

    assert len(cumulative) == 31
    assert cumulative[0] == {"day": "2026-03-01", "spent": "12.30"}
    assert cumulative[-1]["spent"] == "1621.04"
    assert dashboard["budget_target"] == "400.00"


def test_the_month_defaults_to_this_month(owner_client: TestClient) -> None:
    response = owner_client.get("/api/dashboard")
    assert response.json()["month"] == "2026-01"  # the test clock


def test_a_bad_month_is_rejected(owner_client: TestClient) -> None:
    assert owner_client.get("/api/dashboard", params={"month": "2026-13"}).status_code == 422


def test_the_dashboard_requires_a_full_sign_in(client: TestClient) -> None:
    assert client.get("/api/dashboard").status_code == 401


def test_the_average_ignores_months_before_any_data(owner_client: TestClient) -> None:
    _setup(owner_client)  # data only in March 2026
    account = owner_client.get("/api/accounts").json()[0]["id"]
    owner_client.post(
        "/api/transactions",
        json={
            "account_id": account,
            "booked_on": "2026-04-10",
            "amount": "-100.00",
            "label": "April",
        },
        headers=csrf(owner_client),
    )
    kpis = _dashboard(owner_client, month="2026-04")["kpis"]
    # Only March had data before April: the average is March's spending, not a 12th of it.
    assert kpis["average_spent"] == "1621.04"
