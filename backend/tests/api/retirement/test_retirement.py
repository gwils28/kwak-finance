"""Retirement (spec §4.13): each member enters their own, any member the household's settings,
and the plan read from the household."""

from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from kwak_api.models import User
from kwak_api.services import projection, retirement
from kwak_core.budget import Month
from kwak_core.projection import SavingsSource
from kwak_core.visibility import Scope
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
        "horizon_age": 75,
        "default_spending_share": "0.80",
        "default_indexation": "-0.003",
        "default_horizon_age": 75,
        "warned_horizon_age": 85,
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
        75,
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
        {"horizon_age": 69},
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
    _settings(owner_client, spending_amount="1000.00", horizon_age=95)

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


def test_the_horizon_is_75_by_default_and_may_come_down_to_70(
    owner_client: TestClient, session: Session, owner: User
) -> None:
    livret = _line(owner_client, "Savings accounts", "Livret A")
    _value(owner_client, livret, "2026-12", "1000.00")
    _mine(owner_client)  # born December 1960
    assert retirement.plan(session, owner, TODAY.date()).horizon == Month(2035, 12)
    assert _settings(owner_client, horizon_age=70).status_code == 200
    assert retirement.plan(session, owner, TODAY.date()).horizon == Month(2030, 12)
    _mine(owner_client, retirement="2031-01")
    with pytest.raises(retirement.PlanError, match="horizon"):
        retirement.plan(session, owner, TODAY.date())  # before the retirement


def _contribute(client: TestClient, source: str | None = None) -> None:
    ids = {name: c["id"] for name, c in _categories(client).items()}
    body: dict[str, Any] = {
        "contributions": [
            {"category_id": ids["Stocks"], "amount": "300.00"},
            {"category_id": ids["Savings accounts"], "amount": "100.00", "indexed": False},
        ]
    }
    if source is not None:
        body["savings_source"] = source
    response = client.put("/api/projection/contributions", json=body, headers=csrf(client))
    assert response.status_code == 200, response.text


def test_the_savings_follow_the_projections_choice(
    owner_client: TestClient, session: Session, owner: User
) -> None:
    """F-RET-3: declared, the contributions and their split; measured, the capacity."""
    _flat(owner_client)
    livret = _line(owner_client, "Savings accounts", "Livret A")
    _value(owner_client, livret, "2026-12", "10000.00")
    _mine(owner_client, retirement="2030-12", earnings="2000.00")
    _settings(owner_client, horizon_age=95)

    measured = retirement.plan(session, owner, TODAY.date())
    assert measured.source is SavingsSource.MEASURED
    assert measured.scenario.savings[0] == measured.basis.savings
    assert measured.scenario.split is None

    _contribute(owner_client)  # unset: declared once a contribution exists
    session.expire_all()
    declared = retirement.plan(session, owner, TODAY.date())
    assert declared.source is SavingsSource.DECLARED
    assert declared.scenario.savings[0] == D(400)
    assert declared.scenario.split is not None
    shares = dict(
        zip((c.id for c in declared.basis.categories), declared.scenario.split[0], strict=True)
    )
    stocks = _categories(owner_client)["Stocks"]["id"]
    assert str(max(shares, key=lambda k: shares[k])) == stocks
    # Until the retirement, the projection's savings exactly (invariant 37).
    run = projection.scenario(
        projection.basis(session, owner, Scope.HOUSEHOLD, TODAY.date(), contributions=True),
        years=4,
    )
    assert declared.scenario.savings[:47] == run.savings[:47]
    assert run.split is not None
    assert declared.scenario.split[:47] == run.split[:47]
    assert declared.scenario.categories == run.categories

    _contribute(owner_client, "measured")
    session.expire_all()
    back = retirement.plan(session, owner, TODAY.date())
    assert back.source is SavingsSource.MEASURED
    assert back.scenario.savings[0] == back.basis.savings
    assert back.scenario.split is None
    assert back.scenario.categories == run.categories
