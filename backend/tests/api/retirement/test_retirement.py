"""Retirement (spec §4.13): each member enters their own, any member the household's settings,
and the plan read from the household."""

from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from kwak_api.models import User
from kwak_api.services import retirement
from sqlalchemy.orm import Session

from tests.api.conftest import Clock, csrf, log_in
from tests.api.wealth.test_wealth import TODAY, _categories, _line, _value

D = Decimal
MINE = {
    "birth": "1960-12",
    "retirement": "2026-12",
    "earnings": "0",
    "pension_month": None,
    "pension": "1000.00",
}


@pytest.fixture
def owner_client(client: TestClient, clock: Clock, owner: User) -> TestClient:
    clock.now = TODAY
    log_in(client, clock)
    return client


def _get(client: TestClient) -> dict[str, Any]:
    response = client.get("/api/retirement")
    assert response.status_code == 200, response.text
    out: dict[str, Any] = response.json()
    return out


def _mine(client: TestClient, **body: Any) -> Any:
    return client.put("/api/retirement/me", json=MINE | body, headers=csrf(client))


def _settings(client: TestClient, **body: Any) -> Any:
    return client.patch("/api/retirement/settings", json=body, headers=csrf(client))


def test_a_new_household_has_the_defaults_and_no_retirement(owner_client: TestClient) -> None:
    out = _get(owner_client)
    [me] = out["members"]
    assert me | {"user_id": None} == {
        "user_id": None,
        "display_name": "Owner",
        "me": True,
        "birth": None,
        "retirement": None,
        "earnings": None,
        "pension_month": None,
        "pension": None,
        "age_at_retirement": None,
        "age_at_pension": None,
    }
    assert out["settings"] == {
        "spending_share": "0.80",
        "spending_amount": None,
        "indexation": "-0.003",
        "horizon_age": 95,
        "default_spending_share": "0.80",
        "default_indexation": "-0.003",
        "default_horizon_age": 95,
    }
    assert out["spending"] | {"months": None} == {
        "average": "0.00",
        "debt_payments": "0.00",
        "base": "0.00",
        "retirement_spending": "0.00",
        "months": None,
    }


def test_a_member_enters_their_own_retirement(owner_client: TestClient) -> None:
    response = _mine(
        owner_client,
        birth="1990-03",
        retirement="2054-03",
        earnings="2500.00",
        pension_month="2056-03",
        pension="1800.00",
    )
    assert response.status_code == 200, response.text
    [me] = _get(owner_client)["members"]
    assert (me["birth"], me["retirement"], me["pension_month"]) == ("1990-03", "2054-03", "2056-03")
    assert (me["earnings"], me["pension"]) == ("2500.00", "1800.00")
    assert (me["age_at_retirement"], me["age_at_pension"]) == (64, 66)
    # Without a pension month, the pension starts with the retirement.
    _mine(owner_client, birth="1990-03", retirement="2054-03")
    assert _get(owner_client)["members"][0]["pension_month"] == "2054-03"

    deleted = owner_client.delete("/api/retirement/me", headers=csrf(owner_client))
    assert deleted.status_code == 204
    assert _get(owner_client)["members"][0]["birth"] is None


@pytest.mark.parametrize(
    "body",
    [
        {"pension_month": "2026-11"},  # before the retirement
        {"birth": "2027-01"},  # born after retiring
        {"pension": "-5"},
        {"earnings": "10.001"},
        {"birth": "1960-13"},
    ],
)
def test_an_impossible_retirement_is_refused(
    owner_client: TestClient, body: dict[str, Any]
) -> None:
    assert _mine(owner_client, **body).status_code == 422


def test_members_see_each_others_retirement_and_change_only_their_own(
    owner_client: TestClient, clock: Clock, member: User
) -> None:
    _mine(owner_client)
    owner_client.post("/api/auth/logout", headers=csrf(owner_client))
    log_in(owner_client, clock, "member@example.com")
    members = {m["display_name"]: m for m in _get(owner_client)["members"]}
    assert members["Owner"]["pension"] == "1000.00"
    assert not members["Owner"]["me"]
    assert members["Member"]["me"]
    assert members["Member"]["birth"] is None


def test_the_settings_are_the_households_and_return_to_their_defaults(
    owner_client: TestClient,
) -> None:
    assert _settings(owner_client, spending_share="0.9", indexation="-0.005").status_code == 200
    settings = _get(owner_client)["settings"]
    assert (settings["spending_share"], settings["indexation"]) == ("0.90", "-0.005")
    # An amount replaces the share.
    _settings(owner_client, spending_amount="3000.00", horizon_age=90)
    settings = _get(owner_client)["settings"]
    assert (settings["spending_share"], settings["spending_amount"]) == (None, "3000.00")
    assert settings["horizon_age"] == 90
    _settings(owner_client, spending_amount=None, indexation=None, horizon_age=None)
    settings = _get(owner_client)["settings"]
    assert (settings["spending_share"], settings["indexation"], settings["horizon_age"]) == (
        "0.80",
        "-0.003",
        95,
    )
    log = owner_client.get("/api/audit").json()["items"]
    assert any(e["details"] == {"horizon_age": "90"} for e in log)


@pytest.mark.parametrize(
    "body",
    [
        {"spending_share": "0.4"},
        {"spending_share": "0.805"},
        {"indexation": "0.02"},
        {"horizon_age": 120},
        {"spending_amount": "-1"},
    ],
)
def test_settings_out_of_bounds_are_refused(owner_client: TestClient, body: dict[str, Any]) -> None:
    assert _settings(owner_client, **body).status_code == 422


def test_the_retirement_spending_leaves_the_loans_out(owner_client: TestClient) -> None:
    loan = _line(owner_client, "Debts", "Prêt auto")
    _value(owner_client, loan, "2026-12", "5000.00")
    owner_client.put(
        f"/api/projection/debts/{loan}",
        json={"payment": "300.00", "rate": "0", "insurance": "10.00"},
        headers=csrf(owner_client),
    )
    assert _get(owner_client)["spending"]["debt_payments"] == "310.00"


def _flat(client: TestClient) -> None:
    savings = _categories(client)["Savings accounts"]["id"]
    for path, body in (
        (f"/api/projection/categories/{savings}", {"ret": "0", "volatility": "0"}),
        ("/api/projection/inflation", {"inflation": "0"}),
    ):
        assert client.put(path, json=body, headers=csrf(client)).status_code == 200


def test_the_plan_runs_from_the_households_wealth_to_its_horizon(
    owner_client: TestClient, session: Session, owner: User
) -> None:
    _flat(owner_client)
    livret = _line(owner_client, "Savings accounts", "Livret A")
    _value(owner_client, livret, "2026-12", "120000.00")
    _mine(owner_client)  # born December 1960, retired this month, a pension of 1,000
    _settings(owner_client, spending_amount="1000.00")

    plan = retirement.plan(session, owner, TODAY.date())
    assert plan.retired_at == 1
    assert plan.horizon.year == 2055  # 95 years old
    assert plan.left_out == []
    result = retirement.run(plan, paths=10)
    # The pension pays the spending; the wealth pays 120,000 over 348 months alone.
    assert result.withdrawal.nine_tenths == D(300)
    assert result.outcome.shortfall_share() == 0


def test_a_plan_needs_wealth_and_a_member_with_a_birth_month(
    owner_client: TestClient, session: Session, owner: User
) -> None:
    with pytest.raises(retirement.PlanError, match="no_wealth"):
        retirement.plan(session, owner, TODAY.date())
    livret = _line(owner_client, "Savings accounts", "Livret A")
    _value(owner_client, livret, "2026-12", "1000.00")
    with pytest.raises(retirement.PlanError, match="no_member"):
        retirement.plan(session, owner, TODAY.date())
