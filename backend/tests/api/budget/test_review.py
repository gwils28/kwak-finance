from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.api.budget.test_budget import _account, _category, _matrix, _row
from tests.api.budget.test_plans import _plan, _set
from tests.api.conftest import Clock, csrf, log_in

# The test clock starts on 1 January 2026.


def _spend(client: TestClient, account: str, day: str, amount: str, name: str | None) -> None:
    created = client.post(
        "/api/transactions",
        json={"account_id": account, "booked_on": day, "amount": amount, "label": "x"},
        headers=csrf(client),
    )
    assert created.status_code == 201, created.text
    if name is not None:
        client.post(
            "/api/transactions/categorise",
            json={
                "transaction_ids": [created.json()["id"]],
                "category_id": _category(client, name),
            },
            headers=csrf(client),
        )


def _advance(client: TestClient, clock: Clock, days: int) -> None:
    clock.advance(timedelta(days=days))
    log_in(client, clock)


@pytest.fixture
def q1(owner_client: TestClient, clock: Clock) -> Any:
    """A Q1 2026 plan, Groceries at 300 a month, reviewed on 15 February."""
    plan = _plan(owner_client, "2026-Q1")
    _set(owner_client, plan, "Groceries", "300.00")
    owner_client.patch(
        f"/api/budget/plans/{plan['id']}",
        json={"expected_income": "2000.00"},
        headers=csrf(owner_client),
    )
    _advance(owner_client, clock, 45)
    account = _account(owner_client, opening_date="2025-12-01")
    _spend(owner_client, account, "2026-01-10", "-280.00", "Groceries")
    _spend(owner_client, account, "2026-01-31", "2000.00", "Salary")
    _spend(owner_client, account, "2026-02-05", "-250.00", "Groceries")
    _spend(owner_client, account, "2026-02-12", "-50.00", None)
    plan["account"] = account
    return plan


def _review(client: TestClient, plan: Any) -> Any:
    response = client.get(f"/api/budget/plans/{plan['id']}/review")
    assert response.status_code == 200, response.text
    return response.json()


def test_during_a_plan_the_review_compares_spending_with_the_pace(
    owner_client: TestClient, q1: Any
) -> None:
    review = _review(owner_client, q1)

    assert review["plan"]["period"] == "2026-Q1"
    assert (review["elapsed"], review["finished"]) == ("0.5119", False)  # (1 + 15/28) / 3
    groceries = _row(review, "Groceries")
    assert groceries | {"category_id": None, "parent_id": None} == {
        "category_id": None,
        "name": "Groceries",
        "parent_id": None,
        "level": 1,
        "monthly_target": "300.00",
        "envelope": "900.00",
        "spent": "530.00",
        "gap": "-370.00",
        "gap_ratio": "-0.4111",
        "pace": "460.71",
        "status": "over",
        "projection": "1035.35",
        "drift": "135.35",
        "drifting": True,
        "months_over": 0,
        "months_on": 0,
        "months_under": 1,
        "target_from_children": False,
    }
    assert _row(review, "Food")["target_from_children"] is True
    assert review["drifting"] == [
        _category(owner_client, "Food"),
        _category(owner_client, "Groceries"),
    ]


def test_spending_left_to_categorise_makes_the_review_provisional(
    owner_client: TestClient, q1: Any
) -> None:
    review = _review(owner_client, q1)
    assert (review["uncategorised"], review["provisional"]) == ("50.00", True)
    assert review["total"]["spent"] == "580.00"
    assert (review["income"], review["savings"], review["savings_rate"]) == (
        "2000.00",
        "1420.00",
        "0.7100",
    )
    assert review["planned_savings"] == "5100.00"  # 3 x 2000 - 900


def test_the_review_and_the_matrix_agree(owner_client: TestClient, q1: Any) -> None:
    """Invariant 10: a plan's spending is the sum of the matrix cells of its months."""
    matrix = _matrix(owner_client, start="2026-01", end="2026-03")
    review = _review(owner_client, q1)
    for name in ("Food", "Groceries"):
        cells = _row(matrix, name)["cells"]
        assert sum(float(c["spent"]) for c in cells) == float(_row(review, name)["spent"])
    assert sum(float(c["spent"]) for c in matrix["total"]["cells"]) == float(
        review["total"]["spent"]
    )


def test_after_the_plan_the_review_gives_the_final_result(
    owner_client: TestClient, clock: Clock, q1: Any
) -> None:
    _advance(owner_client, clock, 60)  # 16 April
    review = _review(owner_client, q1)
    assert (review["elapsed"], review["finished"]) == ("1.0000", True)
    groceries = _row(review, "Groceries")
    assert (groceries["pace"], groceries["status"], groceries["drifting"]) == (
        "900.00",
        "under",
        False,
    )
    assert (groceries["months_under"], groceries["months_on"]) == (3, 0)
    assert review["drifting"] == []


def test_the_cumulative_chart_runs_day_by_day_against_the_envelope_line(
    owner_client: TestClient, q1: Any
) -> None:
    url = f"/api/budget/plans/{q1['id']}/cumulative"
    total = owner_client.get(url).json()
    assert total["envelope"] == "900.00"
    points = total["points"]
    assert len(points) == 90
    by_day = {p["day"]: p for p in points}
    assert by_day["2026-01-10"]["spent"] == "280.00"
    assert by_day["2026-01-31"] == {"day": "2026-01-31", "spent": "280.00", "envelope": "300.00"}
    assert by_day["2026-02-15"]["spent"] == "580.00"  # uncategorised outflows count
    assert by_day["2026-02-16"]["spent"] is None  # the future

    food = owner_client.get(url, params={"category_id": _category(owner_client, "Food")}).json()
    assert {p["day"]: p["spent"] for p in food["points"]}["2026-02-15"] == "530.00"


def test_the_cumulative_chart_is_for_an_expense_category(owner_client: TestClient, q1: Any) -> None:
    url = f"/api/budget/plans/{q1['id']}/cumulative"
    salary = _category(owner_client, "Salary")
    assert owner_client.get(url, params={"category_id": salary}).status_code == 422


def test_two_plans_compare_on_monthly_figures(owner_client: TestClient, q1: Any) -> None:
    previous = _plan(owner_client, "2025-Q4")  # pre-filled from Q1: Groceries at 300
    _spend(owner_client, q1["account"], "2025-12-03", "-150.00", "Groceries")

    response = owner_client.get(f"/api/budget/plans/{q1['id']}/comparison")

    assert response.status_code == 200, response.text
    comparison = response.json()
    assert (comparison["a"]["id"], comparison["b"]["id"]) == (previous["id"], q1["id"])
    groceries = _row(comparison, "Groceries")
    assert (groceries["target_a"], groceries["target_b"]) == ("300.00", "300.00")
    assert (groceries["average_a"], groceries["average_b"]) == ("50.00", "345.12")
    assert (groceries["change"], groceries["change_ratio"]) == ("295.12", "5.9024")
    assert comparison["rows"][-1]["name"] == "Total"


def test_any_two_plans_can_be_compared(owner_client: TestClient, q1: Any) -> None:
    other = _plan(owner_client, "2027")
    url = f"/api/budget/plans/{q1['id']}/comparison"
    assert owner_client.get(url, params={"against": other["id"]}).json()["a"]["id"] == other["id"]


def test_the_first_plan_has_nothing_to_compare_with(owner_client: TestClient, q1: Any) -> None:
    response = owner_client.get(f"/api/budget/plans/{q1['id']}/comparison")
    assert response.status_code == 404
    assert response.json()["detail"] == "no earlier budget plan to compare with"


def test_another_households_plan_is_not_reviewed(owner_client: TestClient) -> None:
    url = "/api/budget/plans/0192f0a0-0000-7000-8000-000000000099/review"
    assert owner_client.get(url).status_code == 404
