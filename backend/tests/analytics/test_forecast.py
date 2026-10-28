"""The cash-flow forecast's engine (spec §4.14 F-FCT-3, 4, invariant §8.41)."""

from decimal import Decimal
from uuid import UUID, uuid4

import numpy as np
import pytest
from kwak_analytics import foundation
from kwak_analytics.forecast import AVERAGE_MODELS, ORDER, TREES, Result, SeriesInput, run
from kwak_core.budget import Month
from kwak_core.forecast import BASELINE, HORIZON, cuts

D = Decimal
FIRST = Month(2023, 10)


def seasonal(n: int, *, seed: int = 0, december: int = 300) -> list[Decimal]:
    """Around 100 a month, more each December, a little noise."""
    noise = [(i * 37 + seed * 11) % 17 - 8 for i in range(n)]
    return [D(100 + (december if (FIRST.month + i) % 12 == 0 else 0) + noise[i]) for i in range(n)]


def household(n: int, count: int = 4) -> list[SeriesInput]:
    return [SeriesInput(uuid4(), seasonal(n, seed=i), 0) for i in range(count)]


@pytest.fixture(scope="module")
def result_36() -> tuple[list[SeriesInput], Result]:
    series = household(36)
    return series, run(series, first=FIRST, n=36, cuts=cuts(36))


def test_every_candidate_at_every_cut(result_36: tuple[list[SeriesInput], Result]) -> None:
    series, result = result_36
    for s in series:
        for model in ORDER:
            assert set(result.backtests[s.key][model]) == set(cuts(36)), model
            assert len(result.futures[s.key][model]) == HORIZON


def test_a_cut_never_forecasts_past_the_origin(
    result_36: tuple[list[SeriesInput], Result],
) -> None:
    """Invariant §8.41."""
    series, result = result_36
    for model, by_cut in result.backtests[series[0].key].items():
        for c, values in by_cut.items():
            assert len(values) == min(HORIZON, 36 - c), (model, c)


def test_seasonal_naive_repeats_last_year(result_36: tuple[list[SeriesInput], Result]) -> None:
    series, result = result_36
    s = series[0]
    assert result.futures[s.key]["seasonal_naive"] == tuple(s.values[-12:])


def test_the_baseline_is_the_last_six_months(result_36: tuple[list[SeriesInput], Result]) -> None:
    series, result = result_36
    s = series[0]
    mean = sum(s.values[-6:], D(0)) / 6
    assert result.futures[s.key][BASELINE] == (mean.quantize(D("0.01")),) * HORIZON


def test_the_trees_say_what_weighed(result_36: tuple[list[SeriesInput], Result]) -> None:
    series, result = result_36
    shares = result.contributions[series[0].key]
    assert len(shares) >= 3
    assert sum(share for _, share in shares) == pytest.approx(1, abs=0.01)


def test_nothing_after_a_cut_changes_its_forecasts() -> None:
    """Invariant §8.41: training on the months up to the cut only."""
    series = household(30)
    changed = [
        SeriesInput(s.key, [*s.values[:20], *(v * 3 for v in s.values[20:])], 0) for s in series
    ]
    a = run(series, first=FIRST, n=30, cuts=[15, 20])
    b = run(changed, first=FIRST, n=30, cuts=[15, 20])
    for s in series:
        for model in ORDER:
            assert a.backtests[s.key][model][20] == b.backtests[s.key][model][20], model


def test_the_same_series_give_the_same_forecasts() -> None:
    series = household(26)
    a = run(series, first=FIRST, n=26, cuts=cuts(26))
    b = run(series, first=FIRST, n=26, cuts=cuts(26))
    assert a == b


def test_the_models_need_thirteen_months_of_training() -> None:
    s = SeriesInput(uuid4(), seasonal(14), 0)
    result = run([s], first=FIRST, n=14, cuts=cuts(14))
    assert set(result.backtests[s.key]["ets"]) == {13}
    assert set(result.backtests[s.key]["arima"]) == {13}
    assert set(result.backtests[s.key][BASELINE]) == set(cuts(14))
    short = SeriesInput(uuid4(), seasonal(12), 0)
    assert set(run([short], first=FIRST, n=12, cuts=cuts(12)).futures[short.key]) == {
        BASELINE,
        *AVERAGE_MODELS,
    }


def test_a_late_series_is_trained_from_its_first_month() -> None:
    late = SeriesInput(uuid4(), [D(50)] * 10, 26)
    result = run([late, *household(36)], first=FIRST, n=36, cuts=cuts(36))
    by_cut = result.backtests[late.key][BASELINE]
    assert min(by_cut) == 27
    assert by_cut[27] == (D(50),) * 9


def test_a_flat_series_is_forecast_flat() -> None:
    flat = SeriesInput(uuid4(), [D(42)] * 30, 0)
    result = run([flat, *household(30)], first=FIRST, n=30, cuts=cuts(30))
    for model, values in result.futures[flat.key].items():
        assert values == (D(42),) * HORIZON, model
    assert TREES not in result.futures[flat.key]  # nothing to scale


def test_keys_are_series_ids() -> None:
    series = household(24, count=2)
    result = run(series, first=FIRST, n=24, cuts=cuts(24))
    assert all(isinstance(k, UUID) for k in result.futures)


# F-FCT-3, 7: the foundation models, when the image carries them


def _last_value(contexts: list[list[float]], horizon: int) -> dict[str, np.ndarray]:
    """Stands for both models: each context's last month, repeated."""
    last = np.array([[c[-1]] * horizon for c in contexts], dtype=np.float64)
    return {foundation.CHRONOS: last, foundation.TIMESFM: last + 1}


def test_without_the_foundation_models_the_order_is_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(foundation, "available", lambda: False)
    result = run(household(14, count=2), first=FIRST, n=14, cuts=cuts(14))
    assert result.order == ORDER
    assert not result.foundation


def test_the_foundation_models_forecast_each_cut_from_its_months(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(foundation, "available", lambda: True)
    monkeypatch.setattr(foundation, "forecast", _last_value)
    series = household(26, count=2)
    result = run(series, first=FIRST, n=26, cuts=cuts(26))
    assert result.order == (*ORDER, *foundation.NAMES)
    assert set(result.foundation) == set(foundation.NAMES)
    s = series[0]
    by_cut = result.backtests[s.key][foundation.CHRONOS]
    assert set(by_cut) == set(cuts(26))  # every cut has 13 months of training
    for c, values in by_cut.items():
        assert values == (s.values[c - 1],) * min(HORIZON, 26 - c)  # nothing after the cut
    assert result.futures[s.key][foundation.TIMESFM] == (s.values[-1] + 1,) * HORIZON


@pytest.mark.skipif(not foundation.available(), reason="an image built with the models")
def test_the_real_models_give_the_same_forecasts_twice() -> None:
    series = household(30, count=3)
    a = run(series, first=FIRST, n=30, cuts=cuts(30))
    b = run(series, first=FIRST, n=30, cuts=cuts(30))
    for s in series:
        for name in foundation.NAMES:
            assert a.futures[s.key][name] == b.futures[s.key][name]
            assert all(D(50) < v < D(500) for v in a.futures[s.key][name]), name


def test_a_model_that_fails_to_load_leaves_the_forecast_without_them(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F-FCT-7: the page still opens, on the other candidates."""

    def broken() -> None:
        monkeypatch.setattr(foundation, "_failed", True)

    monkeypatch.setattr(foundation, "_failed", False)
    monkeypatch.setattr(foundation, "available", lambda: not foundation._failed)
    monkeypatch.setattr(foundation, "_load", broken)
    series = household(14, count=2)
    result = run(series, first=FIRST, n=14, cuts=cuts(14))
    assert result.order == ORDER
    assert foundation.CHRONOS not in result.futures[series[0].key]
