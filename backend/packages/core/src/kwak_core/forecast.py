"""The cash-flow forecast (spec §4.14 F-FCT-1 to 6, invariants §8.41 to 44): the monthly series by
category, their fixed and variable parts, the back-test's cuts, errors and scores, the choice of a
model per series, the conformal bands and the chances.

The models themselves run in `kwak_analytics.forecast`, which hands back each candidate's
forecasts at every cut and for the months to come; everything here is `Decimal` and pure.

A cut `c` trains on the first `c` months of the history (indices 0 to c - 1) and forecasts step
`k` for month index `c + k - 1`.
"""

import enum
import math
from collections import defaultdict
from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from uuid import UUID

from kwak_core.budget import Month, month_range
from kwak_core.categories import CategoryKind
from kwak_core.fixed import STEP, FixedExpense, is_due
from kwak_core.goals import add_months, months_between
from kwak_core.labels import normalise

ZERO = Decimal(0)
ONE = Decimal(1)

HORIZON = 12
"""Months forecast, the current one first."""
MIN_HISTORY = 12
"""Complete months needed for a forecast."""
MAX_HISTORY = 60
SEASONAL_HISTORY = 24
"""Months of a series' history from which the same month last year competes."""
FIRST_CUT = 13
FIRST_CUT_SHORT = 7
"""The first cut below SEASONAL_HISTORY months of history."""
MIN_ERRORS = 9
LOW, HIGH = Decimal("0.1"), Decimal("0.9")
MARGIN = Decimal("0.10")
"""How much lower a candidate's MASE must be than the baseline's to replace it."""
BIAS = Decimal("0.05")
"""The optimistic bias, of the absolute amounts entered, above which a candidate is set aside."""
BIAS_FLOOR = Decimal(10)
"""And its errors' average a month, in euros: a small series is not judged on cents."""
REST_BIAS = Decimal("0.02")
"""The rest's bias, of the income, above which the summary warns (with BIAS_FLOOR)."""
MIN_ACTIVE = 3
"""Months holding a line for a series to have a contest."""
MIN_CUTS = FIRST_CUT - FIRST_CUT_SHORT
"""Cuts a candidate must cover to be judged: those a short history gives the models."""
LIKELY, POSSIBLE = Decimal("0.5"), Decimal("0.2")

BASELINE = "baseline"
SEASONAL = "seasonal_naive"
"""The one candidate that waits for SEASONAL_HISTORY months of a series."""

type Errs = Mapping[tuple[int, int], Decimal]
"""Back-test errors (actual - forecast) by (cut, step)."""


# F-FCT-1, 2: the series


@dataclass(frozen=True)
class Piece:
    """A line, or one part of a split line, signed as stored."""

    category_id: UUID
    day: date
    amount: Decimal
    label: str
    fixed_expense_id: UUID | None = None
    """The fixed expense it was created from."""
    split: bool = False


@dataclass(frozen=True)
class Series:
    kind: CategoryKind
    total: tuple[Decimal, ...]
    """Each month's figure: received, spent, or saved net of withdrawals."""
    fixed: tuple[Decimal, ...]
    """Of which, the lines matched to a fixed expense."""
    matched: tuple[Decimal, ...]
    """Those occurrences at their fixed expense's current amount: the back-test's known part."""
    start: int | None
    """The month index of its first line; None without any."""

    @property
    def variable(self) -> tuple[Decimal, ...]:
        return tuple(t - f for t, f in zip(self.total, self.fixed, strict=True))

    @property
    def length(self) -> int:
        """Months from its first line to the origin."""
        return 0 if self.start is None else len(self.total) - self.start


def history(first: Month | None, origin: Month) -> list[Month]:
    """From the first month holding a line to the origin, MAX_HISTORY months at most."""
    if first is None or first > origin:
        return []
    return month_range(max(first, add_months(origin, 1 - MAX_HISTORY)), origin)


def figure(amount: Decimal, kind: CategoryKind) -> Decimal:
    """A line as the month's figures count it: received, spent or saved (F-DSH-4)."""
    return amount if kind is CategoryKind.INCOME else -amount


def on_schedule(item: FixedExpense, month: Month) -> bool:
    """Its schedule extended back before its first month (F-FCT-2); pauses ignored."""
    if item.last is not None and month > item.last:
        return False
    return months_between(item.first, month) % STEP[item.frequency] == 0


def build_series(
    pieces: Iterable[Piece],
    kinds: Mapping[UUID, CategoryKind],
    items: Sequence[FixedExpense],
    months: Sequence[Month],
) -> dict[UUID, Series]:
    """Every category's series over `months`; pieces outside them are never read."""
    index = {m: i for i, m in enumerate(months)}
    n = len(months)
    total: dict[UUID, list[Decimal]] = {c: [ZERO] * n for c in kinds}
    fixed: dict[UUID, list[Decimal]] = {c: [ZERO] * n for c in kinds}
    matched: dict[UUID, list[Decimal]] = {c: [ZERO] * n for c in kinds}
    start: dict[UUID, int] = {}
    by_id = {item.id: item for item in items}
    typed: dict[tuple[int, UUID, str], list[Piece]] = defaultdict(list)
    from_item: dict[tuple[int, UUID], list[tuple[UUID, Decimal]]] = defaultdict(list)
    for p in pieces:
        i = index.get(Month.of(p.day))
        if i is None:
            continue
        kind = kinds[p.category_id]
        value = figure(p.amount, kind)
        total[p.category_id][i] += value
        start[p.category_id] = min(start.get(p.category_id, i), i)
        if p.fixed_expense_id is not None:
            fixed[p.category_id][i] += value
            from_item[(i, p.fixed_expense_id)].append((p.category_id, value))
        elif not p.split:
            typed[(i, p.category_id, normalise(p.label))].append(p)
    # Created from a fixed expense: one occurrence at its current amount, shared by the
    # parts of a split line as they share the line.
    for (i, item_id), parts in from_item.items():
        item = by_id.get(item_id)
        whole = sum((v for _, v in parts), ZERO)
        for category, value in parts:
            if item is None or whole == 0:
                matched[category][i] += value
            else:
                matched[category][i] += figure(item.amount, kinds[item.category_id]) * value / whole
    for item in items:
        if item.category_id not in kinds:
            continue
        kind = kinds[item.category_id]
        for i, month in enumerate(months):
            if (i, item.id) in from_item or not on_schedule(item, month):
                continue
            candidates = typed.get((i, item.category_id, normalise(item.label)))
            if not candidates:
                continue
            line = min(candidates, key=lambda p: (abs(p.amount - item.amount), p.day))
            candidates.remove(line)
            fixed[item.category_id][i] += figure(line.amount, kind)
            matched[item.category_id][i] += figure(item.amount, kind)
    return {
        c: Series(kinds[c], tuple(total[c]), tuple(fixed[c]), tuple(matched[c]), start.get(c))
        for c in kinds
    }


def known(
    items: Sequence[FixedExpense],
    kinds: Mapping[UUID, CategoryKind],
    *,
    skipped: Collection[tuple[UUID, Month]],
    months: Sequence[Month],
) -> dict[UUID, tuple[Decimal, ...]]:
    """Each category's known part in the months to come: the occurrences due, not skipped."""
    out = {c: [ZERO] * len(months) for c in kinds}
    for item in items:
        if item.category_id not in kinds:
            continue
        for i, month in enumerate(months):
            if is_due(item, month) and (item.id, month) not in skipped:
                out[item.category_id][i] += figure(item.amount, kinds[item.category_id])
    return {c: tuple(v) for c, v in out.items()}


# F-FCT-4: the back-test


def cuts(n: int) -> list[int]:
    """The cuts of a history of n months: from the 13th month (the 7th below 24 months) to the
    one before the origin."""
    if n < MIN_HISTORY:
        return []
    first = FIRST_CUT if n >= SEASONAL_HISTORY else FIRST_CUT_SHORT
    return list(range(first, n))


def own_cuts(n: int, *, start: int) -> list[int]:
    """The household's cuts where a series starting at `start` has history enough."""
    return [start + c for c in cuts(n - start)]


def errors(
    actual: Sequence[Decimal], forecasts: Mapping[int, Sequence[Decimal]]
) -> dict[tuple[int, int], Decimal]:
    """Actual - forecast by (cut, step), up to the origin."""
    out: dict[tuple[int, int], Decimal] = {}
    for c, values in forecasts.items():
        for k, value in enumerate(values, start=1):
            t = c + k - 1
            if t >= len(actual):
                break
            out[(c, k)] = actual[t] - value
    return out


@dataclass(frozen=True)
class Score:
    mase: Decimal
    rmsse: Decimal
    wape: Decimal | None
    """None when the months forecast hold no amount."""
    bias: Decimal | None = None
    """The errors' sum over the absolute amounts entered: above 0, less forecast than entered.
    None when the months forecast hold no amount."""
    per_month: Decimal = ZERO
    """The errors' average, in euros a month."""


def score(
    actual: Sequence[Decimal], forecasts: Mapping[int, Sequence[Decimal]], *, start: int = 0
) -> Score | None:
    """None when a training never changed from month to month (the MASE is undefined), or
    when nothing was forecast. The training runs from the series' first month, `start`."""
    abs_scaled = sq_scaled = abs_err = abs_actual = err = ZERO
    count = 0
    for c, values in forecasts.items():
        changes = [actual[t] - actual[t - 1] for t in range(start + 1, c)]
        scale = sum((abs(d) for d in changes), ZERO) / len(changes) if changes else ZERO
        if scale == 0:
            return None
        scale2 = sum((d * d for d in changes), ZERO) / len(changes)
        for (_, k), e in errors(actual, {c: values}).items():
            abs_scaled += abs(e) / scale
            sq_scaled += e * e / scale2
            abs_err += abs(e)
            err += e
            abs_actual += abs(actual[c + k - 1])
            count += 1
    if count == 0:
        return None
    return Score(
        abs_scaled / count,
        (sq_scaled / count).sqrt(),
        abs_err / abs_actual if abs_actual else None,
        err / abs_actual if abs_actual else None,
        err / count,
    )


@dataclass(frozen=True)
class Choice:
    model: str
    scores: Mapping[str, Score]
    """Each candidate scored on the series' cuts it covers, the baseline on all of them."""
    gains: Mapping[str, Decimal]
    """Each candidate's MASE over the baseline's on the same cuts (below 1: it errs less)."""
    contest: bool
    """False when the baseline was kept without one."""
    set_aside: frozenset[str] = frozenset()
    """The candidates left out of the contest for forecasting too optimistically."""


def optimism(bias: Decimal, kind: CategoryKind) -> Decimal:
    """How optimistic a bias reads: less spending, more income, or savings either way."""
    if kind is CategoryKind.EXPENSE:
        return bias
    if kind is CategoryKind.INCOME:
        return -bias
    return abs(bias)


def _too_optimistic(s: Score, base: Score, kind: CategoryKind) -> bool:
    if s.bias is None or base.bias is None:
        return False
    mine = optimism(s.bias, kind)
    return (
        mine > BIAS
        and optimism(s.per_month, kind) > BIAS_FLOOR
        and mine > optimism(base.bias, kind)
    )


def choose(
    actual: Sequence[Decimal],
    backtests: Mapping[str, Mapping[int, Sequence[Decimal]]],
    order: Sequence[str],
    *,
    cuts: Sequence[int],
    kind: CategoryKind,
    start: int = 0,
) -> Choice:
    """The candidate whose MASE is lowest against the baseline's on the same cuts, when at
    least MARGIN below it; ties to the simpler (earlier in `order`). A candidate needing a
    longer training than the first cuts is judged on the cuts it covers, MIN_CUTS at least
    (all of them when there are fewer). A candidate more optimistic than the baseline on the
    same cuts, beyond BIAS and BIAS_FLOOR, is set aside first; the baseline never is."""
    no_contest = Choice(BASELINE, {}, {}, contest=False)
    if not cuts or sum(1 for v in actual if v != 0) < MIN_ACTIVE:
        return no_contest
    base_found = backtests.get(BASELINE, {})
    if not all(c in base_found for c in cuts):
        return no_contest
    base = score(actual, {c: base_found[c] for c in cuts}, start=start)
    if base is None:
        return no_contest
    scores: dict[str, Score] = {BASELINE: base}
    gains: dict[str, Decimal] = {BASELINE: ONE}
    set_aside: set[str] = set()
    for model in order:
        found = backtests.get(model, {})
        covered = [c for c in cuts if c in found]
        if model == BASELINE or len(covered) < min(MIN_CUTS, len(cuts)):
            continue
        s = score(actual, {c: found[c] for c in covered}, start=start)
        b = score(actual, {c: base_found[c] for c in covered}, start=start)
        if s is None or b is None or b.mase == 0:
            continue
        scores[model] = s
        gains[model] = s.mase / b.mase
        if _too_optimistic(s, b, kind):
            set_aside.add(model)
    kept = [m for m in gains if m not in set_aside]
    best = min(kept, key=lambda m: (gains[m], order.index(m) if m in order else -1))
    model = best if best != BASELINE and gains[best] <= ONE - MARGIN else BASELINE
    return Choice(model, scores, gains, contest=True, set_aside=frozenset(set_aside))


# F-FCT-5: bands and chances


@dataclass(frozen=True)
class Band:
    low: Decimal
    point: Decimal
    high: Decimal


def quantiles(errs: Sequence[Decimal]) -> tuple[Decimal, Decimal] | None:
    """The conformal ranks ⌈(n+1)·0.1⌉ and ⌈(n+1)·0.9⌉ of n errors; None below MIN_ERRORS."""
    n = len(errs)
    if n < MIN_ERRORS:
        return None
    ranked = sorted(errs)
    low = math.ceil((n + 1) * LOW)
    high = min(n, math.ceil((n + 1) * HIGH))
    return ranked[low - 1], ranked[high - 1]


def band(point: Decimal, errs: Sequence[Decimal] | None, *, floor: bool) -> Band:
    """The forecast with its 80 % band, which always holds it; `floor` for spending and
    income, never below zero."""
    q = quantiles(errs) if errs else None
    low, high = (point, point) if q is None else (point + min(q[0], ZERO), point + max(q[1], ZERO))
    if floor:
        return Band(max(low, ZERO), max(point, ZERO), max(high, ZERO))
    return Band(low, point, high)


def chance_above(point: Decimal, errs: Sequence[Decimal], threshold: Decimal) -> Decimal:
    """(k + 1) / (n + 1), k of the n errors carrying the forecast above the threshold."""
    k = sum(1 for e in errs if point + e > threshold)
    return Decimal(k + 1) / Decimal(len(errs) + 1)


def chance_below(point: Decimal, errs: Sequence[Decimal], threshold: Decimal) -> Decimal:
    k = sum(1 for e in errs if point + e < threshold)
    return Decimal(k + 1) / Decimal(len(errs) + 1)


@dataclass(frozen=True)
class Errors:
    """A series' errors by step, those past the longest step with enough widened."""

    steps: tuple[tuple[Decimal, ...], ...]
    """Steps 1 to HORIZON; an empty tuple where there is no band."""
    widened_from: int | None
    """The first step whose errors are widened; 1 when there is no band at all."""

    @classmethod
    def of(cls, errs: Errs) -> "Errors":
        raw: dict[int, list[Decimal]] = defaultdict(list)
        for (_, k), e in sorted(errs.items()):
            raw[k].append(e)
        enough = [k for k in range(1, HORIZON + 1) if len(raw[k]) >= MIN_ERRORS]
        if not enough:
            return cls(((),) * HORIZON, 1)
        h0 = max(enough)
        steps = []
        for k in range(1, HORIZON + 1):
            if k <= h0:
                steps.append(tuple(raw[k]))
            else:
                factor = (Decimal(k) / Decimal(h0)).sqrt()
                steps.append(tuple(e * factor for e in raw[h0]))
        return cls(tuple(steps), h0 + 1 if h0 < HORIZON else None)

    def at(self, step: int) -> list[Decimal] | None:
        values = self.steps[step - 1]
        return list(values) if len(values) >= MIN_ERRORS else None


def sum_errors(errs: Errs, k: int) -> list[Decimal] | None:
    """The errors of each cut's first k months added up, for a sum over k months; None
    without MIN_ERRORS of them."""
    by_cut: dict[int, dict[int, Decimal]] = defaultdict(dict)
    for (c, step), e in errs.items():
        by_cut[c][step] = e
    out = [
        sum((steps[j] for j in range(1, k + 1)), ZERO)
        for _, steps in sorted(by_cut.items())
        if all(j in steps for j in range(1, k + 1))
    ]
    return out if len(out) >= MIN_ERRORS else None


def coverage(errs: Errs) -> Decimal | None:
    """How often the actual month fell inside its band, each band built only from the errors
    known at its cut (sequential conformal); None when no band could be built."""
    inside = tried = 0
    for (c, k), e in errs.items():
        prior = [e2 for (c2, k2), e2 in errs.items() if k2 == k and c2 + k <= c]
        q = quantiles(prior)
        if q is None:
            continue
        tried += 1
        inside += min(q[0], ZERO) <= e <= max(q[1], ZERO)  # the band shown holds its forecast
    return Decimal(inside) / Decimal(tried) if tried else None


# Assembling


def _add(a: Errs, b: Errs, sign: int = 1) -> dict[tuple[int, int], Decimal]:
    out = dict(a)
    for key, e in b.items():
        out[key] = out.get(key, ZERO) + sign * e
    return out


@dataclass(frozen=True)
class CategoryForecast:
    series: Series
    choice: Choice | None
    """None for a category without lines."""
    known: tuple[Decimal, ...]
    bands: tuple[Band, ...]
    errors: Mapping[tuple[int, int], Decimal]
    """The back-test's, known part included."""
    steps: Errors
    coverage: Decimal | None


@dataclass(frozen=True)
class Bias:
    share: Decimal | None
    """The errors' sum over the absolute amounts entered; None without any."""
    per_month: Decimal
    """The errors' average, in euros a month: above 0, less forecast than entered."""


@dataclass(frozen=True)
class Forecast:
    n: int
    """Months of history."""
    categories: Mapping[UUID, CategoryForecast]
    income: tuple[Band, ...]
    spent: tuple[Band, ...]
    saved: tuple[Band, ...]
    rest: tuple[Band, ...]
    total_errors: Mapping[str, Mapping[tuple[int, int], Decimal]]
    """By total: "income", "spent", "saved", "rest"."""
    entered_at: Mapping[str, Mapping[tuple[int, int], Decimal]] = field(default_factory=dict)
    """By total and (cut, step): what was entered in the categories with an error there."""

    def bias(self, name: str) -> Bias | None:
        """A total's bias in the back-test, from its summed errors (F-FCT-6)."""
        errs = self.total_errors[name]
        if not errs:
            return None
        at = self.entered_at[name]
        err = sum(errs.values(), ZERO)
        entered = sum((abs(at.get(key, ZERO)) for key in errs), ZERO)
        return Bias(err / entered if entered else None, err / len(errs))

    def rest_above(self) -> Decimal | None:
        """How much a month the rest was forecast above what was left, when beyond REST_BIAS
        of the income and BIAS_FLOOR; None otherwise."""
        rest = self.bias("rest")
        errs = self.total_errors["rest"]
        if rest is None:
            return None
        income = self.entered_at["income"]
        average = sum((income.get(key, ZERO) for key in errs), ZERO) / len(errs)
        above = -rest.per_month
        return above if above > BIAS_FLOOR and above > REST_BIAS * average else None

    def year(self, category: UUID, k: int) -> Band:
        """The category's first k months added up, with the band of k-month sums."""
        cf = self.categories[category]
        point = sum((b.point for b in cf.bands[:k]), ZERO)
        return band(
            point, sum_errors(cf.errors, k), floor=cf.series.kind is not CategoryKind.SAVINGS
        )

    def total_over(self, name: str, k: int) -> Band:
        bands: tuple[Band, ...] = getattr(self, name)
        point = sum((b.point for b in bands[:k]), ZERO)
        return band(point, sum_errors(self.total_errors[name], k), floor=name in FLOORED)


FLOORED = frozenset({"income", "spent"})
TOTAL_OF = {
    CategoryKind.INCOME: "income",
    CategoryKind.EXPENSE: "spent",
    CategoryKind.SAVINGS: "saved",
}


def _category(
    s: Series,
    known_part: Sequence[Decimal],
    backtests: Mapping[str, Mapping[int, Sequence[Decimal]]],
    futures: Mapping[str, Sequence[Decimal]],
    order: Sequence[str],
    household_cuts: Sequence[int],
) -> CategoryForecast:
    floor = s.kind is not CategoryKind.SAVINGS
    if s.start is None:
        bands = tuple(band(v, None, floor=floor) for v in known_part)
        return CategoryForecast(s, None, tuple(known_part), bands, {}, Errors.of({}), None)
    n, start = len(s.total), s.start
    allowed = [m for m in order if m != SEASONAL or s.length >= SEASONAL_HISTORY]
    variable = s.variable
    choice = choose(
        variable,
        {m: backtests[m] for m in allowed if m in backtests},
        allowed,
        cuts=own_cuts(n, start=start),
        kind=s.kind,
        start=start,
    )
    chosen = backtests.get(choice.model, {})
    errs: dict[tuple[int, int], Decimal] = {}
    for c in household_cuts:
        steps = min(HORIZON, n - c)
        if c <= start:
            forecast = [ZERO] * steps  # not started: it was 0
        elif c in chosen:
            forecast = list(chosen[c])
        else:
            continue  # too short a training for the chosen candidate: its errors only
        for k, value in enumerate(forecast[:steps], start=1):
            t = c + k - 1
            errs[(c, k)] = s.total[t] - s.matched[t] - value
    steps_errs = Errors.of(errs)
    future = futures.get(choice.model) or futures.get(BASELINE) or [ZERO] * HORIZON
    bands = tuple(
        band(known_part[k] + future[k], steps_errs.at(k + 1), floor=floor) for k in range(HORIZON)
    )
    return CategoryForecast(s, choice, tuple(known_part), bands, errs, steps_errs, coverage(errs))


def assemble(
    series: Mapping[UUID, Series],
    known: Mapping[UUID, Sequence[Decimal]],
    backtests: Mapping[UUID, Mapping[str, Mapping[int, Sequence[Decimal]]]],
    futures: Mapping[UUID, Mapping[str, Sequence[Decimal]]],
    order: Sequence[str],
) -> Forecast:
    """Each category's choice, forecast and band, and the totals' (F-FCT-4, 5).

    `backtests[category][model][cut]` are a model's forecasts of the variable part at a cut,
    `futures[category][model]` its forecasts for the HORIZON months to come; `order` lists the
    candidates from the simplest.
    """
    n = len(next(iter(series.values())).total) if series else 0
    household_cuts = cuts(n)
    categories = {
        c: _category(
            s,
            known.get(c, (ZERO,) * HORIZON),
            backtests.get(c, {}),
            futures.get(c, {}),
            order,
            household_cuts,
        )
        for c, s in series.items()
    }
    points: dict[str, list[Decimal]] = {name: [ZERO] * HORIZON for name in TOTAL_OF.values()}
    total_errs: dict[str, dict[tuple[int, int], Decimal]] = {name: {} for name in TOTAL_OF.values()}
    for cf in categories.values():
        name = TOTAL_OF[cf.series.kind]
        for k in range(HORIZON):
            points[name][k] += cf.bands[k].point
        total_errs[name] = _add(total_errs[name], cf.errors)
    rest_errs = _add(_add(total_errs["income"], total_errs["spent"], -1), total_errs["saved"], -1)
    total_errs["rest"] = rest_errs
    rest = [points["income"][k] - points["spent"][k] - points["saved"][k] for k in range(HORIZON)]

    def bands(name: str, values: Sequence[Decimal]) -> tuple[Band, ...]:
        steps = Errors.of(total_errs[name])
        return tuple(band(v, steps.at(k + 1), floor=name in FLOORED) for k, v in enumerate(values))

    entered_at: dict[str, dict[tuple[int, int], Decimal]] = {name: {} for name in TOTAL_OF.values()}
    for cf in categories.values():
        at = entered_at[TOTAL_OF[cf.series.kind]]
        for c, k in cf.errors:
            at[(c, k)] = at.get((c, k), ZERO) + cf.series.total[c + k - 1]
    entered_at["rest"] = {
        key: entered_at["income"].get(key, ZERO)
        - entered_at["spent"].get(key, ZERO)
        - entered_at["saved"].get(key, ZERO)
        for key in rest_errs
    }
    return Forecast(
        n,
        categories,
        bands("income", points["income"]),
        bands("spent", points["spent"]),
        bands("saved", points["saved"]),
        bands("rest", rest),
        total_errs,
        entered_at,
    )


# F-FCT-6: against the targets


class Risk(enum.StrEnum):
    """Of going over a target (likely over, may go over, within), or of falling short of a
    savings objective (likely short, may fall short, on track)."""

    LIKELY = "likely"
    POSSIBLE = "possible"
    UNLIKELY = "unlikely"


def _risk(chance: Decimal) -> Risk:
    if chance >= LIKELY:
        return Risk.LIKELY
    return Risk.POSSIBLE if chance >= POSSIBLE else Risk.UNLIKELY


def against_target(
    point: Decimal, errs: Sequence[Decimal] | None, target: Decimal
) -> tuple[Risk, Decimal | None]:
    """The risk of going over and its chance; without a band, the forecast alone decides."""
    if errs is None or len(errs) < MIN_ERRORS:
        return (Risk.LIKELY if point > target else Risk.UNLIKELY), None
    chance = chance_above(point, errs, target)
    return _risk(chance), chance


def against_objective(
    point: Decimal, errs: Sequence[Decimal] | None, objective: Decimal
) -> tuple[Risk, Decimal | None]:
    """The risk of saving less than the objective and its chance."""
    if errs is None or len(errs) < MIN_ERRORS:
        return (Risk.LIKELY if point < objective else Risk.UNLIKELY), None
    chance = chance_below(point, errs, objective)
    return _risk(chance), chance
