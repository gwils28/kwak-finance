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
from kwak_api.dash.projection import View, fan, view_of
from kwak_api.models import User
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


def _update(client: TestClient, search: str = "", **headers: str) -> Any:
    body = {
        "output": "..fan.figure...notes.children..",
        "outputs": [{"id": "fan", "property": "figure"}, {"id": "notes", "property": "children"}],
        "inputs": [
            {"id": "scope", "property": "value", "value": "household"},
            {"id": "horizon", "property": "value", "value": 5},
            {"id": "euros", "property": "value", "value": "today"},
        ],
        "state": [{"id": "url", "property": "search", "value": search}],
        "changedPropIds": ["horizon.value"],
    }
    response = client.post("/dash/_dash-update-component", json=body, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["response"]


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
    assert len(figure["data"]) == 5
    assert figure["data"][-1]["name"] == "Médiane"
    assert len(figure["data"][-1]["y"]) == 61  # the start and 5 years of months
    notes = json.dumps(out["notes"]["children"], ensure_ascii=False)
    assert "Épargne mensuelle" in notes
    assert "graine 20261022" in notes


def test_without_a_wealth_line_the_page_asks_for_one(owner_client: TestClient) -> None:
    notes = json.dumps(_update(owner_client)["notes"]["children"])
    assert "enter the wealth first" in notes


def test_the_query_string_sets_language_and_theme() -> None:
    assert view_of("?lang=fr&theme=dark") == View("fr", "dark")
    assert view_of("") == View("en", "light")
    assert view_of("?lang=de&theme=neon") == View("en", "light")


def test_the_fan_takes_the_themes_colours() -> None:
    category = mc.Category(uuid4(), "savings", D(1000), Assumption(D(0), D(0)), D(1))
    scenario = mc.Scenario([category], [D(0)] * 12, [D(0)] * 12, D(0), D(0))
    outcome = mc.simulate(scenario, paths=10)
    figure = fan(outcome, Month(2026, 12), today=True, view=View("en", "dark"))
    assert figure.data[-1].line.color == "rgb(115,194,81)"  # primary-400
    assert figure.data[1].fillcolor == "rgb(36,78,18)"  # primary-800
    assert figure.layout.yaxis.tickprefix == "€"


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
