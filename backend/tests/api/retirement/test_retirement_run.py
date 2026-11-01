"""The Retirement page's data (spec §4.13 F-RET-4): the standard of living, how long the wealth
lasts, the fan and the income once retired, every figure the page shows, its words left to it."""

from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from kwak_api.models import User

from tests.api.conftest import Clock, log_in
from tests.api.retirement.test_retirement import _flat, _mine, _settings
from tests.api.wealth.test_wealth import TODAY, _line, _value

D = Decimal


@pytest.fixture
def owner_client(client: TestClient, clock: Clock, owner: User) -> TestClient:
    clock.now = TODAY
    log_in(client, clock)
    return client


def _run(client: TestClient) -> Any:
    response = client.get("/api/retirement/run")
    assert response.status_code == 200, response.text
    return response.json()


def _planned(client: TestClient) -> Any:
    _flat(client)
    livret = _line(client, "Savings accounts", "Livret A")
    _value(client, livret, "2026-12", "120000.00")
    _mine(client)  # born December 1960, retired this month, a pension of 1,000
    _settings(client, spending_amount="1000.00")
    return _run(client)


def test_it_needs_a_signed_in_session(client: TestClient) -> None:
    assert client.get("/api/retirement/run").status_code == 401


def test_without_wealth_the_page_says_so(owner_client: TestClient) -> None:
    assert _run(owner_client) == {"problem": "no_wealth", "plan": None}


def test_without_a_retirement_entered_the_page_asks_for_one(owner_client: TestClient) -> None:
    livret = _line(owner_client, "Savings accounts", "Livret A")
    _value(owner_client, livret, "2026-12", "1000.00")
    assert _run(owner_client) == {"problem": "no_member", "plan": None}


def test_the_standard_of_living_and_how_long_the_wealth_lasts(owner_client: TestClient) -> None:
    out = _planned(owner_client)
    assert out["problem"] is None
    plan = out["plan"]
    assert plan["this_month"] == "2026-12"
    assert plan["retired"] == "2026-12"
    assert plan["horizon"] == "2055-12"
    living = plan["living"]
    assert D(living["pensions"]).quantize(D(-2)) == 1000, "indexed -0.3 % a year"
    assert D(living["withdrawal"]).quantize(D(-2)) == 300
    assert D(living["spending"]) == 1000
    assert living["later_pension"] is False
    lasts = plan["lasts"]
    assert D(lasts["chance"]) > D("0.99")
    assert lasts["ten_age"] is None
    assert lasts["half_age"] is None
    assert lasts["shortfall"] is False
    assert plan["horizon_age"] == 95
    assert plan["youngest_age_at_horizon"] == 95


def test_the_fan_and_the_income_once_retired(owner_client: TestClient) -> None:
    plan = _planned(owner_client)["plan"]
    months = plan["months"]
    assert months[0]["month"] == "2026-12"
    assert months[-1]["month"] == "2055-12"
    first = months[0]
    assert D(first["p10"]) <= D(first["p50"]) <= D(first["p90"])
    assert D(first["liquid"]) == D("120000.00")
    income = plan["income"]
    assert income[0]["month"] == "2027-01", "from the household's retirement, counted from 1"
    assert D(income[0]["pensions"]) == D(plan["living"]["pensions"])
    assert D(income[0]["spending"]) == 1000
    assert D(income[0]["withdrawal"]) == D(plan["living"]["withdrawal"])


def test_the_inputs_are_given_back(owner_client: TestClient) -> None:
    plan = _planned(owner_client)["plan"]
    [me] = plan["people"]
    assert me["name"] == "Owner"
    assert me["birth"] == "1960-12"
    assert me["age_at_retirement"] == 66
    assert D(me["pension"]) == 1000
    spending = plan["spending"]
    assert spending["share"] is None, "set by hand"
    assert D(spending["retirement"]) == 1000
    assert plan["left_out"] == []
    assert D(plan["indexation"]) == D("-0.003")
    assert plan["engine"]["paths"] == 5000
