"""The Forecast page, a Dash page (spec §4.14 F-FCT-6), on the demo's three years of
fictitious data (F-ADM-5)."""

import json
import re
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from kwak_analytics import foundation
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


def test_the_demo_is_forecast(demo_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(foundation, "available", lambda: False)  # an image built without them
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
    assert "Bias, past months tested" in text
    assert "Foundation models not installed" in text  # the test image has none
    assert "A price rise faster than in the past months is forecast late" in text


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


def test_the_tables_wrap_their_headers_and_words_but_not_their_amounts() -> None:
    # issue #164: the year table was wider than its frame
    from kwak_api.dash.forecast import _table

    table = _table(
        ["Category", "To date", "Chance"], [["Leisure", "4 377 €", "nearly always"]], worded=(2,)
    ).children
    header = table.children[0].children
    wraps = [c.style["whiteSpace"] for c in header.children]
    assert wraps == ["normal", "normal", "normal"]
    (row,) = table.children[1].children
    assert [c.style["whiteSpace"] for c in row.children] == ["normal", "nowrap", "normal"]
    assert [c.style["textAlign"] for c in row.children] == ["left", "right", "right"]


def test_a_bias_reads_by_kind() -> None:
    """Spec F-FCT-6: what the forecast rests on, in words."""
    from decimal import Decimal

    from kwak_api.dash.forecast import bias_text
    from kwak_core.categories import CategoryKind

    d = Decimal
    assert bias_text(d("0.03"), CategoryKind.EXPENSE, "en") == "3% less spending than was entered"
    assert bias_text(d("-0.03"), CategoryKind.INCOME, "en") == "3% more income than was received"
    assert bias_text(d("-0.03"), CategoryKind.SAVINGS, "en") == "3% more savings than was saved"
    assert bias_text(d("0.004"), CategoryKind.EXPENSE, "en") == "about what was entered"
    assert bias_text(d("0.03"), CategoryKind.EXPENSE, "fr") == (
        "3\u202f% de dépenses en moins que ce qui a été saisi"
    )


def test_a_candidate_set_aside_is_named_when_it_erred_less() -> None:
    from decimal import Decimal

    from kwak_api.dash.forecast import set_aside_text
    from kwak_core.categories import CategoryKind
    from kwak_core.forecast import Choice, Score

    d = Decimal
    choice = Choice(
        "naive",
        {
            "baseline": Score(d(1), d(1), None, d(0)),
            "naive": Score(d("0.8"), d(1), None, d("-0.02")),
            "timesfm": Score(d("0.7"), d(1), None, d("0.07")),
        },
        {"baseline": d(1), "naive": d("0.8"), "timesfm": d("0.7")},  # 13 % below naive
        contest=True,
        set_aside=frozenset({"timesfm"}),
    )
    assert set_aside_text(choice, CategoryKind.EXPENSE, "en") == (
        "TimesFM 2.5 erred 13% less but forecast 7% less spending than was entered in the past "
        "months tested, so it was not used."
    )
    kept = Choice("timesfm", choice.scores, choice.gains, contest=True)
    assert set_aside_text(kept, CategoryKind.EXPENSE, "en") is None
