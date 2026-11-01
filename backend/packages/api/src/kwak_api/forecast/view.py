"""The Forecast page's figures (spec §4.14 F-FCT-6), from `services.forecast`: the months
entered and forecast with their bands, the month so far, the targets and objectives this month
and this year, the income, what each forecast rests on and the back-test. Words are the page's:
here only numbers, months and the names of the methods."""

from calendar import monthrange
from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from kwak_analytics.forecast import TREES
from kwak_core import forecast as core
from kwak_core.budget import Month, month_range, target_for
from kwak_core.categories import CategoryKind
from kwak_core.forecast import BASELINE, Band, Risk
from kwak_core.money import quantize
from pydantic import BaseModel

from kwak_api.services import forecast as service

ZERO = Decimal(0)
SHARE = Decimal("0.0001")
TABLE_HISTORY = 24
"""The months entered the page sends: its table's two years, its chart's last one."""
FEATURES = 3
"""The trees' most telling features, by their share."""
TOTALS = ("income", "spent", "saved", "rest")
KIND_TOTAL = {
    CategoryKind.INCOME: "income",
    CategoryKind.EXPENSE: "spent",
    CategoryKind.SAVINGS: "saved",
}

type Total = Literal["income", "spent", "saved", "rest"]


def _share(value: Decimal) -> Decimal:
    return value.quantize(SHARE)


def _share_or_none(value: Decimal | None) -> Decimal | None:
    return None if value is None else _share(value)


class ForecastBandOut(BaseModel):
    low: Decimal
    point: Decimal
    high: Decimal
    """`low` and `high` equal `point` when there is no band yet."""

    @classmethod
    def of(cls, b: Band) -> "ForecastBandOut":
        return cls(low=quantize(b.low), point=quantize(b.point), high=quantize(b.high))


class ForecastHistoryMonthOut(BaseModel):
    month: str
    income: Decimal
    spent: Decimal
    saved: Decimal
    fixed: Decimal
    """The part of `spent` that fixed expenses paid."""
    rest: Decimal


class ForecastAheadMonthOut(BaseModel):
    month: str
    income: ForecastBandOut
    spent: ForecastBandOut
    saved: ForecastBandOut
    rest: ForecastBandOut
    fixed: Decimal
    """The fixed expenses due that month, known: part of `spent`."""


class ForecastTotalsOut(BaseModel):
    """The twelve months added up, with the band of twelve-month sums."""

    income: ForecastBandOut
    spent: ForecastBandOut
    saved: ForecastBandOut
    rest: ForecastBandOut
    banded: bool
    """False when the history is too short for the rest's band."""


class MonthSoFarOut(BaseModel):
    month: str
    entered: Decimal
    """Spent so far this month, never used by the forecast."""
    expected: ForecastBandOut
    elapsed: Decimal | None
    """The share of the month gone; null when the month is not today's."""


class ForecastAgainstOut(BaseModel):
    """A category against its target (expenses) or objective (savings)."""

    category_id: UUID
    name: str
    kind: CategoryKind
    point: Decimal
    band: ForecastBandOut
    target: Decimal
    risk: Risk
    """Of going over a target, or of falling short of an objective."""
    chance: Decimal | None
    """Of that, null without a band."""
    to_date: Decimal | None
    """The year only: entered to the last complete month; `point` less it is the forecast to
    December."""


class ForecastIncomeOut(BaseModel):
    category_id: UUID
    name: str
    band: ForecastBandOut


class ForecastSetAsideOut(BaseModel):
    model: str
    gain: Decimal
    """How much less it erred than the method kept, a share."""
    bias: Decimal
    """Entered less forecast, over what was entered, in the past months tested."""


class ForecastMethodOut(BaseModel):
    model: str | None
    """Null: the category has no line yet, its fixed expenses due only."""
    contest: bool
    """False: kept without a contest (too few months, or always the same)."""
    features: list[str]
    """The trees' most telling features, the first first; empty for another method."""
    set_aside: ForecastSetAsideOut | None
    """The candidate set aside for its optimism that erred least, when it erred less."""


class ForecastReliabilityOut(BaseModel):
    category_id: UUID
    name: str
    kind: CategoryKind
    method: ForecastMethodOut
    known: Decimal
    """The fixed expenses due over the twelve months."""
    mase: Decimal | None
    wape: Decimal | None
    versus: Decimal | None
    """How much less the method errs than the 6-month average, a share; 0 for the average itself
    and null without a method."""
    bias: Decimal | None
    optimism: Decimal | None
    """The bias turned so that optimistic is positive (less spending, more income or savings)."""
    coverage: Decimal | None
    """How often the months entered fell inside the band built from the errors known then."""


class ForecastScoreOut(BaseModel):
    name: Total
    mase: Decimal | None
    wape: Decimal | None
    rmsse: Decimal | None
    bias_share: Decimal | None
    """Income, spent and saved: entered less forecast, over what was entered."""
    bias_per_month: Decimal | None
    """The rest: entered less forecast, a month; negative when it was forecast above."""


class BacktestPointOut(BaseModel):
    month: str
    entered: Decimal
    forecast: Decimal
    """Forecast one month ahead, from the months before only."""


class BacktestOut(BaseModel):
    name: Literal["income", "spent"]
    points: list[BacktestPointOut]


class ForecastBandNoteOut(BaseModel):
    none: bool
    """No band yet: too few months to measure the errors."""
    widened_from: str | None
    """From this month, the band is the last one measured on enough months, widened."""


class ForecastEngineOut(BaseModel):
    cuts: int
    months: int
    seed: int
    version: int
    models: dict[str, str]
    """The foundation models that took part and their revisions; empty when not installed."""


class ForecastOut(BaseModel):
    origin: str
    """The last complete month."""
    history: list[ForecastHistoryMonthOut]
    """The last TABLE_HISTORY months entered, the oldest first."""
    ahead: list[ForecastAheadMonthOut]
    """The twelve months forecast, the current one first."""
    totals: ForecastTotalsOut
    month: MonthSoFarOut
    rest_above: Decimal | None
    """In the back-test, how much a month the rest was forecast above what was left, when it
    matters; null otherwise."""
    band: ForecastBandNoteOut
    targets: list[ForecastAgainstOut]
    """This month's expense targets, the likeliest overrun first."""
    objectives: list[ForecastAgainstOut]
    """This month's savings objectives, the likeliest shortfall first."""
    year: int
    year_targets: list[ForecastAgainstOut]
    """Each target's and objective's year: to date plus the forecast to December."""
    income: list[ForecastIncomeOut]
    """This month's income by category."""
    reliability: list[ForecastReliabilityOut]
    bias_limit: Decimal
    """Beyond this optimism in the back-test, a candidate is set aside (F-FCT-4)."""
    scores: list[ForecastScoreOut]
    backtest: list[BacktestOut]
    engine: ForecastEngineOut


class ForecastPageOut(BaseModel):
    complete_months: int
    needed: int
    forecast: ForecastOut | None
    """Null below `needed` complete months."""


def history_totals(r: service.Result) -> dict[str, list[Decimal]]:
    """Each month of the history's income, spent and saved, its fixed spending and rest."""
    n = len(r.history)
    out = {name: [ZERO] * n for name in ("income", "spent", "saved", "fixed")}
    for c in r.categories:
        s = r.forecast.categories[c.id].series
        name = KIND_TOTAL[c.kind]
        for i in range(n):
            out[name][i] += s.total[i]
            if c.kind is CategoryKind.EXPENSE:
                out["fixed"][i] += s.fixed[i]
    out["rest"] = [out["income"][i] - out["spent"][i] - out["saved"][i] for i in range(n)]
    return out


def known_spent(r: service.Result) -> list[Decimal]:
    out = [ZERO] * core.HORIZON
    for c in r.categories:
        if c.kind is CategoryKind.EXPENSE:
            for k, v in enumerate(r.forecast.categories[c.id].known):
                out[k] += v
    return out


_RANK = {Risk.LIKELY: 0, Risk.POSSIBLE: 1, Risk.UNLIKELY: 2}


def _ranked(items: list[ForecastAgainstOut]) -> list[ForecastAgainstOut]:
    return sorted(items, key=lambda a: (_RANK[a.risk], -(a.chance or ZERO)))


def month_targets(r: service.Result, kind: CategoryKind) -> list[ForecastAgainstOut]:
    """This month's expense targets (the chance of going over) or savings objectives (of
    falling short), the likeliest first."""
    month = r.ahead[0]
    check = core.against_objective if kind is CategoryKind.SAVINGS else core.against_target
    out = []
    for c in r.categories:
        target = r.target(c.id, month) if c.kind is kind else None
        if target is None:
            continue
        cf = r.forecast.categories[c.id]
        b = cf.bands[0]
        risk, chance = check(b.point, cf.steps.at(1), target)
        out.append(
            ForecastAgainstOut(
                category_id=c.id,
                name=c.name,
                kind=kind,
                point=quantize(b.point),
                band=ForecastBandOut.of(b),
                target=quantize(target),
                risk=risk,
                chance=_share_or_none(chance),
                to_date=None,
            )
        )
    return _ranked(out)


def year_targets(r: service.Result) -> list[ForecastAgainstOut]:
    """Each target's and objective's year: to date plus the forecast to December (F-BUD-10)."""
    first = r.ahead[0]
    left = 12 - first.month + 1
    year_months = month_range(Month(first.year, 1), Month(first.year, 12))
    out = []
    for c in r.categories:
        if c.kind is CategoryKind.INCOME:
            continue
        history = r.targets.get(c.id, [])
        in_force = [v for m in year_months if (v := target_for(history, m)) is not None]
        if not in_force:
            continue
        full = sum(in_force, ZERO)
        cf = r.forecast.categories[c.id]
        to_date = sum(
            (v for m, v in zip(r.history, cf.series.total, strict=True) if m.year == first.year),
            ZERO,
        )
        rest = r.forecast.year(c.id, left)
        point = to_date + rest.point
        whole = Band(to_date + rest.low, point, to_date + rest.high)
        errs = core.sum_errors(cf.errors, left)
        check = core.against_objective if c.kind is CategoryKind.SAVINGS else core.against_target
        risk, chance = check(point, errs, full)
        out.append(
            ForecastAgainstOut(
                category_id=c.id,
                name=c.name,
                kind=c.kind,
                point=quantize(point),
                band=ForecastBandOut.of(whole),
                target=quantize(full),
                risk=risk,
                chance=_share_or_none(chance),
                to_date=quantize(to_date),
            )
        )
    return _ranked(out)


def _method(r: service.Result, category: UUID) -> ForecastMethodOut:
    cf = r.forecast.categories[category]
    choice = cf.choice
    if choice is None:
        return ForecastMethodOut(model=None, contest=False, features=[], set_aside=None)
    features: list[str] = []
    if choice.contest and choice.model == TREES and (shares := r.contributions.get(category)):
        features = [name for name, _ in shares[:FEATURES]]
    set_aside = None
    if choice.contest:
        kept = choice.gains.get(choice.model, core.ONE)
        better = [m for m in choice.set_aside if choice.gains[m] < kept]
        if better:
            model = min(better, key=lambda m: choice.gains[m])
            bias = choice.scores[model].bias
            if bias is not None:
                set_aside = ForecastSetAsideOut(
                    model=model,
                    gain=_share(1 - choice.gains[model] / kept),
                    bias=_share(bias),
                )
    return ForecastMethodOut(
        model=choice.model, contest=choice.contest, features=features, set_aside=set_aside
    )


def reliability(r: service.Result) -> list[ForecastReliabilityOut]:
    out = []
    for c in r.categories:
        cf = r.forecast.categories[c.id]
        choice = cf.choice
        score = choice.scores.get(choice.model) if choice else None
        gain = choice.gains.get(choice.model) if choice else None
        versus = None
        if choice is not None:
            versus = (
                _share(1 - gain) if gain is not None and choice.model != BASELINE else Decimal(0)
            )
        bias = score.bias if score else None
        out.append(
            ForecastReliabilityOut(
                category_id=c.id,
                name=c.name,
                kind=c.kind,
                method=_method(r, c.id),
                known=quantize(sum(cf.known, ZERO)),
                mase=_share_or_none(score.mase if score else None),
                wape=_share_or_none(score.wape if score else None),
                versus=versus,
                bias=_share_or_none(bias),
                optimism=None if bias is None else _share(core.optimism(bias, c.kind)),
                coverage=_share_or_none(cf.coverage),
            )
        )
    return out


def _one_ahead(r: service.Result, name: str, actual: Sequence[Decimal]) -> list[BacktestPointOut]:
    """At each cut, what was entered the month after it, and the total forecast for it."""
    errs = r.forecast.total_errors[name]
    return [
        BacktestPointOut(
            month=str(r.history[c]),
            entered=quantize(actual[c]),
            forecast=quantize(actual[c] - errs[(c, 1)]),
        )
        for c in core.cuts(len(r.history))
        if (c, 1) in errs
    ]


def scores(r: service.Result, actuals: dict[str, list[Decimal]]) -> list[ForecastScoreOut]:
    out = []
    for name in TOTALS:
        errs = r.forecast.total_errors[name]
        actual = actuals[name]
        forecasts: dict[int, list[Decimal]] = {}
        for (c, k), e in sorted(errs.items()):
            forecasts.setdefault(c, []).append(actual[c + k - 1] - e)
        s = core.score(actual, forecasts)
        bias = r.forecast.bias(name)
        out.append(
            ForecastScoreOut(
                name=name,
                mase=_share_or_none(s.mase if s else None),
                wape=_share_or_none(s.wape if s else None),
                rmsse=_share_or_none(s.rmsse if s else None),
                bias_share=(
                    _share_or_none(bias.share) if bias is not None and name != "rest" else None
                ),
                bias_per_month=(
                    quantize(bias.per_month) if bias is not None and name == "rest" else None
                ),
            )
        )
    return out


def _band_note(r: service.Result) -> ForecastBandNoteOut:
    steps = core.Errors.of(r.forecast.total_errors["spent"])
    if steps.widened_from == 1:
        return ForecastBandNoteOut(none=True, widened_from=None)
    if steps.widened_from is not None:
        return ForecastBandNoteOut(none=False, widened_from=str(r.ahead[steps.widened_from - 1]))
    return ForecastBandNoteOut(none=False, widened_from=None)


def _month_so_far(r: service.Result, today: date) -> MonthSoFarOut:
    month = r.ahead[0]
    entered = sum(
        (r.entered.get(c.id, ZERO) for c in r.categories if c.kind is CategoryKind.EXPENSE), ZERO
    )
    elapsed = (
        _share(Decimal(today.day) / monthrange(today.year, today.month)[1])
        if (today.year, today.month) == (month.year, month.month)
        else None
    )
    return MonthSoFarOut(
        month=str(month),
        entered=quantize(entered),
        expected=ForecastBandOut.of(r.forecast.spent[0]),
        elapsed=elapsed,
    )


def forecast_out(r: service.Result, today: date) -> ForecastOut:
    f = r.forecast
    h = history_totals(r)
    start = max(0, len(r.history) - TABLE_HISTORY)
    fixed = known_spent(r)
    over = {name: f.total_over(name, core.HORIZON) for name in TOTALS}
    return ForecastOut(
        origin=str(r.origin),
        history=[
            ForecastHistoryMonthOut(
                month=str(m),
                income=quantize(h["income"][i]),
                spent=quantize(h["spent"][i]),
                saved=quantize(h["saved"][i]),
                fixed=quantize(h["fixed"][i]),
                rest=quantize(h["rest"][i]),
            )
            for i, m in enumerate(r.history)
            if i >= start
        ],
        ahead=[
            ForecastAheadMonthOut(
                month=str(m),
                income=ForecastBandOut.of(f.income[k]),
                spent=ForecastBandOut.of(f.spent[k]),
                saved=ForecastBandOut.of(f.saved[k]),
                rest=ForecastBandOut.of(f.rest[k]),
                fixed=quantize(fixed[k]),
            )
            for k, m in enumerate(r.ahead)
        ],
        totals=ForecastTotalsOut(
            income=ForecastBandOut.of(over["income"]),
            spent=ForecastBandOut.of(over["spent"]),
            saved=ForecastBandOut.of(over["saved"]),
            rest=ForecastBandOut.of(over["rest"]),
            banded=core.sum_errors(f.total_errors["rest"], core.HORIZON) is not None,
        ),
        month=_month_so_far(r, today),
        rest_above=None if (above := f.rest_above()) is None else quantize(above),
        band=_band_note(r),
        targets=month_targets(r, CategoryKind.EXPENSE),
        objectives=month_targets(r, CategoryKind.SAVINGS),
        year=r.ahead[0].year,
        year_targets=year_targets(r),
        income=[
            ForecastIncomeOut(
                category_id=c.id, name=c.name, band=ForecastBandOut.of(f.categories[c.id].bands[0])
            )
            for c in r.categories
            if c.kind is CategoryKind.INCOME
        ],
        reliability=reliability(r),
        bias_limit=core.BIAS,
        scores=scores(r, h),
        backtest=[
            BacktestOut(name=name, points=_one_ahead(r, name, h[name]))
            for name in ("income", "spent")
        ],
        engine=ForecastEngineOut(
            cuts=len(core.cuts(len(r.history))),
            months=len(r.history),
            seed=r.seed,
            version=r.engine_version,
            models=dict(r.foundation),
        ),
    )
