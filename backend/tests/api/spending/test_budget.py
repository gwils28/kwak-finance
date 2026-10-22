from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from kwak_api.models import User

from tests.api.conftest import Clock, csrf, log_in

TODAY = datetime(2026, 10, 21, 12, tzinfo=UTC)


@pytest.fixture
def owner_client(client: TestClient, clock: Clock, owner: User) -> TestClient:
    clock.now = TODAY
    log_in(client, clock)
    return client


def _categories(client: TestClient) -> dict[str, str]:
    return {c["name"]: c["id"] for c in client.get("/api/spending/categories").json()}


def _line(client: TestClient, category: str, amount: str, day: str = "2026-10-05") -> None:
    body = {
        "day": day,
        "label": "x",
        "amount": amount,
        "category_id": _categories(client)[category],
    }
    response = client.post("/api/spending/lines", json=body, headers=csrf(client))
    assert response.status_code == 201, response.text


def _income(client: TestClient, month: str, amount: str) -> None:
    response = client.put(
        f"/api/spending/income/{month}", json={"amount": amount}, headers=csrf(client)
    )
    assert response.status_code == 200, response.text


def _target(client: TestClient, category: str, month: str, amount: str | None) -> Any:
    return client.put(
        f"/api/spending/targets/{_categories(client)[category]}/{month}",
        json={"amount": amount},
        headers=csrf(client),
    )


def _get(client: TestClient, path: str, **params: str) -> Any:
    response = client.get(f"/api/spending{path}", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def _october(client: TestClient) -> None:
    """Income 2000; spent 500 (groceries 300, home 200); saved 500 (600 put aside, 100 back)."""
    _income(client, "2026-10", "2000.00")
    _line(client, "Groceries", "-300.00")
    _line(client, "Home", "-200.00")
    _line(client, "Savings", "-600.00")
    _line(client, "Savings", "100.00")


# Targets (F-BUD-1, 9)


def test_a_target_is_kept_from_its_month_until_changed(owner_client: TestClient) -> None:
    assert _target(owner_client, "Groceries", "2026-01", "400.00").status_code == 200
    assert _target(owner_client, "Groceries", "2026-10", "500.00").status_code == 200
    assert _target(owner_client, "Leisure", "2026-03", None).status_code == 200
    groceries = _categories(owner_client)["Groceries"]
    targets = _get(owner_client, "/targets")
    assert [(t["from_month"], t["amount"]) for t in targets if t["category_id"] == groceries] == [
        ("2026-01", "400.00"),
        ("2026-10", "500.00"),
    ]
    response = owner_client.delete(
        f"/api/spending/targets/{groceries}/2026-10", headers=csrf(owner_client)
    )
    assert response.status_code == 204
    assert len([t for t in _get(owner_client, "/targets") if t["category_id"] == groceries]) == 1


def test_a_target_is_zero_or_more(owner_client: TestClient) -> None:
    assert _target(owner_client, "Groceries", "2026-10", "-1.00").status_code == 422


# The month (F-DSH-4, F-BUD-2, F-FIX-4)


def test_the_month_figures_progress_and_projected_rest(owner_client: TestClient) -> None:
    _october(owner_client)
    _target(owner_client, "Groceries", "2026-01", "400.00")
    _target(owner_client, "Home", "2026-01", "150.00")
    body = {
        "label": "Rent",
        "category_id": _categories(owner_client)["Housing"],
        "amount": "-950.00",
        "frequency": "monthly",
        "day": 28,
        "first_month": "2026-10",
    }
    owner_client.post("/api/spending/fixed", json=body, headers=csrf(owner_client))

    month = _get(owner_client, "/month", month="2026-10")
    figures = month["figures"]
    assert (figures["income"], figures["spent"], figures["saved"], figures["rest"]) == (
        "2000.00",
        "500.00",
        "500.00",
        "1000.00",
    )
    assert (figures["savings_rate"], month["income_carried"]) == ("0.7500", False)
    assert (month["projected_rest"], month["to_confirm"]) == ("50.00", 1)
    cats = _categories(owner_client)
    assert [(t["category_id"], t["spent"], t["share"]) for t in month["top"]] == [
        (cats["Groceries"], "300.00", "0.6000"),
        (cats["Home"], "200.00", "0.4000"),
    ]
    progress = month["progress"]
    assert progress["warn_at"] == "0.80"
    assert [(p["name"], p["status"]) for p in progress["lines"]] == [
        ("Home", "over"),
        ("Groceries", "on_track"),
    ]
    assert progress["lines"][1]["pace"] == "0.6774"  # 21 / 31


def test_changes_against_the_previous_month_and_the_average(owner_client: TestClient) -> None:
    _income(owner_client, "2026-08", "1000.00")
    _line(owner_client, "Groceries", "-100.00", "2026-08-10")
    _line(owner_client, "Groceries", "-300.00", "2026-09-10")  # income carried: 1000
    _line(owner_client, "Groceries", "-400.00", "2026-10-10")
    month = _get(owner_client, "/month", month="2026-10")
    assert month["income_carried"] is True
    assert month["previous"]["spent"] == "300.00"
    assert month["average"]["spent"] == "200.00"  # August and September only
    assert month["changes"]["vs_previous"]["spent"] == "0.3333"
    assert month["changes"]["vs_average"]["spent"] == "1.0000"


def test_an_empty_household_has_no_average(owner_client: TestClient) -> None:
    month = _get(owner_client, "/month", month="2026-10")
    assert month["average"] is None
    assert month["figures"]["income"] == "0.00"


# Matrix (F-BUD-6) and year (F-BUD-10)


def test_the_matrix_by_month_with_savings_and_totals(owner_client: TestClient) -> None:
    _october(owner_client)
    _target(owner_client, "Groceries", "2026-01", "400.00")
    _target(owner_client, "Savings", "2026-01", "500.00")
    matrix = _get(owner_client, "/matrix", first="2026-09", last="2026-10")
    assert matrix["months"] == ["2026-09", "2026-10"]
    groceries = next(r for r in matrix["rows"] if r["name"] == "Groceries")
    assert [(c["spent"], c["target"], c["status"]) for c in groceries["cells"]] == [
        ("0.00", "400.00", "under"),
        ("300.00", "400.00", "under"),
    ]
    (savings,) = matrix["savings"]
    assert (savings["cells"][1]["spent"], savings["cells"][1]["status"]) == ("500.00", "on")
    assert matrix["total"]["cells"][1]["spent"] == "500.00"
    assert [f["rest"] for f in matrix["figures"]] == ["0.00", "1000.00"]


def test_the_matrix_period_is_checked(owner_client: TestClient) -> None:
    response = owner_client.get(
        "/api/spending/matrix", params={"first": "2026-10", "last": "2026-09"}
    )
    assert response.status_code == 422


def test_the_year_to_date(owner_client: TestClient) -> None:
    _october(owner_client)
    _line(owner_client, "Groceries", "-450.00", "2026-09-10")
    _target(owner_client, "Groceries", "2026-01", "400.00")
    _target(owner_client, "Savings", "2026-07", "300.00")
    year = _get(owner_client, "/year", year="2026")
    groceries = next(r for r in year["expenses"] if r["name"] == "Groceries")
    assert (groceries["target_to_date"], groceries["target_full"], groceries["spent_to_date"]) == (
        "4000.00",
        "4800.00",
        "750.00",
    )
    assert (groceries["status"], groceries["above"], groceries["below"]) == ("under", 1, 8)
    (savings,) = year["savings"]
    assert (savings["target_to_date"], savings["spent_to_date"]) == ("1200.00", "500.00")
    assert (year["totals"]["income"], year["totals"]["spent"]) == ("2000.00", "950.00")


def test_the_month_adds_up_its_spending_day_by_day(owner_client: TestClient) -> None:
    """F-DSH-5: every day of the month, savings left out, against the targets added up."""
    _october(owner_client)
    _line(owner_client, "Groceries", "-50.00", day="2026-10-20")
    _target(owner_client, "Groceries", "2026-01", "400.00")
    _target(owner_client, "Home", "2026-01", "150.00")
    month = _get(owner_client, "/month", month="2026-10")

    days = month["cumulative"]
    assert len(days) == 31
    assert days[0] == {"day": "2026-10-01", "spent": "0.00"}
    assert days[4] == {"day": "2026-10-05", "spent": "500.00"}
    assert days[19] == {"day": "2026-10-20", "spent": "550.00"}
    assert days[-1]["spent"] == month["figures"]["spent"] == "550.00"
    # A split line counts its expense parts on its day, its savings part never.
    categories = _categories(owner_client)
    split = {
        "day": "2026-10-25",
        "label": "Supermarket",
        "amount": "-100.00",
        "split": {
            "parts": [{"category_id": categories["Groceries"], "amount": "-30.00"}],
            "rest_category_id": categories["Savings"],
        },
    }
    response = owner_client.post("/api/spending/lines", json=split, headers=csrf(owner_client))
    assert response.status_code == 201, response.text
    days = _get(owner_client, "/month", month="2026-10")["cumulative"]
    assert days[23]["spent"] == "550.00"
    assert days[24]["spent"] == days[-1]["spent"] == "580.00"
    assert month["target_total"] == "550.00"
    assert _get(owner_client, "/month", month="2026-09")["target_total"] == "550.00"
    _target(owner_client, "Groceries", "2026-01", None)
    _target(owner_client, "Home", "2026-01", None)
    assert _get(owner_client, "/month", month="2026-09")["target_total"] is None
