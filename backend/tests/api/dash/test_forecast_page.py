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
from tests.api.dash.helpers import class_named, find, graphs

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
    charts = graphs(body)
    months = charts["fct-months-chart"]
    names = [d.get("name") for d in months["data"]]
    for name in ("Income", "Spent", "Of which fixed expenses", "Spent (forecast)", "Rest"):
        assert name in names
    assert "Spent, about 8 times in 10" in names
    assert "Rest (forecast)" in names
    assert "Last complete month" in _text(months["layout"]["annotations"])
    assert "Spent: forecast one month ahead" in [
        d.get("name") for d in charts["fct-backtest-chart"]["data"]
    ]
    for title in ("Against the targets", "What the forecast rests on", "The back-test", "Limits"):
        assert title in text
    assert "the average of the last 6 months" in text or "kept without a contest" in text
    assert "not a prediction of your decisions" in text
    assert "Bias, past months tested" in text
    assert "Foundation models not installed" in text  # the test image has none
    assert "A price rise faster than in the past months is forecast late" in text


def test_the_answer_comes_first_in_tiles(demo_client: TestClient) -> None:
    """Spec §7: the sections' links, the rest's warning, then the tiles, then the cards."""
    body = _body(demo_client)
    assert body[0]["type"] == "Nav"
    assert "#fct-reliable" in _text(body[0])
    warning, tiles = body[1], body[2]
    assert "the rest may be lower than shown" in _text(warning)
    assert tiles["props"]["className"] == "kw-tiles"
    labels = [c["props"]["children"] for c in class_named(tiles, "kw-label")]
    assert labels[0] == "Rest, Oct 2026 to Sep 2027"
    assert "Oct 2026 so far" in labels
    assert len(labels) == 7
    assert class_named(tiles, "kw-meter"), "the month's spending against its forecast"
    assert any("likely over" in _text(c) for c in class_named(tiles, "kw-chip"))


def test_the_targets_and_the_year_are_drawn_against_their_targets(demo_client: TestClient) -> None:
    charts = graphs(_body(demo_client))
    targets = charts["fct-targets-chart"]
    assert targets["layout"]["shapes"][0]["x0"] == 100, "the target, at 100 %"
    rows = targets["data"][1]["y"]
    assert rows[-1].startswith("▲ "), "the likeliest overrun on top"
    year = charts["fct-year-chart"]
    assert year["layout"]["barmode"] == "stack"
    assert [d["name"] for d in year["data"][:2]] == ["To Sep 2026", "Forecast to December"]
    assert "fct-income-chart" in charts


def test_the_method_is_folded_under_how_reliable_it_is(demo_client: TestClient) -> None:
    body = _body(demo_client)
    (fold,) = class_named(body, "kw-fold")
    assert fold["props"]["id"] == "fct-reliable"
    inside = _text(fold)
    for title in ("What the forecast rests on", "The back-test", "Limits"):
        assert title in inside
    assert "fct-reliability-chart" in graphs(fold)


def test_the_page_follows_the_language(demo_client: TestClient) -> None:
    text = _text(_body(demo_client, "?lang=fr&theme=dark"))
    assert "Entre oct. 2026 et sept. 2027, des revenus de" in text
    assert "Face aux objectifs" in text
    assert "Le reste, oct. 2026 à sept. 2027" in text


def test_the_charts_and_ratios_follow_the_language(demo_client: TestClient) -> None:
    body = _body(demo_client, "?lang=fr")
    months = graphs(body)["fct-months-chart"]
    assert "janv. 2026" in months["layout"]["xaxis2"]["ticktext"]
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


def _cells(component: Any, tag: str) -> list[Any]:
    if isinstance(component, list):
        return [c for item in component for c in _cells(item, tag)]
    if not isinstance(component, dict):
        return []
    props = component.get("props", {})
    found = [props] if component.get("type") == tag else []
    return found + _cells(props.get("children"), tag)


def test_the_biases_wrap_so_the_tables_fit_their_frame(demo_client: TestClient) -> None:
    # in French, a bias on one line pushed the last column out of the frame
    cells = _cells(_body(demo_client, "?lang=fr"), "Td")
    biases = [
        c for c in cells if re.search(r"que ce qui (a été saisi|restait)", str(c["children"]))
    ]
    assert len(biases) > 3
    assert {c["style"]["whiteSpace"] for c in biases} == {"normal"}


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


def test_every_chart_is_boxed_to_its_height(demo_client: TestClient) -> None:
    """Responsive, a chart fills its box: without a height of its own it took its card's, and
    ten rows were squeezed into ninety pixels."""
    body = _body(demo_client)
    charts = find(body, lambda c: c.get("type") == "Graph")
    assert len(charts) >= 5
    for chart in charts:
        props = chart["props"]
        height = props["figure"]["layout"].get("height")
        boxed = props.get("style", {}).get("height", "")
        assert boxed == f"{height}px" if height else boxed.endswith("rem"), props["id"]


def test_the_rows_are_named_without_a_euro_sign(demo_client: TestClient) -> None:
    """The row charts' y axis names categories: the euro sign of the value axes stays off it."""
    charts = graphs(_body(demo_client, "?lang=fr"))
    for name in (
        "fct-targets-chart",
        "fct-year-chart",
        "fct-income-chart",
        "fct-reliability-chart",
    ):
        axis = charts[name]["layout"]["yaxis"]
        assert "€" not in axis.get("ticksuffix", "") + axis.get("tickprefix", ""), name
