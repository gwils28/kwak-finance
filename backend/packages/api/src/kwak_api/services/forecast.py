"""The cash-flow forecast (spec §4.14): the household's lines, fixed expenses and targets read
once, the series built by `kwak_core.forecast`, the candidates run by
`kwak_analytics.forecast`. Nothing is saved: the page computes it when it opens, and the last
few results are kept in memory, keyed by everything they were computed from."""

import threading
from collections import OrderedDict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from uuid import UUID

from kwak_analytics import forecast as engine
from kwak_analytics import foundation
from kwak_core import forecast as core
from kwak_core.budget import Month, target_for
from kwak_core.categories import CategoryKind
from kwak_core.fixed import FixedExpense as CoreFixed
from kwak_core.goals import add_months
from sqlalchemy import select
from sqlalchemy.orm import Session

from kwak_api.models import FixedExpense, FixedSkip, SpendingLine, SpendingLinePart
from kwak_api.services import spending, spending_budget

ZERO = Decimal(0)
CACHED = 8


class NotEnoughHistoryError(Exception):
    """Fewer than MIN_HISTORY complete months: `months` says how many there are."""

    def __init__(self, months: int) -> None:
        super().__init__(f"{months} complete months, {core.MIN_HISTORY} needed")
        self.months = months


@dataclass(frozen=True)
class Category:
    id: UUID
    name: str
    kind: CategoryKind


@dataclass(frozen=True)
class Result:
    origin: Month
    history: list[Month]
    ahead: list[Month]
    """The HORIZON months forecast, the current one first."""
    categories: list[Category]
    """In the household's order."""
    forecast: core.Forecast
    contributions: Mapping[UUID, tuple[tuple[str, Decimal], ...]]
    entered: Mapping[UUID, Decimal]
    """What each category holds so far in the current month, never used by the forecast."""
    targets: spending_budget.Targets
    seed: int
    foundation: Mapping[str, str] = field(default_factory=dict)
    """The foundation models that took part and their revisions; empty when not installed."""
    engine_version: int = engine.ENGINE_VERSION

    def target(self, category: UUID, month: Month) -> Decimal | None:
        """The target or objective in force for the category that month (F-BUD-1, 9)."""
        return target_for(self.targets.get(category, []), month)


def pieces(db: Session, household_id: UUID, first: Month, last: Month) -> list[core.Piece]:
    """Every line with a category of its own and every part of a split line, from `first` to
    `last` included."""
    start, end = first.first_day(), last.next().first_day()
    in_period = (
        SpendingLine.household_id == household_id,
        SpendingLine.day >= start,
        SpendingLine.day < end,
    )
    own = db.execute(
        select(
            SpendingLine.category_id,
            SpendingLine.day,
            SpendingLine.amount,
            SpendingLine.label,
            SpendingLine.fixed_expense_id,
        )
        .where(*in_period, SpendingLine.category_id.is_not(None))
        .order_by(SpendingLine.day, SpendingLine.created_at, SpendingLine.id)
    )
    parts = db.execute(
        select(
            SpendingLinePart.category_id,
            SpendingLine.day,
            SpendingLinePart.amount,
            SpendingLine.label,
            SpendingLine.fixed_expense_id,
        )
        .join(SpendingLine, SpendingLine.id == SpendingLinePart.line_id)
        .where(*in_period)
        .order_by(SpendingLine.day, SpendingLine.created_at, SpendingLinePart.position)
    )
    out = [core.Piece(c, d, a, label, f) for c, d, a, label, f in own if c is not None]
    out += [core.Piece(c, d, a, label, f, split=True) for c, d, a, label, f in parts]
    return out


def _skipped(
    db: Session, items: Sequence[FixedExpense], months: Sequence[Month]
) -> set[tuple[UUID, Month]]:
    rows = db.execute(
        select(FixedSkip.fixed_expense_id, FixedSkip.month).where(
            FixedSkip.fixed_expense_id.in_([i.id for i in items]),
            FixedSkip.month >= months[0].first_day(),
            FixedSkip.month <= months[-1].first_day(),
        )
    )
    return {(item, Month.of(month)) for item, month in rows}


_cache: OrderedDict[object, tuple[core.Forecast, engine.Result]] = OrderedDict()
_lock = threading.Lock()
"""Dash answers in threads."""


def _run(
    series: Mapping[UUID, core.Series],
    known: Mapping[UUID, Sequence[Decimal]],
    first: Month,
    n: int,
    seed: int,
) -> tuple[core.Forecast, engine.Result]:
    key = (
        first,
        n,
        seed,
        engine.ENGINE_VERSION,
        tuple(sorted(foundation.revisions().items())),
        tuple(sorted((str(k), s) for k, s in series.items())),
        tuple(sorted((str(k), tuple(v)) for k, v in known.items())),
    )
    with _lock:
        if key in _cache:
            _cache.move_to_end(key)
            return _cache[key]
    inputs = [
        engine.SeriesInput(
            key,
            s.variable[s.start :],
            s.start,
        )
        for key, s in series.items()
        if s.start is not None
    ]
    result = engine.run(inputs, first=first, n=n, cuts=core.cuts(n), seed=seed)
    forecast = core.assemble(series, known, result.backtests, result.futures, result.order)
    with _lock:
        _cache[key] = (forecast, result)
        while len(_cache) > CACHED:
            _cache.popitem(last=False)
    return forecast, result


def compute(
    db: Session, household_id: UUID, today: date, *, seed: int = engine.DEFAULT_SEED
) -> Result:
    """Raises NotEnoughHistoryError below MIN_HISTORY complete months."""
    this_month = Month.of(today)
    origin = this_month.previous()
    months = core.history(spending_budget.first_month(db, household_id), origin)
    if len(months) < core.MIN_HISTORY:
        raise NotEnoughHistoryError(len(months))
    rows = spending.categories(db, household_id)
    kinds = {c.id: c.kind for c in rows}
    items = spending.fixed_expenses(db, household_id)
    core_items: list[CoreFixed] = [spending.core_item(i) for i in items]
    ahead = [add_months(this_month, k) for k in range(core.HORIZON)]
    series = core.build_series(
        pieces(db, household_id, months[0], origin), kinds, core_items, months
    )
    known = core.known(core_items, kinds, skipped=_skipped(db, items, ahead), months=ahead)
    forecast, result = _run(series, known, months[0], len(months), seed)
    entered: dict[UUID, Decimal] = {c.id: ZERO for c in rows}
    for p in pieces(db, household_id, this_month, this_month):
        entered[p.category_id] += core.figure(p.amount, kinds[p.category_id])
    return Result(
        origin=origin,
        history=months,
        ahead=ahead,
        categories=[Category(c.id, c.name, c.kind) for c in rows],
        forecast=forecast,
        contributions=result.contributions,
        entered=entered,
        targets=spending_budget.targets(db, household_id),
        seed=seed,
        foundation=dict(result.foundation),
    )
