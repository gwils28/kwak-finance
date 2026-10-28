"""The study's protocol, shared by every notebook so they all measure the same thing.

- Panels: households with enough months, cut to a common length, and their **variable** series
  (the app adds the fixed expenses, known in advance, on top of a model's forecast).
- Back-tests: rolling origins only (each cutoff trains on the months up to it), horizons 1 to
  12, never a month after the cutoff in a training set.
- Metrics, per series and cutoff, scaled by that training's own mean absolute month-to-month
  change (MASE, RMSSE, the scaled pinball loss and CRPS), as `kwak_core.forecast.score` does,
  plus the pooled WAPE and bias.
- Expensive runs are cached in `cache/` (git-ignored) so notebooks can reuse each other's.
"""

import math
import time
from collections.abc import Callable, Sequence
from pathlib import Path

import matplotlib as mpl
import numpy as np
import pandas as pd
from scipy import stats

import synthetic

CACHE = Path(__file__).parent / "cache"
H = 12
QUANTILES = (0.1, 0.5, 0.9)
LEVEL = 80

mpl.rcParams.update({"figure.dpi": 80, "savefig.dpi": 80, "figure.figsize": (9, 3.6)})


# Data


def full_panel() -> tuple[pd.DataFrame, list[synthetic.Intervention]]:
    return synthetic.panel()


def bench(
    months: int = 48, households: int = 60, *, seed: int = 0, df: pd.DataFrame | None = None
) -> pd.DataFrame:
    """The variable series of `households` drawn among those with `months` months or more, cut
    to their last `months` months."""
    if df is None:
        df, _ = full_panel()
    lengths = df.groupby("household")["t"].max() + 1
    eligible = lengths[lengths >= months].index.to_numpy()
    chosen = np.random.default_rng(seed).choice(eligible, size=households, replace=False)
    sub = df[df["household"].isin(chosen)]
    last = sub["ds"].max()
    sub = sub[sub["ds"] > last - pd.DateOffset(months=months)]
    return synthetic.variable_series(sub)


def cutoffs(v: pd.DataFrame, n_windows: int, step: int, h: int = H) -> list[pd.Timestamp]:
    last = v["ds"].max()
    return [last - pd.DateOffset(months=h + step * k) for k in reversed(range(n_windows))]


# Running things once


def cached(name: str, compute: Callable[[], pd.DataFrame]) -> pd.DataFrame:
    """The frame saved under `cache/name.parquet`, computed and saved when missing."""
    CACHE.mkdir(exist_ok=True)
    path = CACHE / f"{name}.parquet"
    if path.exists():
        return pd.read_parquet(path)
    start = time.perf_counter()
    out = compute()
    out.attrs = {}
    out.to_parquet(path)
    print(f"{name}: computed in {time.perf_counter() - start:.0f} s")
    return out


# Point metrics


def _scales(v: pd.DataFrame, cuts: Sequence[pd.Timestamp]) -> pd.DataFrame:
    """Each series' scale at each cutoff: mean |Δy| and mean Δy² of the training months."""
    rows = []
    for uid, g in v.sort_values("ds").groupby("unique_id", sort=False):
        ds, y = g["ds"].to_numpy(), g["y"].to_numpy(dtype=float)
        for c in cuts:
            train = y[ds <= np.datetime64(c)]
            d = np.diff(train)
            rows.append(
                (
                    uid,
                    c,
                    np.abs(d).mean() if d.size else np.nan,
                    (d**2).mean() if d.size else np.nan,
                )
            )
    return pd.DataFrame(rows, columns=["unique_id", "cutoff", "scale", "scale2"])


def with_steps(cv: pd.DataFrame) -> pd.DataFrame:
    """Adds `step`, the months ahead (1 to H) of each row of a cross-validation frame."""
    cv = cv.copy()
    cv["step"] = (cv["ds"].dt.year - cv["cutoff"].dt.year) * 12 + (
        cv["ds"].dt.month - cv["cutoff"].dt.month
    )
    return cv


def point_scores(cv: pd.DataFrame, v: pd.DataFrame, models: Sequence[str]) -> pd.DataFrame:
    """One row per series, cutoff and model: MASE, RMSSE and the sums WAPE and bias pool."""
    cv = with_steps(cv)
    scales = _scales(v, sorted(cv["cutoff"].unique()))
    cv = cv.merge(scales, on=["unique_id", "cutoff"])
    out = []
    for m in models:
        e = cv["y"] - cv[m]
        g = cv.assign(ae=e.abs(), se=e**2, e=e, ay=cv["y"].abs()).groupby(
            ["unique_id", "cutoff"], sort=False
        )
        agg = g.agg(
            ae=("ae", "mean"),
            se=("se", "mean"),
            sae=("ae", "sum"),
            sy=("ay", "sum"),
            se_sum=("e", "sum"),
            scale=("scale", "first"),
            scale2=("scale2", "first"),
        ).reset_index()
        agg["model"] = m
        agg["mase"] = agg["ae"] / agg["scale"]
        agg["rmsse"] = np.sqrt(agg["se"] / agg["scale2"])
        out.append(agg)
    res = pd.concat(out, ignore_index=True)
    return res.replace([np.inf, -np.inf], np.nan)


def summary(scores: pd.DataFrame, baseline: str | None = None) -> pd.DataFrame:
    """Per model: mean and median MASE (series with a zero scale left out), mean RMSSE, pooled
    WAPE and bias, and the share of series-cutoffs where it beats the baseline."""
    ok = scores.dropna(subset=["mase"])
    g = ok.groupby("model")
    out = pd.DataFrame(
        {
            "MASE": g["mase"].mean(),
            "MASE median": g["mase"].median(),
            "RMSSE": g["rmsse"].mean(),
            "WAPE": g["sae"].sum() / g["sy"].sum(),
            "bias": g["se_sum"].sum() / g["sy"].sum(),
        }
    )
    if baseline is not None:
        piv = ok.pivot_table(index=["unique_id", "cutoff"], columns="model", values="mase")
        out["beats baseline"] = (piv.lt(piv[baseline], axis=0)).mean()
    return out.sort_values("MASE")


def by_horizon(cv: pd.DataFrame, v: pd.DataFrame, models: Sequence[str]) -> pd.DataFrame:
    """Mean scaled absolute error by months ahead."""
    cv = with_steps(cv).merge(_scales(v, sorted(cv["cutoff"].unique())), on=["unique_id", "cutoff"])
    cv = cv[cv["scale"] > 0]
    return pd.DataFrame(
        {m: ((cv["y"] - cv[m]).abs() / cv["scale"]).groupby(cv["step"]).mean() for m in models}
    )


# Probabilistic metrics


def pinball(y: np.ndarray, q: np.ndarray, level: float) -> np.ndarray:
    d = y - q
    return np.maximum(level * d, (level - 1) * d)


def prob_scores(
    cv: pd.DataFrame,
    v: pd.DataFrame,
    name: str,
    quantile_cols: dict[float, str],
) -> pd.Series:
    """Coverage and width of the 80 % interval (10th to 90th percentile), the scaled pinball
    losses, a scaled CRPS approximated on the quantiles given, and the MSIS."""
    cv = cv.merge(_scales(v, sorted(cv["cutoff"].unique())), on=["unique_id", "cutoff"])
    cv = cv[cv["scale"] > 0]
    y, s = cv["y"].to_numpy(float), cv["scale"].to_numpy(float)
    lo, hi = cv[quantile_cols[0.1]].to_numpy(float), cv[quantile_cols[0.9]].to_numpy(float)
    losses = {lv: pinball(y, cv[c].to_numpy(float), lv) / s for lv, c in quantile_cols.items()}
    alpha = 0.2
    msis = (hi - lo + 2 / alpha * ((lo - y) * (y < lo) + (y - hi) * (y > hi))) / s
    return pd.Series(
        {
            "coverage 80%": float(((y >= lo) & (y <= hi)).mean()),
            "width / scale": float(np.mean((hi - lo) / s)),
            "MSIS": float(np.mean(msis)),
            **{f"pinball {int(lv * 100)}": float(np.mean(x)) for lv, x in losses.items()},
            "scaled CRPS": float(2 * np.mean([np.mean(x) for x in losses.values()])),
        },
        name=name,
    )


# Conformal bands, as the app builds them (kwak_core.forecast)


def conformal_quantiles(
    errs: np.ndarray, levels: tuple[float, float] = (0.1, 0.9), minimum: int = 9
):
    n = len(errs)
    if n < minimum:
        return None
    r = np.sort(errs)
    lo = math.ceil((n + 1) * levels[0])
    hi = min(n, math.ceil((n + 1) * levels[1]))
    return r[lo - 1], r[hi - 1]


def sequential_conformal(
    cv: pd.DataFrame, model: str, *, widen: bool = True, minimum: int = 9
) -> pd.DataFrame:
    """For every row of a dense cross-validation (cutoffs every month), the band built from the
    errors of the same series and months ahead known at its cutoff, the app's rank rule; past
    the longest step with `minimum` errors, that step's band widened by √(h / h₀)."""
    cv = with_steps(cv).sort_values(["unique_id", "cutoff", "step"])
    cv["err"] = cv["y"] - cv[model]
    out = []
    for _, g in cv.groupby("unique_id", sort=False):
        known_at = g["cutoff"] + pd.to_timedelta(0, "D")
        target = g["ds"].to_numpy()
        steps, errs, cuts = g["step"].to_numpy(), g["err"].to_numpy(float), g["cutoff"].to_numpy()
        lo_out, hi_out = np.full(len(g), np.nan), np.full(len(g), np.nan)
        for i in range(len(g)):
            known = target <= cuts[i]
            q = None
            k = steps[i]
            pool = errs[known & (steps == k)]
            q = conformal_quantiles(pool, minimum=minimum)
            if q is None and widen:
                for k0 in range(k - 1, 0, -1):
                    q0 = conformal_quantiles(errs[known & (steps == k0)], minimum=minimum)
                    if q0 is not None:
                        f = math.sqrt(k / k0)
                        q = (q0[0] * f, q0[1] * f)
                        break
            if q is not None:
                lo_out[i] = g[model].iloc[i] + min(q[0], 0)
                hi_out[i] = g[model].iloc[i] + max(q[1], 0)
        del known_at
        out.append(g.assign(lo=lo_out, hi=hi_out))
    return pd.concat(out)


# Comparing models


def friedman_nemenyi(scores: pd.DataFrame) -> tuple[pd.Series, float, float]:
    """Average ranks of the models' MASE over series-cutoffs, the Friedman test's p-value and
    the Nemenyi critical difference at 5 % (two models whose ranks differ by less are not told
    apart)."""
    piv = scores.pivot_table(index=["unique_id", "cutoff"], columns="model", values="mase").dropna()
    ranks = piv.rank(axis=1).mean().sort_values()
    p = stats.friedmanchisquare(*[piv[c] for c in piv.columns]).pvalue
    k, n = piv.shape[1], piv.shape[0]
    q = stats.studentized_range.ppf(0.95, k, 1e6) / math.sqrt(2)
    cd = q * math.sqrt(k * (k + 1) / (6 * n))
    return ranks, float(p), float(cd)


def diebold_mariano(e1: np.ndarray, e2: np.ndarray, h: int = 1) -> tuple[float, float]:
    """DM statistic on absolute-error differentials, with the Harvey small-sample correction;
    negative means the first forecast errs less."""
    d = np.abs(e1) - np.abs(e2)
    n = len(d)
    mean = d.mean()
    gamma = [np.mean((d[k:] - mean) * (d[: n - k] - mean)) for k in range(h)]
    var = (gamma[0] + 2 * sum(gamma[1:])) / n
    dm = mean / math.sqrt(var) if var > 0 else 0.0
    dm *= math.sqrt((n + 1 - 2 * h + h * (h - 1) / n) / n)
    p = 2 * stats.t.sf(abs(dm), df=n - 1)
    return float(dm), float(p)
