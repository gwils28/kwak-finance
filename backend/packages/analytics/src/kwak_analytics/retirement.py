"""Retirement on the Monte Carlo engine (spec §4.13 F-RET-4, invariants §8.38-39): the
sustainable withdrawal, the largest multiple of €100 a month, indexed to inflation, that each
outcome's liquid wealth at the household's retirement pays alone to the horizon without a
Shortfall, in 9 outcomes in 10 and in half of them.

The plan's months before the retirement draw exactly as `montecarlo.simulate` does (the same
streams, the same steps). From the retirement, only the liquid categories matter, since the
home, equipment, private equity and exotic holdings are never taken: their growth is drawn
once from the same streams, then each path's own largest withdrawal is found by bisection, all
paths at once (more withdrawn never leaves a path more wealth, so a path that fails at an
amount fails at every larger one)."""

from dataclasses import dataclass
from decimal import Decimal

import numpy as np
import numpy.typing as npt
from kwak_core.projection import NEVER_TAKEN, SHORTFALL_RATE

from kwak_analytics.montecarlo import (
    DEFAULT_SEED,
    PATHS,
    Floats,
    Scenario,
    draw,
    rules,
    streams,
    withdraw,
)

STEP = 100
"""The withdrawal is a multiple of €100, rounded down (F-RET-4)."""
NINE_TENTHS = Decimal("0.1")
"""At most one outcome in ten may fail."""
HALF = Decimal("0.5")
CENT = 0.005
"""What is left to take below half a cent is no Shortfall: floats do not end exactly at 0."""


@dataclass(frozen=True)
class Withdrawal:
    nine_tenths: Decimal | None
    """Paid in 9 outcomes in 10; None when more than one in ten already have a Shortfall at the
    household's retirement."""
    half: Decimal | None


@dataclass(frozen=True)
class _Retired:
    """Each path at the household's retirement, and its liquid categories' growth after."""

    held: Floats
    """The liquid categories' holdings: (paths, liquid)."""
    short: npt.NDArray[np.bool_]
    """Paths already in Shortfall."""
    growth: npt.NDArray[np.float32]
    """(months after, paths, liquid)."""
    index: Floats
    """(1 + inflation)^(t / 12) for each month from the retirement on."""
    first: list[int]
    pro_rata: npt.NDArray[np.bool_]


def _retire(plan: Scenario, retired_at: int, paths: int, seed: int) -> _Retired:
    months = len(plan.savings)
    if not 1 <= retired_at <= months:
        raise ValueError("the household retires within the plan's months")
    cats = plan.categories
    r = rules(cats)
    generators = streams(cats, seed)
    held = np.tile(np.array([float(c.start) for c in cats]), (paths, 1))
    short = np.zeros(paths)
    rate = float(SHORTFALL_RATE) / 12
    for t in range(1, retired_at):
        held = held * np.exp(r.mu + r.sigma * draw(generators, paths))
        short = short * (1 + rate)
        saved = float(plan.savings[t - 1])
        if saved >= 0:
            repaid = np.minimum(short, saved)
            short = short - repaid
            held = held + (saved - repaid)[:, None] * r.share
        else:
            held, missing = withdraw(held, np.full(paths, -saved), r.first, r.pro_rata)
            short = short + missing
        held = np.maximum(held, 0)
    liquid = [k for k, c in enumerate(cats) if c.preset not in NEVER_TAKEN]
    after = months - retired_at + 1
    growth = np.empty((after, paths, len(liquid)), dtype=np.float32)
    kept = [generators[k] for k in liquid]
    for j in range(after):
        z = draw(kept, paths)
        growth[j] = np.exp(r.mu[liquid] + r.sigma[liquid] * z)
    first = [liquid.index(k) for k in r.first if k in liquid]
    pro_rata = r.pro_rata[liquid]
    inflation = float(plan.inflation)
    index = (1 + inflation) ** (np.arange(retired_at, months + 1) / 12)
    return _Retired(held[:, liquid], short > CENT, growth, index, first, pro_rata)


def _lasts(retired: _Retired, amounts: Floats) -> npt.NDArray[np.bool_]:
    """The paths whose liquid wealth pays `amounts` (today's euros, one per path) each month to
    the horizon, indexed to inflation, without a Shortfall."""
    held = retired.held.copy()
    ok = ~retired.short
    for j in range(retired.growth.shape[0]):
        held = held * retired.growth[j]
        held, missing = withdraw(held, amounts * retired.index[j], retired.first, retired.pro_rata)
        held = np.maximum(held, 0)
        ok &= missing <= CENT
    return ok


def _largest(retired: _Retired) -> npt.NDArray[np.int64]:
    """Each path's largest withdrawal, in hundreds of euros; -1 for a path already in
    Shortfall."""
    paths = retired.held.shape[0]
    first_growth = retired.growth[0].max(axis=1) if retired.growth.shape[0] else np.ones(paths)
    # Above the wealth after a month's best growth, the first month already fails.
    high = np.floor(retired.held.sum(axis=1) * first_growth / STEP).astype(np.int64) + 2
    low = np.where(retired.short, -1, 0)
    high = np.where(retired.short, 0, high)
    while np.any(high - low > 1):
        middle = (low + high) // 2
        ok = _lasts(retired, middle.astype(np.float64) * STEP)
        searching = high - low > 1
        low = np.where(searching & ok, middle, low)
        high = np.where(searching & ~ok, middle, high)
    return low


def _at(largest: npt.NDArray[np.int64], failing: Decimal) -> Decimal | None:
    """The largest amount at which no more than `failing` of the paths fail."""
    ordered = np.sort(largest)
    value = int(ordered[int(float(failing) * len(ordered))])
    return None if value < 0 else Decimal(value * STEP)


def sustainable_withdrawal(
    plan: Scenario, *, retired_at: int, paths: int = PATHS, seed: int = DEFAULT_SEED
) -> Withdrawal:
    """`plan`: the plan's months to the horizon (F-RET-3); `retired_at`: the household's
    retirement month, counted from the start (1 for a household already retired)."""
    largest = _largest(_retire(plan, retired_at, paths, seed))
    return Withdrawal(_at(largest, NINE_TENTHS), _at(largest, HALF))


def failing_share(
    plan: Scenario,
    *,
    retired_at: int,
    amount: Decimal,
    paths: int = PATHS,
    seed: int = DEFAULT_SEED,
) -> Decimal:
    """The share of outcomes that cannot pay `amount` a month from the retirement on."""
    retired = _retire(plan, retired_at, paths, seed)
    ok = _lasts(retired, np.full(paths, float(amount)))
    return Decimal(int((~ok).sum())) / Decimal(paths)
