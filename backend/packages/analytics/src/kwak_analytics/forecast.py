"""The cash-flow forecast's engine (spec §4.14 F-FCT-3, 4, invariant §8.41): every candidate fit
at each back-test cut and for the months to come.

Floating point like the Monte Carlo engine (spec §6): the series come in `Decimal` from
`kwak_core.forecast`, the forecasts go back as `Decimal` cents, and `kwak_core.forecast` makes
every choice from them. The averages are computed here; the statistical models are Nixtla's
`statsforecast` (one per series); the trees are one LightGBM for all the household's series,
through Nixtla's `mlforecast`, trained at each cut on the months up to it only. The same series,
seed and engine version always give the same forecasts.
"""

import multiprocessing
import os
import threading
import warnings
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any
from uuid import UUID

import lightgbm as lgb
import numpy as np
import pandas as pd
from kwak_core.budget import Month
from kwak_core.forecast import BASELINE, FIRST_CUT, HORIZON
from kwak_core.goals import add_months
from kwak_core.money import quantize
from mlforecast import MLForecast
from mlforecast.lag_transforms import RollingMean
from mlforecast.target_transforms import LocalStandardScaler
from statsforecast import StatsForecast
from statsforecast.models import (
    ADIDA,
    AutoARIMA,
    AutoETS,
    AutoTheta,
    Naive,
    SeasonalNaive,
    SimpleExponentialSmoothingOptimized,
)

ENGINE_VERSION = 1
"""Raised whenever the same series and seed could give different forecasts."""
DEFAULT_SEED = 20261028
SEASON = 12
JOBS = min(4, os.cpu_count() or 1)
"""Processes fitting the statistical models: AutoARIMA alone would take most of a visit."""
BASELINE_WINDOW = 6

AVERAGE_MODELS = ("average_3", "average_12", "average_all")
STATS_MODELS = ("naive", "seasonal_naive", "ses", "ets", "theta", "arima", "adida")
TREES = "trees"
ORDER = (BASELINE, *AVERAGE_MODELS, *STATS_MODELS, TREES)
"""Every candidate, from the simplest (F-FCT-3)."""

LAGS = (1, 2, 3, 6, 12)
FEATURES = ("lag1", "lag2", "lag3", "lag6", "lag12", "mean3", "mean6", "month", "category")
"""The trees' features, as named in their contributions."""

type Forecasts = tuple[Decimal, ...]


@dataclass(frozen=True)
class SeriesInput:
    key: UUID
    values: Sequence[Decimal]
    """Its variable part, from its first line to the origin."""
    offset: int
    """The household month index of its first value."""


@dataclass(frozen=True)
class Result:
    backtests: Mapping[UUID, Mapping[str, Mapping[int, Forecasts]]]
    """By series, model and household cut: the next months up to HORIZON, never past the
    origin."""
    futures: Mapping[UUID, Mapping[str, Forecasts]]
    """By series and model: the HORIZON months after the origin."""
    contributions: Mapping[UUID, tuple[tuple[str, Decimal], ...]] = field(default_factory=dict)
    """The trees' forecast one month ahead, by feature: each one's share of the absolute
    TreeSHAP contributions, the largest first."""


def _cents(values: Sequence[float]) -> Forecasts:
    return tuple(quantize(Decimal(repr(float(v)))) for v in values)


def _averages(training: Sequence[float], steps: int) -> dict[str, Forecasts]:
    def mean(window: int | None) -> Forecasts:
        part = training if window is None else training[-window:]
        return _cents([float(np.mean(part))] * steps)

    return {
        BASELINE: mean(BASELINE_WINDOW),
        "average_3": mean(3),
        "average_12": mean(12),
        "average_all": mean(None),
    }


def _stats_models() -> list[Any]:
    return [
        Naive(alias="naive"),
        SeasonalNaive(SEASON, alias="seasonal_naive"),
        SimpleExponentialSmoothingOptimized(alias="ses"),
        AutoETS(season_length=SEASON, alias="ets"),
        AutoTheta(season_length=SEASON, alias="theta"),
        AutoARIMA(season_length=SEASON, alias="arima"),
        ADIDA(alias="adida"),
    ]


def _dates(first: Month, offset: int, length: int) -> pd.DatetimeIndex:
    start = add_months(first, offset).first_day()
    return pd.date_range(start, periods=length, freq="MS")


type Job = tuple[UUID, int, Sequence[float], int]
"""A series, the cut it is trained to (n for the months to come), its training and how many
months to forecast."""


def _frame(jobs: Sequence[Job], first: Month, offsets: Mapping[UUID, int]) -> pd.DataFrame:
    frames = []
    for key, cut, training, _ in jobs:
        frames.append(
            pd.DataFrame(
                {
                    "unique_id": f"{key}|{cut}",
                    "ds": _dates(first, offsets[key], len(training)),
                    "y": np.asarray(training, dtype=np.float64),
                }
            )
        )
    return pd.concat(frames, ignore_index=True)


def _fit_stats(df: pd.DataFrame) -> pd.DataFrame:
    """In a worker process: every statistical model on the series of `df`."""
    with warnings.catch_warnings(), np.errstate(all="ignore"):
        warnings.simplefilter("ignore", RuntimeWarning)  # ETS on a short flat training
        out: pd.DataFrame = StatsForecast(models=_stats_models(), freq="MS", n_jobs=1).forecast(
            df=df, h=HORIZON
        )
    return out


_workers: ProcessPoolExecutor | None = None
_workers_lock = threading.Lock()


def _pool() -> ProcessPoolExecutor:
    """Started once, by spawning: the server answers in threads, where fork() may deadlock."""
    global _workers
    with _workers_lock:
        if _workers is None:
            _workers = ProcessPoolExecutor(JOBS, mp_context=multiprocessing.get_context("spawn"))
        return _workers


def _stats(
    jobs: Sequence[Job], first: Month, offsets: Mapping[UUID, int]
) -> dict[tuple[UUID, int], dict[str, Forecasts]]:
    """Every statistical model on every (series, cut) at once, cut to each job's months."""
    if not jobs:
        return {}
    frames = [_frame(jobs[i::JOBS], first, offsets) for i in range(JOBS) if jobs[i::JOBS]]
    out = pd.concat(_pool().map(_fit_stats, frames), ignore_index=True)
    steps = {f"{key}|{cut}": n for key, cut, _, n in jobs}
    result: dict[tuple[UUID, int], dict[str, Forecasts]] = {}
    for uid, rows in out.groupby("unique_id", sort=False):
        key, _, cut = str(uid).partition("|")
        n = steps[str(uid)]
        result[(UUID(key), int(cut))] = {
            m: _cents(values)
            for m in STATS_MODELS
            if np.all(np.isfinite(values := rows[m].to_numpy()[:n]))
        }
    return result


def _trees_model(seed: int) -> lgb.LGBMRegressor:
    return lgb.LGBMRegressor(
        n_estimators=100,
        learning_rate=0.05,
        num_leaves=7,
        min_child_samples=5,
        subsample=1.0,
        colsample_bytree=1.0,
        deterministic=True,
        force_row_wise=True,
        num_threads=1,
        random_state=seed,
        verbosity=-1,
    )


def _trees(
    jobs: Sequence[Job],
    first: Month,
    offsets: Mapping[UUID, int],
    seed: int,
    explain: bool,
) -> tuple[dict[UUID, Forecasts], dict[UUID, tuple[tuple[str, Decimal], ...]]]:
    """One LightGBM for the jobs of one cut, forecasting month after month."""
    usable = [j for j in jobs if np.std(np.asarray(j[2], dtype=np.float64)) > 0]
    if len(usable) < 2:
        return {}, {}
    df = _frame(usable, first, offsets)
    categories = {f"{key}|{cut}": i for i, (key, cut, _, _) in enumerate(usable)}
    df["category"] = pd.Categorical(df["unique_id"].map(categories))
    fcst = MLForecast(
        models={TREES: _trees_model(seed)},
        freq="MS",
        lags=list(LAGS),
        lag_transforms={1: [RollingMean(window_size=3), RollingMean(window_size=6)]},
        date_features=["month"],
        target_transforms=[LocalStandardScaler()],
        num_threads=1,
    )
    fcst.fit(df, static_features=["category"], dropna=True)
    captured: list[pd.DataFrame] = []

    def capture(features: pd.DataFrame) -> pd.DataFrame:
        if not captured:
            captured.append(features.copy())
        return features

    callback: Callable[[pd.DataFrame], pd.DataFrame] | None = capture if explain else None
    out = fcst.predict(h=HORIZON, before_predict_callback=callback)
    steps = {f"{key}|{cut}": n for key, cut, _, n in usable}
    forecasts: dict[UUID, Forecasts] = {}
    for uid, rows in out.groupby("unique_id", sort=False):
        values = rows[TREES].to_numpy()[: steps[str(uid)]]
        if np.all(np.isfinite(values)):
            forecasts[UUID(str(uid).partition("|")[0])] = _cents(values)
    contributions: dict[UUID, tuple[tuple[str, Decimal], ...]] = {}
    if captured:
        trees: lgb.LGBMRegressor = fcst.models_[TREES]  # type: ignore[assignment]
        booster = trees.booster_
        x = captured[0]
        contrib = np.asarray(booster.predict(x, pred_contrib=True), dtype=np.float64)
        raw = contrib[:, :-1]  # the last column is the bias
        names = [_feature(c) for c in x.columns]
        for row, uid in zip(raw, fcst.ts.uids, strict=True):
            total = float(np.abs(row).sum())
            ranked = sorted(zip(names, np.abs(row), strict=True), key=lambda p: -p[1])
            contributions[UUID(str(uid).partition("|")[0])] = tuple(
                (name, Decimal(f"{value / total:.4f}") if total else Decimal(0))
                for name, value in ranked
            )
    return forecasts, contributions


def _feature(column: str) -> str:
    """mlforecast's column names, as FEATURES names them."""
    return {
        "rolling_mean_lag1_window_size3": "mean3",
        "rolling_mean_lag1_window_size6": "mean6",
    }.get(column, column)


def run(
    series: Sequence[SeriesInput],
    *,
    first: Month,
    n: int,
    cuts: Sequence[int],
    seed: int = DEFAULT_SEED,
) -> Result:
    """Every candidate at each household cut (training on the months up to it) and for the
    months to come. The averages run on any training; the other candidates from FIRST_CUT
    months of a series' own history."""
    offsets = {s.key: s.offset for s in series}
    floats = {s.key: [float(v) for v in s.values] for s in series}
    backtests: dict[UUID, dict[str, dict[int, Forecasts]]] = {
        s.key: {m: {} for m in ORDER} for s in series
    }
    futures: dict[UUID, dict[str, Forecasts]] = {s.key: {} for s in series}
    stats_jobs: list[Job] = []
    trees_jobs: dict[int, list[Job]] = {}
    for s in series:
        values = floats[s.key]
        for c in [*cuts, n]:
            if c <= s.offset:
                continue  # not started yet: kwak_core counts it as 0
            training = values[: c - s.offset]
            steps = HORIZON if c == n else min(HORIZON, n - c)
            for model, fc in _averages(training, steps).items():
                if c == n:
                    futures[s.key][model] = fc
                else:
                    backtests[s.key][model][c] = fc
            if len(training) >= FIRST_CUT:
                job = (s.key, c, training, steps)
                stats_jobs.append(job)
                trees_jobs.setdefault(c, []).append(job)
    for (key, c), by_model in _stats(stats_jobs, first, offsets).items():
        for model, fc in by_model.items():
            if c == n:
                futures[key][model] = fc
            else:
                backtests[key][model][c] = fc
    contributions: dict[UUID, tuple[tuple[str, Decimal], ...]] = {}
    for c, jobs in sorted(trees_jobs.items()):
        found, explained = _trees(jobs, first, offsets, seed, explain=c == n)
        for key, fc in found.items():
            if c == n:
                futures[key][TREES] = fc
            else:
                backtests[key][TREES][c] = fc
        contributions.update(explained)
    return Result(backtests, futures, contributions)
