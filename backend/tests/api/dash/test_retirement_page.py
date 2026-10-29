"""The Retirement page, a Dash page (spec §4.13 F-RET-4)."""

import json
from typing import Any

import pytest
from fastapi.testclient import TestClient
from kwak_api.models import User

from tests.api.conftest import Clock, log_in
from tests.api.dash.helpers import class_named, graphs
from tests.api.retirement.test_retirement import _flat, _mine, _settings
from tests.api.wealth.test_wealth import TODAY, _line, _value


@pytest.fixture
def owner_client(client: TestClient, clock: Clock, owner: User) -> TestClient:
    clock.now = TODAY
    log_in(client, clock)
    return client


def _body(client: TestClient, search: str = "") -> Any:
    request = {
        "output": "ret-body.children",
        "outputs": {"id": "ret-body", "property": "children"},
        "inputs": [{"id": "ret-trigger", "property": "data", "value": True}],
        "state": [{"id": "url", "property": "search", "value": search}],
        "changedPropIds": ["ret-trigger.data"],
    }
    response = client.post("/dash/_dash-update-component", json=request)
    assert response.status_code == 200, response.text
    return response.json()["response"]["ret-body"]["children"]


def _text(component: Any) -> str:
    return json.dumps(component, ensure_ascii=False)


def test_the_page_is_served(owner_client: TestClient) -> None:
    assert owner_client.get("/dash/retirement?lang=fr").status_code == 200


def test_without_a_retirement_entered_the_page_asks_for_one(owner_client: TestClient) -> None:
    livret = _line(owner_client, "Savings accounts", "Livret A")
    _value(owner_client, livret, "2026-12", "1000.00")
    assert "Enter your birth month" in _text(_body(owner_client))


def test_the_standard_of_living_and_how_long_the_wealth_lasts(owner_client: TestClient) -> None:
    _flat(owner_client)
    livret = _line(owner_client, "Savings accounts", "Livret A")
    _value(owner_client, livret, "2026-12", "120000.00")
    _mine(owner_client)  # born December 1960, retired this month, a pension of 1,000
    _settings(owner_client, spending_amount="1000.00")
    body = _body(owner_client)
    text = _text(body)
    assert (
        "From Dec 2026, pensions of €1,000 and a sustainable withdrawal of €300 a month give "
        "€1,300 a month in 9 outcomes in 10 (€1,300 in half of them), for spending of €1,000: "
        "130% covered."
    ) in text
    assert "In more than 99% of the outcomes, the plan runs to Dec 2055" in text
    assert "In 9 outcomes in 10, the liquid wealth does not run out before 95." in text
    charts = graphs(body)
    fan, income = charts["ret-fan-chart"], charts["ret-income-chart"]
    assert "Liquid wealth (median)" in [d.get("name") for d in fan["data"]]
    assert "Household retires" in _text(fan["layout"]["annotations"])
    assert [d["name"] for d in income["data"]] == [
        "Pensions",
        "Sustainable withdrawal (9 in 10)",
        "Retirement spending",
    ]
    assert "info-retraite.fr" in text
    assert "Long-term care not modelled" in text


def test_the_page_follows_the_language(owner_client: TestClient) -> None:
    _flat(owner_client)
    livret = _line(owner_client, "Savings accounts", "Livret A")
    _value(owner_client, livret, "2026-12", "120000.00")
    _mine(owner_client)
    assert "retrait soutenable" in _text(_body(owner_client, "?lang=fr"))


def test_the_answer_comes_first_then_the_timeline(owner_client: TestClient) -> None:
    """Spec §7, F-RET-4: the standard of living as a tile, the pensions and the withdrawal
    against the spending, then each member's working months and pension on a timeline."""
    _flat(owner_client)
    livret = _line(owner_client, "Savings accounts", "Livret A")
    _value(owner_client, livret, "2026-12", "120000.00")
    _mine(owner_client)
    _settings(owner_client, spending_amount="1000.00")
    body = _body(owner_client)
    assert body[0]["type"] == "Nav"
    tiles = body[1]
    assert tiles["props"]["className"] == "kw-tiles"
    values = [c["props"]["children"] for c in class_named(tiles, "kw-value")]
    assert values == ["€1,300 a month", "130%", "more than 99%"]
    (split,) = class_named(tiles, "kw-split")
    assert [c["props"]["children"] for c in split["props"]["children"]] == [
        "Pensions €1,000",
        "Withdrawal €300",
    ]
    assert "Spending €1,000" in _text(class_named(tiles, "kw-against"))
    (life,) = class_named(body, "kw-life")
    segments = [c["props"]["children"] for c in class_named(life, "kw-segment")]
    assert segments[0].startswith("Pension €1,000")
    assert "Today" in _text(class_named(life, "kw-at"))
    (fold,) = class_named(body, "kw-fold")
    assert "Long-term care not modelled" in _text(fold)
