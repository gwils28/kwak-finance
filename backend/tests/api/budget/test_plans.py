from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.api.budget.test_budget import _category, _matrix, _row
from tests.api.conftest import Clock, csrf, log_in

# The test clock starts on 1 January 2026.
Q1 = {"start": "2026-01", "end": "2026-04"}


def _create(client: TestClient, period: str, **extra: Any) -> Any:
    return client.post("/api/budget/plans", json={"period": period, **extra}, headers=csrf(client))


def _plan(client: TestClient, period: str) -> Any:
    response = _create(client, period)
    assert response.status_code == 201, response.text
    return response.json()


def _set(client: TestClient, plan: Any, name: str, amount: str | None) -> Any:
    return client.put(
        f"/api/budget/plans/{plan['id']}/targets/{_category(client, name)}",
        json={"amount": amount},
        headers=csrf(client),
    )


def _next_month(client: TestClient, clock: Clock) -> None:
    """1 February: past the first month of a Q1 plan. The session has expired by then."""
    clock.advance(timedelta(days=31))
    log_in(client, clock)


def _plans(client: TestClient) -> Any:
    return client.get("/api/budget/plans").json()


def test_a_plan_covers_its_calendar_period(owner_client: TestClient) -> None:
    plan = _plan(owner_client, "2026-Q1")
    assert plan | {"id": None} == {
        "id": None,
        "period": "2026-Q1",
        "kind": "quarter",
        "start": "2026-01",
        "end": "2026-03",
        "targets": [],
        "expected_income": None,
        "note": None,
        "closed_early": False,
        "close_reason": None,
        "editable": True,
    }


def test_the_matrix_takes_its_targets_from_the_plans(owner_client: TestClient) -> None:
    plan = _plan(owner_client, "2026-Q1")
    response = _set(owner_client, plan, "Groceries", "400.00")
    assert response.status_code == 200, response.text
    assert response.json()["targets"] == [
        {"category_id": _category(owner_client, "Groceries"), "amount": "400.00"}
    ]
    cells = _row(_matrix(owner_client, **Q1), "Groceries")["cells"]
    assert [c["target"] for c in cells] == ["400.00", "400.00", "400.00", None]


def test_a_target_can_be_removed_from_a_plan(owner_client: TestClient) -> None:
    plan = _plan(owner_client, "2026-Q1")
    _set(owner_client, plan, "Groceries", "400.00")
    assert _set(owner_client, plan, "Groceries", None).json()["targets"] == []


def test_a_new_plan_is_prefilled_from_the_latest_one(owner_client: TestClient) -> None:
    q1 = _plan(owner_client, "2026-Q1")
    _set(owner_client, q1, "Groceries", "400.00")
    owner_client.patch(
        f"/api/budget/plans/{q1['id']}",
        json={"expected_income": "3000.00", "note": "first plan"},
        headers=csrf(owner_client),
    )
    s2 = _plan(owner_client, "2026-S2")
    assert [t["amount"] for t in s2["targets"]] == ["400.00"]
    assert s2["expected_income"] == "3000.00"
    assert s2["note"] is None
    assert [p["period"] for p in _plans(owner_client)] == ["2026-Q1", "2026-S2"]


def test_plans_cannot_overlap(owner_client: TestClient) -> None:
    _plan(owner_client, "2026-Q1")
    response = _create(owner_client, "2026")
    assert response.status_code == 409
    assert response.json()["detail"] == "budget plans overlap: 2026 and 2026-Q1"


@pytest.mark.parametrize("period", ["2026-Q5", "2026-T1", "26"])
def test_unknown_periods_are_rejected(owner_client: TestClient, period: str) -> None:
    assert _create(owner_client, period).status_code == 422


@pytest.mark.parametrize(
    ("name", "amount"), [("Salary", "100"), ("Groceries", "-1"), ("Groceries", "1.234")]
)
def test_invalid_targets_are_rejected(owner_client: TestClient, name: str, amount: str) -> None:
    plan = _plan(owner_client, "2026-Q1")
    assert _set(owner_client, plan, name, amount).status_code == 422


def test_after_its_first_month_a_plan_is_changed_by_closing_it_early(
    owner_client: TestClient, clock: Clock
) -> None:
    plan = _plan(owner_client, "2026-Q1")
    _set(owner_client, plan, "Groceries", "400.00")
    _next_month(owner_client, clock)

    refused = _set(owner_client, plan, "Groceries", "300.00")
    assert refused.status_code == 409
    assert refused.json()["detail"] == (
        "this plan can no longer be edited: close it early to change its targets"
    )
    assert _plans(owner_client)[0]["editable"] is False

    closed = owner_client.post(
        f"/api/budget/plans/{plan['id']}/close",
        json={"last_month": "2026-01", "reason": "job loss"},
        headers=csrf(owner_client),
    )
    assert closed.status_code == 200, closed.text
    first, rest = _plans(owner_client)
    assert (first["start"], first["end"], first["closed_early"]) == ("2026-01", "2026-01", True)
    assert first["close_reason"] == "job loss"
    assert (rest["period"], rest["start"], rest["end"]) == ("2026-Q1", "2026-02", "2026-03")
    assert rest["editable"] is True
    assert closed.json() == rest

    _set(owner_client, rest, "Groceries", "300.00")
    cells = _row(_matrix(owner_client, **Q1), "Groceries")["cells"]
    assert [c["target"] for c in cells] == ["400.00", "300.00", "300.00", None]


@pytest.mark.parametrize("last_month", ["2025-12", "2026-03", "2026-13"])
def test_a_plan_closes_early_on_one_of_its_months_but_the_last(
    owner_client: TestClient, last_month: str
) -> None:
    plan = _plan(owner_client, "2026-Q1")
    response = owner_client.post(
        f"/api/budget/plans/{plan['id']}/close",
        json={"last_month": last_month},
        headers=csrf(owner_client),
    )
    assert response.status_code == 422


def test_only_an_editable_plan_can_be_deleted(owner_client: TestClient, clock: Clock) -> None:
    q1, q2 = _plan(owner_client, "2026-Q1"), _plan(owner_client, "2026-Q2")
    assert (
        owner_client.delete(f"/api/budget/plans/{q2['id']}", headers=csrf(owner_client)).status_code
        == 204
    )
    _next_month(owner_client, clock)
    response = owner_client.delete(f"/api/budget/plans/{q1['id']}", headers=csrf(owner_client))
    assert response.status_code == 409
    assert [p["period"] for p in _plans(owner_client)] == ["2026-Q1"]


def test_the_expected_income_is_frozen_with_the_targets_but_the_note_is_not(
    owner_client: TestClient, clock: Clock
) -> None:
    plan = _plan(owner_client, "2026-Q1")
    _next_month(owner_client, clock)
    url = f"/api/budget/plans/{plan['id']}"
    assert (
        owner_client.patch(url, json={"note": "tight"}, headers=csrf(owner_client)).json()["note"]
        == "tight"
    )
    frozen = owner_client.patch(url, json={"expected_income": "1"}, headers=csrf(owner_client))
    assert frozen.status_code == 409


def test_an_unknown_plan_is_not_found(owner_client: TestClient) -> None:
    url = "/api/budget/plans/0192f0a0-0000-7000-8000-000000000099"
    assert owner_client.delete(url, headers=csrf(owner_client)).status_code == 404


def test_plans_require_a_full_sign_in(client: TestClient) -> None:
    assert client.get("/api/budget/plans").status_code == 401
