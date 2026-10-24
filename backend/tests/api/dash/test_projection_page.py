"""The Projection page, a Dash page behind the session (spec §4.11 F-SIM-5)."""

import json
import string
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from kwak_analytics import montecarlo as mc
from kwak_api.dash import i18n
from kwak_api.dash import projection_views as views
from kwak_api.dash.projection import View, WhatIfError, view_of, what_if
from kwak_api.models import User
from kwak_api.services import projection
from kwak_core.budget import Month
from kwak_core.projection import Assumption

from tests.api.conftest import Clock, log_in
from tests.api.wealth.test_wealth import TODAY, _line, _value

D = Decimal


@pytest.fixture
def owner_client(client: TestClient, clock: Clock, owner: User) -> TestClient:
    clock.now = TODAY
    log_in(client, clock)
    return client


OUTPUTS = [
    ("invalid", "children"),
    ("fan", "figure"),
    ("fan-after", "children"),
    ("categories-title", "children"),
    ("categories", "figure"),
    ("categories-after", "children"),
    ("compare", "children"),
    ("about", "children"),
]


def _wi(n: int, field: str, value: Any) -> dict[str, Any]:
    return {"id": {"type": "wi", "n": n, "field": field}, "property": "value", "value": value}


def _update(
    client: TestClient,
    search: str = "",
    *,
    amount: Any = 20000,
    what_ifs: list[dict[str, Any]] | None = None,
    allocation: list[dict[str, Any]] | None = None,
    **headers: str,
) -> Any:
    wi = what_ifs or []
    alloc = allocation or []
    body = {
        "output": ".." + "...".join(f"{i}.{p}" for i, p in OUTPUTS) + "..",
        "outputs": [{"id": i, "property": p} for i, p in OUTPUTS],
        "inputs": [
            {"id": "scope", "property": "value", "value": "household"},
            {"id": "horizon", "property": "value", "value": 5},
            {"id": "euros", "property": "value", "value": "today"},
            {"id": "amount", "property": "value", "value": amount},
            {"id": "reach-year", "property": "value", "value": 2031},
            {"id": "reach-month", "property": "value", "value": 12},
            wi,
            alloc,
        ],
        "state": [
            [{"id": w["id"], "property": "id", "value": w["id"]} for w in wi],
            [{"id": a["id"], "property": "id", "value": a["id"]} for a in alloc],
            {"id": "url", "property": "search", "value": search},
        ],
        "changedPropIds": ["horizon.value"],
    }
    response = client.post("/dash/_dash-update-component", json=body, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["response"]


def _text(component: Any) -> str:
    return json.dumps(component, ensure_ascii=False)


def test_the_page_needs_a_signed_in_session(client: TestClient, owner: User) -> None:
    for path in ("/dash/projection", "/dash/_dash-layout"):
        assert client.get(path).status_code == 401
    refused = client.get("/dash/projection?lang=fr")
    assert refused.text == "Connectez-vous à Kwak Finance pour voir cette page."


def test_the_page_is_served_to_a_signed_in_member(owner_client: TestClient) -> None:
    page = owner_client.get("/dash/projection?lang=fr&theme=dark")
    assert page.status_code == 200
    assert "/dash/_dash-component-suites/" in page.text
    assert owner_client.get("/dash/_dash-layout").status_code == 200


def test_the_fan_is_drawn_for_the_viewer_whatever_header_is_sent(
    owner_client: TestClient,
) -> None:
    livret = _line(owner_client, "Savings accounts", "Livret A")
    _value(owner_client, livret, "2026-12", "10000.00")
    # A header naming someone else is replaced by the gate.
    out = _update(owner_client, "?lang=fr", **{"X-Kwak-User": str(uuid4())})
    figure = out["fan"]["figure"]
    assert [d.get("name") for d in figure["data"]][-1] == "Médiane"
    assert len(figure["data"][-1]["y"]) == 61  # the start and 5 years of months
    after = _text(out["fan-after"]["children"])
    assert "Épargne mensuelle" in after
    assert "graine 20261022" in after
    assert "Afficher les données" in after


def test_the_chance_of_reaching_an_amount_and_when(owner_client: TestClient) -> None:
    livret = _line(owner_client, "Savings accounts", "Livret A")
    _value(owner_client, livret, "2026-12", "10000.00")
    # No volatility and no savings: at 1.7 % against 2 % of inflation, every outcome holds
    # about €9,850 of today's euros in five years.
    after = _text(_update(owner_client, amount=9800)["fan-after"]["children"])
    assert "In more than 99% of the outcomes, net worth is at least €9,800 in Dec 2031." in after
    assert "Half of the outcomes have reached it once by Dec 2026" in after
    after = _text(_update(owner_client, amount=9900)["fan-after"]["children"])
    assert "In less than 1% of the outcomes" in after
    after = _text(_update(owner_client, amount=1_000_000)["fan-after"]["children"])
    assert "In less than 1% of the outcomes" in after
    assert "not within the horizon" in after
    assert "Enter an amount" in _text(_update(owner_client, amount=None)["fan-after"]["children"])


def test_a_what_if_is_drawn_and_compared(owner_client: TestClient) -> None:
    livret = _line(owner_client, "Savings accounts", "Livret A")
    _value(owner_client, livret, "2026-12", "10000.00")
    out = _update(
        owner_client,
        what_ifs=[_wi(1, "on", ["on"]), _wi(1, "savings", 500), _wi(1, "inflation", 3)],
    )
    names = [d.get("name") for d in out["fan"]["figure"]["data"]]
    assert "Median (What-if 1)" in names
    compare = _text(out["compare"]["children"])
    assert "What-if 1" in compare
    assert "Base" in compare
    assert "What-if 1: savings of €500 a month, inflation of 3%." in _text(out["about"]["children"])


def test_a_what_if_that_cannot_run_says_why(owner_client: TestClient) -> None:
    livret = _line(owner_client, "Savings accounts", "Livret A")
    _value(owner_client, livret, "2026-12", "10000.00")
    savings = "00000000-0000-0000-0000-000000000001"
    out = _update(
        owner_client,
        what_ifs=[_wi(2, "on", ["on"])],
        allocation=[
            {"id": {"type": "wi-alloc", "n": 2, "cat": savings}, "property": "value", "value": 60}
        ],
    )
    assert "What-if 2 is not compared: the shares of the allocation sum to 100%." in _text(
        out["invalid"]["children"]
    )
    assert "Median (What-if 2)" not in _text(out["fan"]["figure"])


def test_the_median_by_category_shows_the_debts_below_zero(owner_client: TestClient) -> None:
    livret = _line(owner_client, "Savings accounts", "Livret A")
    _value(owner_client, livret, "2026-12", "10000.00")
    loan = _line(owner_client, "Debts", "Prêt auto")
    _value(owner_client, loan, "2026-12", "3000.00")
    out = _update(owner_client)
    data = out["categories"]["figure"]["data"]
    assert [d["name"] for d in data] == ["Savings accounts", "Debts"]
    assert data[1]["y"][0] == -3000
    assert "together they need not add up" in _text(out["categories-after"]["children"])


def test_without_a_wealth_line_the_page_asks_for_one(owner_client: TestClient) -> None:
    assert "enter the wealth first" in _text(_update(owner_client)["fan-after"]["children"])


def test_a_what_if_reads_percentages_as_typed() -> None:
    stocks, gold = uuid4(), uuid4()
    w = what_if(
        {"savings": 450.5, "inflation": 2.5, "category": str(stocks), "ret": 6.5, "volatility": 18},
        {stocks: 70, gold: 30},
    )
    assert w == projection.WhatIf(
        savings=D("450.50"),
        allocation={stocks: 70, gold: 30},
        assumptions={stocks: Assumption(D("0.065"), D("0.18"))},
        inflation=D("0.025"),
    )
    assert what_if({}, {stocks: None}) == projection.WhatIf()
    for fields, allocation, reason in (
        ({"category": str(stocks), "ret": 6.55}, {}, "reason_assumption"),
        ({"inflation": 25}, {}, "reason_inflation"),
        ({}, {stocks: 50.5, gold: 49.5}, "reason_allocation"),
        ({}, {stocks: 90}, "reason_allocation"),
    ):
        with pytest.raises(WhatIfError, match=reason):
            what_if(fields, allocation)


def test_the_query_string_sets_language_and_theme() -> None:
    assert view_of("?lang=fr&theme=dark") == View("fr", "dark")
    assert view_of("") == View("en", "light")
    assert view_of("?lang=de&theme=neon") == View("en", "light")


def test_the_fan_takes_the_themes_colours() -> None:
    category = mc.Category(uuid4(), "savings", D(1000), Assumption(D(0), D(0)), D(1))
    scenario = mc.Scenario([category], [D(0)] * 12, [D(0)] * 12, D(0), D(0))
    run = projection.Run(scenario, mc.simulate(scenario, paths=10))
    base = views.Scenario("Base", run, projection.BASE)
    other = views.Scenario("What-if 1", run, projection.BASE)
    figure = views.fan(
        [base, other],
        Month(2026, 12),
        today=True,
        view=View("en", "dark"),
        target=views.Target(D(1000), 12),
    )
    assert figure.data[1].fillcolor == "rgb(36,78,18)"  # primary-800
    assert figure.data[4].line.color == "rgb(115,194,81)"  # primary-400
    assert figure.data[5].line.color == "rgb(236,156,19)"  # secondary-500
    assert figure.data[5].line.dash == "dash"
    assert figure.layout.shapes[0].line.dash == "dot"
    assert figure.layout.yaxis.tickprefix == "€"
    assert figure.layout.modebar.activecolor == "rgb(115,194,81)"  # primary-400
    assert figure.layout.hoverlabel.bgcolor == "rgb(24,29,22)"  # the dark surface


def test_both_languages_have_the_same_strings() -> None:
    assert set(i18n.EN) == set(i18n.FR)
    for key in i18n.EN:
        assert set(_fields(i18n.EN[key])) == set(_fields(i18n.FR[key])), key


def _fields(text: str) -> list[str]:
    return [f for _, f, _, _ in string.Formatter().parse(text) if f]


def test_amounts_are_rounded_to_the_hundred_in_each_language() -> None:
    assert i18n.money(D("12345.67"), "en") == "€12,300"
    assert i18n.money(D("12350"), "fr") == "12\u202f400\u00a0€"
    assert i18n.money(D("-49"), "en") == "€0"
    assert i18n.money(D("-1250"), "en") == "-€1,300"
    assert i18n.month(Month(2037, 3), "fr") == "mars 2037"


def test_the_amount_follows_the_euros_shown(owner_client: TestClient) -> None:
    """In current euros the same amount is worth more by the month chosen: the chance stays."""

    def convert(euros: str, amount: int) -> Any:
        body = {
            "output": "amount.value",
            "outputs": {"id": "amount", "property": "value"},
            "inputs": [{"id": "euros", "property": "value", "value": euros}],
            "state": [
                {"id": "amount", "property": "value", "value": amount},
                {"id": "reach-year", "property": "value", "value": 2031},
                {"id": "reach-month", "property": "value", "value": 12},
                {
                    "id": "basis",
                    "property": "data",
                    "value": {"start": "2026-12", "inflation": "0.02"},
                },
            ],
            "changedPropIds": ["euros.value"],
        }
        response = owner_client.post("/dash/_dash-update-component", json=body)
        assert response.status_code == 200, response.text
        return response.json()["response"]["amount"]["value"]

    assert convert("current", 100_000) == 110_400  # 1.02 ** 5
    assert convert("today", 110_400) == 100_000
