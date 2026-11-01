"""The Forecast page's data (spec §4.14 F-FCT-6), on the demo's three years of fictitious data
(F-ADM-5): every figure the page shows, its words left to the page."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from kwak_analytics import foundation
from kwak_api.models import User

from tests.api.conftest import Clock, csrf, log_in

D = Decimal
NOW = datetime(2026, 10, 28, 9, tzinfo=UTC)


@pytest.fixture
def owner_client(client: TestClient, clock: Clock, owner: User) -> TestClient:
    clock.now = NOW
    log_in(client, clock)
    return client


@pytest.fixture
def demo(owner_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    monkeypatch.setattr(foundation, "available", lambda: False)
    response = owner_client.post("/api/demo/enter", headers=csrf(owner_client))
    assert response.status_code in (200, 204), response.text
    response = owner_client.get("/api/forecast")
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    assert body["forecast"] is not None
    return body


def test_a_new_household_is_told_how_many_months_it_has(owner_client: TestClient) -> None:
    response = owner_client.get("/api/forecast")
    assert response.status_code == 200
    assert response.json() == {"complete_months": 0, "needed": 12, "forecast": None}


def test_it_needs_a_signed_in_session(client: TestClient) -> None:
    assert client.get("/api/forecast").status_code == 401


def test_the_next_twelve_months_follow_the_history(demo: dict[str, Any]) -> None:
    f = demo["forecast"]
    assert demo["complete_months"] == 36
    assert f["origin"] == "2026-09"
    assert [m["month"] for m in f["ahead"]][:2] == ["2026-10", "2026-11"]
    assert len(f["ahead"]) == 12
    assert len(f["history"]) == 24, "the table's two years"
    assert f["history"][-1]["month"] == "2026-09"
    last = f["history"][-1]
    assert D(last["rest"]) == D(last["income"]) - D(last["spent"]) - D(last["saved"])
    first = f["ahead"][0]
    for name in ("income", "spent", "saved", "rest"):
        band = first[name]
        assert D(band["low"]) <= D(band["point"]) <= D(band["high"]), name
    assert D(first["fixed"]) > 0, "the fixed expenses due are known"


def test_the_totals_and_the_month_so_far(demo: dict[str, Any]) -> None:
    f = demo["forecast"]
    totals = f["totals"]
    assert totals["banded"] is True
    point = sum(D(m["rest"]["point"]) for m in f["ahead"])
    assert D(totals["rest"]["point"]) == point
    month = f["month"]
    assert month["month"] == "2026-10"
    assert D(month["entered"]) > 0
    assert D(month["elapsed"]) == (D(28) / 31).quantize(D("0.0001"))
    assert month["expected"] == f["ahead"][0]["spent"]


def test_the_rest_was_optimistic_in_the_back_test(demo: dict[str, Any]) -> None:
    """The demo's rest was forecast above what was left (foundation-models memory, ~€165)."""
    assert D(demo["forecast"]["rest_above"]) > 10


def test_the_targets_come_likeliest_overrun_first(demo: dict[str, Any]) -> None:
    f = demo["forecast"]
    targets = f["targets"]
    assert targets, "the demo has expense targets"
    order = {"likely": 0, "possible": 1, "unlikely": 2}
    ranks = [order[a["risk"]] for a in targets]
    assert ranks == sorted(ranks)
    assert {a["kind"] for a in targets} == {"expense"}
    assert any(a["risk"] == "likely" for a in targets)
    assert all(a["to_date"] is None for a in targets)
    year = f["year_targets"]
    assert f["year"] == 2026
    assert year
    assert all(a["to_date"] is not None for a in year)
    assert {a["kind"] for a in year} <= {"expense", "savings"}


def test_the_income_and_the_objectives(demo: dict[str, Any]) -> None:
    f = demo["forecast"]
    assert f["income"], "the demo's salaries"
    assert any(D(i["band"]["point"]) > 0 for i in f["income"])
    assert all(a["kind"] == "savings" for a in f["objectives"])


def test_what_each_forecast_rests_on(demo: dict[str, Any]) -> None:
    f = demo["forecast"]
    rows = f["reliability"]
    assert len(rows) >= 5
    models = {r["method"]["model"] for r in rows}
    assert models - {None} <= {
        "baseline",
        "average_3",
        "average_12",
        "average_all",
        "naive",
        "seasonal_naive",
        "ses",
        "ets",
        "theta",
        "arima",
        "adida",
        "trees",
    }
    contested = [r for r in rows if r["method"]["contest"]]
    assert contested
    for r in contested:
        assert D(r["versus"]) >= 0
        assert r["mase"] is not None
    assert all(r["method"]["model"] != "trees" or r["method"]["features"] for r in rows)


def test_the_back_test_and_the_scores(demo: dict[str, Any]) -> None:
    f = demo["forecast"]
    names = [s["name"] for s in f["scores"]]
    assert names == ["income", "spent", "saved", "rest"]
    rest = f["scores"][3]
    assert D(rest["bias_per_month"]) < 0, "optimistic: the rest above what was left"
    spent = next(b for b in f["backtest"] if b["name"] == "spent")
    assert len(spent["points"]) >= 9
    point = spent["points"][0]
    assert set(point) == {"month", "entered", "forecast"}


def test_the_engine_is_named(demo: dict[str, Any]) -> None:
    engine = demo["forecast"]["engine"]
    assert engine["months"] == 36
    assert engine["cuts"] >= 9
    assert engine["models"] == {}, "the test image has no foundation model"
    assert engine["seed"]
    assert engine["version"]


def test_the_band_note(demo: dict[str, Any]) -> None:
    note = demo["forecast"]["band"]
    assert note["none"] is False
    assert note["widened_from"] is None or note["widened_from"] > "2026-10"
