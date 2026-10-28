"""The Forecast page, a Dash page (spec §4.14 F-FCT-6), on the demo's three years of
fictitious data (F-ADM-5)."""

import json
import re
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from kwak_api.models import User

from tests.api.conftest import Clock, csrf, log_in

NOW = datetime(2026, 10, 28, 9, tzinfo=UTC)


@pytest.fixture
def owner_client(client: TestClient, clock: Clock, owner: User) -> TestClient:
    clock.now = NOW
    log_in(client, clock)
    return client


@pytest.fixture
def demo_client(owner_client: TestClient) -> TestClient:
    response = owner_client.post("/api/demo/enter", headers=csrf(owner_client))
    assert response.status_code in (200, 204), response.text
    return owner_client


def _body(client: TestClient, search: str = "") -> Any:
    request = {
        "output": "fct-body.children",
        "outputs": {"id": "fct-body", "property": "children"},
        "inputs": [{"id": "fct-trigger", "property": "data", "value": True}],
        "state": [{"id": "url", "property": "search", "value": search}],
        "changedPropIds": ["fct-trigger.data"],
    }
    response = client.post("/dash/_dash-update-component", json=request)
    assert response.status_code == 200, response.text
    return response.json()["response"]["fct-body"]["children"]


def _text(component: Any) -> str:
    return json.dumps(component, ensure_ascii=False)


def test_the_page_is_served(owner_client: TestClient) -> None:
    assert owner_client.get("/dash/forecast?lang=fr").status_code == 200


def test_a_new_household_is_told_how_many_months_it_has(owner_client: TestClient) -> None:
    text = _text(_body(owner_client))
    assert "A forecast needs 12 complete months of spending; there are 0 so far." in text


def test_the_demo_is_forecast(demo_client: TestClient) -> None:
    body = _body(demo_client)
    text = _text(body)
    assert "From Oct 2026 to Sep 2027, an income of €" in text
    assert "about 8 times in 10" in text
    assert "spent so far in Oct 2026" in text
    figures = [c["props"]["figure"] for c in body if c.get("type") == "Graph"]
    months, rest, backtest = figures
    names = [d.get("name") for d in months["data"]]
    for name in ("Income", "Spent", "Saved", "Of which fixed expenses", "Spent (forecast)"):
        assert name in names
    assert "Spent, about 8 times in 10" in names
    assert "Last complete month" in _text(months["layout"]["annotations"])
    assert "Rest (forecast)" in [d.get("name") for d in rest["data"]]
    assert "Spent: forecast one month ahead" in [d.get("name") for d in backtest["data"]]
    for title in ("Against the targets", "What the forecast rests on", "The back-test", "Limits"):
        assert title in text
    assert "the average of the last 6 months" in text or "kept without a contest" in text
    assert "not a prediction of your decisions" in text


def test_the_page_follows_the_language(demo_client: TestClient) -> None:
    text = _text(_body(demo_client, "?lang=fr&theme=dark"))
    assert "Entre oct. 2026 et sept. 2027, des revenus de" in text
    assert "Face aux objectifs" in text


def test_the_charts_and_ratios_follow_the_language(demo_client: TestClient) -> None:
    body = _body(demo_client, "?lang=fr")
    months = next(c for c in body if c.get("type") == "Graph")["props"]["figure"]
    assert "janv. 2026" in months["layout"]["xaxis"]["ticktext"]
    text = _text(body)
    assert "Dépensé : prévu un mois à l'avance" in text
    assert not re.search(r'"\d\.\d\d"', text), "a ratio with a decimal point in French"
