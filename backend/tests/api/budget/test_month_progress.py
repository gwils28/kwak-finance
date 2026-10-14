"""The month so far (F-BUD-2), one-off categories (F-CAT-6) and the warning threshold."""

from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.api.budget.test_budget_month import _account, _add, _category
from tests.api.conftest import Clock, csrf, log_in

# The test clock starts on 1 January 2026.


def _target(client: TestClient, plan: Any, name: str, amount: str) -> None:
    response = client.put(
        f"/api/budget/plans/{plan['id']}/targets/{_category(client, name)}",
        json={"amount": amount},
        headers=csrf(client),
    )
    assert response.status_code == 200, response.text


def _progress(client: TestClient, **params: str) -> Any:
    response = client.get("/api/budget/progress", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def _one_off(client: TestClient, name: str, value: bool | None) -> Any:
    return client.patch(
        f"/api/categories/{_category(client, name)}",
        json={"one_off": value},
        headers=csrf(client),
    )


def _january(client: TestClient) -> None:
    plan = client.post("/api/budget/plans", json={"period": "2026-Q1"}, headers=csrf(client)).json()
    _target(client, plan, "Food", "400.00")
    _target(client, plan, "Rent or mortgage", "900.00")
    _target(client, plan, "Sports", "50.00")
    account = _account(client)
    _add(client, account, "2026-01-01", "-300.00", "SUPERMARCHE", "Groceries")
    _add(client, account, "2026-01-01", "-40.00", "BOULANGERIE", "Bakery and coffee")
    _add(client, account, "2026-01-01", "-900.00", "LOYER", "Rent or mortgage")
    _add(client, account, "2026-01-01", "-80.00", "CINEMA", "Culture")  # no target


def test_the_month_so_far_ranks_the_categories_with_a_target(owner_client: TestClient) -> None:
    _january(owner_client)

    progress = _progress(owner_client)
    assert progress["month"] == "2026-01"
    assert progress["plan"] == "2026-Q1"
    assert progress["warn_at"] == "0.80"
    lines = progress["lines"]
    assert [line["name"] for line in lines] == ["Rent or mortgage", "Food", "Sports"]
    rent, food, sports = lines
    assert rent | {"category_id": None} == {
        "category_id": None,
        "name": "Rent or mortgage",
        "parent_id": _category(owner_client, "Housing"),
        "spent": "900.00",
        "target": "900.00",
        "remaining": "0.00",
        "share": "1.0000",
        "status": "on_track",  # one-off: paid as planned, nothing to watch
        "pace": None,  # Housing is one-off by default, and Rent follows it
    }
    assert (food["spent"], food["remaining"], food["share"]) == ("340.00", "60.00", "0.8500")
    assert food["pace"] == "0.0323"  # 1 January: 1/31 of the month
    assert sports["status"] == "on_track"


def test_the_month_so_far_agrees_with_the_matrix(owner_client: TestClient) -> None:
    _january(owner_client)
    matrix = owner_client.get(
        "/api/budget/matrix", params={"start": "2026-01", "end": "2026-01"}
    ).json()
    cells = {r["category_id"]: r["cells"][0]["spent"] for r in matrix["rows"]}
    for line in _progress(owner_client)["lines"]:
        assert line["spent"] == cells[line["category_id"]]


def test_a_month_outside_any_plan_has_no_lines(owner_client: TestClient) -> None:
    _january(owner_client)
    progress = _progress(owner_client, month="2026-04")
    assert (progress["plan"], progress["lines"]) == (None, [])


def test_a_past_month_has_no_pace(owner_client: TestClient, clock: Clock) -> None:
    _january(owner_client)
    clock.advance(timedelta(days=40))
    log_in(owner_client, clock)
    food = next(
        line for line in _progress(owner_client, month="2026-01")["lines"] if line["name"] == "Food"
    )
    assert food["pace"] is None


def test_a_category_is_one_off_like_its_parent_unless_it_says_otherwise(
    owner_client: TestClient,
) -> None:
    categories = {c["name"]: c for c in owner_client.get("/api/categories").json()}
    assert categories["Housing"]["one_off"] is True
    assert categories["Subscriptions"]["one_off"] is True
    assert categories["Rent or mortgage"]["one_off"] is None
    assert categories["Food"]["one_off"] is None

    _january(owner_client)
    assert _one_off(owner_client, "Rent or mortgage", False).json()["one_off"] is False
    rent = next(r for r in _progress(owner_client)["lines"] if r["name"] == "Rent or mortgage")
    assert rent["pace"] == "0.0323"


def test_only_an_expense_category_can_be_one_off(owner_client: TestClient) -> None:
    assert _one_off(owner_client, "Salary", True).status_code == 422
    assert _one_off(owner_client, "Investments", True).status_code == 422


def test_the_owner_sets_the_warning_threshold(owner_client: TestClient) -> None:
    assert owner_client.get("/api/household/settings").json()["warn_at"] == "0.80"

    response = owner_client.patch(
        "/api/household/settings", json={"warn_at": "0.9"}, headers=csrf(owner_client)
    )
    assert response.status_code == 200, response.text
    assert response.json()["warn_at"] == "0.90"
    _january(owner_client)
    progress = _progress(owner_client)
    assert progress["warn_at"] == "0.90"
    food = next(line for line in progress["lines"] if line["name"] == "Food")
    assert food["status"] == "on_track"  # 85 % < 90 %


@pytest.mark.parametrize("value", ["0.49", "1.01", "0.855"])
def test_the_warning_threshold_is_a_whole_percentage_from_50_to_100(
    owner_client: TestClient, value: str
) -> None:
    response = owner_client.patch(
        "/api/household/settings", json={"warn_at": value}, headers=csrf(owner_client)
    )
    assert response.status_code == 422


@pytest.mark.usefixtures("member")
def test_only_the_owner_changes_the_threshold(client: TestClient, clock: Clock) -> None:
    log_in(client, clock, "member@example.com")
    assert client.get("/api/household/settings").json()["warn_at"] == "0.80"
    response = client.patch(
        "/api/household/settings", json={"warn_at": "0.9"}, headers=csrf(client)
    )
    assert response.status_code == 403
