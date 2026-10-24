"""The wealth projection's Monte Carlo engine (spec §4.11 F-SIM-4, invariants §8.23-29).

The one place money is drawn in floating point (spec §6): its inputs come in `Decimal` from
`kwak_core.projection`, its outputs go back as `Decimal` cents. Month by month, each asset
category grows by a lognormal return drawn independently, then receives its share of the
savings or gives its part of the withdrawals, never falling below zero; what cannot be taken
builds up as the Shortfall debt, borrowed at `SHORTFALL_RATE` and repaid first; the debts follow
their repayment, already worked out in `Decimal`. The same assumptions, seed and engine version
always give the same paths. Each category draws from its own stream, keyed by its id, so every
scenario of a visit uses the same draws for a category whatever the others are.

Months are counted from the start: month 0 is the starting point, month t the t-th after it.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

import numpy as np
import numpy.typing as npt
from kwak_core.money import quantize
from kwak_core.projection import (
    FIRST_TAKEN,
    NEVER_TAKEN,
    SHORTFALL_RATE,
    Assumption,
    monthly_params,
)

ENGINE_VERSION = 1
"""Raised whenever the same inputs and seed could give different paths."""
PATHS = 5000
DEFAULT_SEED = 20261022
"""Fixed, and shown on the page."""
PERCENTILES = (10, 25, 50, 75, 90)

Floats = npt.NDArray[np.float64]


@dataclass(frozen=True)
class Category:
    id: UUID
    preset: str | None
    start: Decimal
    """Its total at the start."""
    assumption: Assumption
    share: Decimal
    """Of the savings, the allocation summing to 1 over the categories."""


@dataclass(frozen=True)
class Scenario:
    categories: Sequence[Category]
    savings: Sequence[Decimal]
    """Months 1 to n, current euros, the debts' freed payments included (savings_path)."""
    debts: Sequence[Decimal]
    """What the debts owe at the end of months 1 to n, current euros (amortise, summed)."""
    start_debts: Decimal
    inflation: Decimal


@dataclass(frozen=True)
class Flows:
    """A month's movements on each path, kept for the tests of invariant §8.27."""

    returns: Floats
    added: Floats
    taken: Floats
    missing: Floats
    """Withdrawals the assets could not cover, added to the Shortfall."""
    interest: Floats
    """The Shortfall's interest this month."""
    repaid: Floats
    """Savings that repaid the Shortfall."""


def _cents(value: float) -> Decimal:
    """Back to `Decimal` cents, half up as all money is (the float's shortest form first, so
    0.125 is 0.13)."""
    return quantize(Decimal(repr(value)))


@dataclass(frozen=True)
class Outcome:
    net: Floats
    """Net worth, current euros: (months + 1, paths)."""
    shortfall: Floats
    """The Shortfall debt: (months + 1, paths)."""
    category_median: Floats
    """Each category's own median, current euros: (months + 1, categories)."""
    deflator: Floats
    """(1 + inflation)^(t / 12) for each month t."""
    seed: int
    assets: Floats | None = None
    """(months + 1, paths, categories), only when kept."""
    flows: Sequence[Flows] | None = None

    @property
    def months(self) -> int:
        return int(self.net.shape[0]) - 1

    def _unit(self, today: bool) -> Floats:
        return self.deflator if today else np.ones_like(self.deflator)

    def percentiles(self, *, today: bool = True) -> list[dict[int, Decimal]]:
        """Each month's 10th, 25th, 50th, 75th and 90th percentiles of net worth, in today's
        euros (or current ones), to the cent."""
        q = np.percentile(self.net, PERCENTILES, axis=1) / self._unit(today)
        return [
            {p: _cents(float(q[k, t])) for k, p in enumerate(PERCENTILES)}
            for t in range(self.months + 1)
        ]

    def medians_by_category(self, *, today: bool = True) -> list[list[Decimal]]:
        """Each category's median month by month; together they need not add up to the median
        net worth."""
        m = self.category_median / self._unit(today)[:, None]
        return [[_cents(float(v)) for v in row] for row in m]

    def shortfall_median(self, *, today: bool = True) -> list[Decimal]:
        """The Shortfall's median month by month, as owed (positive)."""
        m = np.median(self.shortfall, axis=1) / self._unit(today)
        return [_cents(float(v)) for v in m]

    def _threshold(self, amount: Decimal, today: bool) -> Floats:
        """The amount in each month's current euros: an amount in today's euros grows with the
        inflation, so switching the unit changes no chance (invariant §8.28)."""
        return float(amount) * self._unit(today)

    def _month(self, month: int) -> int:
        if not 0 <= month <= self.months:
            raise ValueError(f"a month is from 0 to {self.months}")
        return month

    def chance(self, amount: Decimal, month: int, *, today: bool = True) -> Decimal:
        """The share of outcomes whose net worth is at least `amount` in `month`."""
        month = self._month(month)
        hit = self.net[month] >= self._threshold(amount, today)[month]
        return Decimal(int(hit.sum())) / Decimal(hit.size)

    def _reached(self, amount: Decimal, today: bool) -> npt.NDArray[np.bool_]:
        above = self.net >= self._threshold(amount, today)[:, None]
        return np.logical_or.accumulate(above, axis=0)

    def reached_share(self, amount: Decimal, month: int, *, today: bool = True) -> Decimal:
        """The share of outcomes that have reached `amount` at least once by `month`."""
        month = self._month(month)
        hit = self._reached(amount, today)[month]
        return Decimal(int(hit.sum())) / Decimal(hit.size)

    def reached_by(self, amount: Decimal, share: Decimal, *, today: bool = True) -> int | None:
        """The first month by which `share` of the outcomes have reached `amount` once; None
        within the horizon (invariant §8.29)."""
        counts = self._reached(amount, today).sum(axis=1)
        needed = float(share) * self.net.shape[1]
        months = np.nonzero(counts >= needed)[0]
        return int(months[0]) if months.size else None

    def shortfall_share(self) -> Decimal:
        """The share of outcomes that run into a Shortfall at some point."""
        hit = (self.shortfall > 0).any(axis=0)
        return Decimal(int(hit.sum())) / Decimal(hit.size)


def simulate(
    scenario: Scenario, *, paths: int = PATHS, seed: int = DEFAULT_SEED, keep: bool = False
) -> Outcome:
    """`keep` keeps every category of every path and the month's flows, for the tests."""
    cats = scenario.categories
    months = len(scenario.savings)
    if len(scenario.debts) != months:
        raise ValueError("savings and debts cover the same months")
    if paths < 1:
        raise ValueError("a simulation draws one path at least")
    if not cats and any(scenario.savings):
        raise ValueError("savings with nowhere to go: no asset category")
    if cats and sum((c.share for c in cats), Decimal(0)) != 1:
        raise ValueError("the allocation's shares sum to 1")
    if any(c.start < 0 or not 0 <= c.share <= 1 for c in cats):
        raise ValueError("a category's start is positive and its share from 0 to 1")
    params = [monthly_params(c.assumption) for c in cats]
    mu = np.array([float(m) for m, _ in params])
    sigma = np.array([float(s) for _, s in params])
    share = np.array([float(c.share) for c in cats])
    presets = [c.preset for c in cats]
    first = [presets.index(p) for p in FIRST_TAKEN if p in presets]
    pro_rata = np.array(
        [k not in first and p not in NEVER_TAKEN for k, p in enumerate(presets)], dtype=bool
    )

    # One stream per category, keyed by its id: a scenario adding a category changes no other.
    streams = [np.random.default_rng(np.random.SeedSequence([seed, c.id.int])) for c in cats]
    monthly_rate = float(SHORTFALL_RATE) / 12
    held = np.tile(np.array([float(c.start) for c in cats]), (paths, 1))
    short = np.zeros(paths)
    debts = np.array([float(scenario.start_debts), *(float(d) for d in scenario.debts)])
    net = np.empty((months + 1, paths))
    shortfall = np.zeros((months + 1, paths))
    median = np.empty((months + 1, len(cats)))
    kept = np.empty((months + 1, paths, len(cats))) if keep else None
    flows: list[Flows] = []

    def record(t: int) -> None:
        net[t] = held.sum(axis=1) - debts[t] - short
        shortfall[t] = short
        median[t] = np.median(held, axis=0) if cats else 0
        if kept is not None:
            kept[t] = held

    record(0)
    for t in range(1, months + 1):
        # Drawn every month, whatever the scenario: every scenario shares the draws.
        z = (
            np.column_stack([g.standard_normal(paths) for g in streams])
            if cats
            else np.zeros((paths, 0))
        )
        before = held.sum(axis=1)
        held = held * np.exp(mu + sigma * z)
        returns = held.sum(axis=1) - before
        interest = short * monthly_rate
        short = short + interest
        saved = float(scenario.savings[t - 1])
        added = np.zeros(paths)
        taken = np.zeros(paths)
        missing = np.zeros(paths)
        repaid = np.zeros(paths)
        if saved >= 0:
            repaid = np.minimum(short, saved)
            short = short - repaid
            added = saved - repaid
            held = held + added[:, None] * share
        else:
            need = np.full(paths, -saved)
            for k in first:
                take = np.minimum(held[:, k], need)
                held[:, k] -= take
                need -= take
                taken += take
            pool = (held * pro_rata).sum(axis=1)
            take = np.minimum(pool, need)
            ratio = np.divide(take, pool, out=np.zeros(paths), where=pool > 0)
            held = held - held * pro_rata * ratio[:, None]
            need -= take
            taken += take
            missing = need
            short = short + need
        held = np.maximum(held, 0)
        if keep:
            flows.append(Flows(returns, added, taken, missing, interest, repaid))
        record(t)

    deflator = (1 + float(scenario.inflation)) ** (np.arange(months + 1) / 12)
    return Outcome(net, shortfall, median, deflator, seed, kept, flows if keep else None)
