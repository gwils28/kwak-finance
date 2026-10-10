"""Budget plans by calendar period and their review (F-BUD-7, F-BUD-8, F-DSH-6).

A plan holds monthly targets for a year, a semester or a quarter. It is judged on its
envelope (monthly target x months), so a cheaper month offsets a dearer one. The review is
built on the budget matrix, so both always show the same spending (invariant 10).
"""

import calendar
import enum
import itertools
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from kwak_core.budget import (
    DEFAULT_BAND,
    BudgetStatus,
    Cell,
    Month,
    budget_status,
    build_matrix,
    month_range,
)
from kwak_core.kpis import change, savings_rate
from kwak_core.money import quantize, require_cents

ZERO = Decimal(0)


class PeriodKind(enum.StrEnum):
    YEAR = "year"
    SEMESTER = "semester"
    QUARTER = "quarter"


_LENGTH = {PeriodKind.YEAR: 12, PeriodKind.SEMESTER: 6, PeriodKind.QUARTER: 3}
_SUFFIX = {PeriodKind.YEAR: "", PeriodKind.SEMESTER: "S", PeriodKind.QUARTER: "Q"}
_LABEL = re.compile(r"(\d{4})(?:-([SQ])(\d))?")


@dataclass(frozen=True, order=True)
class Period:
    """A calendar period: `index` is 1 for a year, 1-2 for a semester, 1-4 for a quarter."""

    kind: PeriodKind
    year: int
    index: int

    def __post_init__(self) -> None:
        if not 1 <= self.index <= 12 // _LENGTH[self.kind]:
            raise ValueError(f"no such period: {self.kind} {self.index} of {self.year}")

    @classmethod
    def containing(cls, kind: PeriodKind, month: Month) -> "Period":
        return cls(kind, month.year, (month.month - 1) // _LENGTH[kind] + 1)

    @classmethod
    def parse(cls, text: str) -> "Period":
        """ "2027" -> the year, "2027-S1" -> a semester, "2027-Q3" -> a quarter."""
        match = _LABEL.fullmatch(text)
        if not match:
            raise ValueError(f"invalid period {text!r}, expected YYYY, YYYY-Sn or YYYY-Qn")
        year, letter, index = match.groups()
        if letter is None:
            return cls(PeriodKind.YEAR, int(year), 1)
        kind = PeriodKind.SEMESTER if letter == "S" else PeriodKind.QUARTER
        return cls(kind, int(year), int(index))

    @property
    def start(self) -> Month:
        return Month(self.year, (self.index - 1) * _LENGTH[self.kind] + 1)

    @property
    def end(self) -> Month:
        return Month(self.year, self.index * _LENGTH[self.kind])

    @property
    def months(self) -> list[Month]:
        return month_range(self.start, self.end)

    def __str__(self) -> str:
        if self.kind is PeriodKind.YEAR:
            return str(self.year)
        return f"{self.year}-{_SUFFIX[self.kind]}{self.index}"


@dataclass(frozen=True)
class Plan:
    """Monthly targets per category from `start` to `end`, within one calendar period.

    A plan closed early ends before its period; the replacement plan starts after its period's
    first month.
    """

    period: Period
    targets: Mapping[UUID, Decimal]
    start: Month
    end: Month
    expected_income: Decimal | None = None
    """Expected monthly income, for the planned savings."""
    note: str | None = None
    close_reason: str | None = None

    def __post_init__(self) -> None:
        if not self.period.start <= self.start <= self.end <= self.period.end:
            raise ValueError("a plan lies within its period")
        for amount in [*self.targets.values(), self.expected_income]:
            if amount is not None:
                require_cents(amount)
                if amount < 0:
                    raise ValueError("a target cannot be negative")

    @classmethod
    def covering(
        cls,
        period: Period,
        targets: Mapping[UUID, Decimal],
        *,
        expected_income: Decimal | None = None,
        note: str | None = None,
    ) -> "Plan":
        """A plan over its whole period."""
        return cls(period, targets, period.start, period.end, expected_income, note)

    @property
    def months(self) -> list[Month]:
        return month_range(self.start, self.end)

    @property
    def closed_early(self) -> bool:
        return self.end < self.period.end

    def __str__(self) -> str:
        return str(self.period)


def check_no_overlap(plans: Iterable[Plan]) -> None:
    """Raise when two plans share a month (invariant 8)."""
    ordered = sorted(plans, key=lambda p: (p.start, -len(p.months)))
    for before, after in itertools.pairwise(ordered):
        if after.start <= before.end:
            raise ValueError(f"budget plans overlap: {before} and {after}")


def new_plan(period: Period, latest: Plan | None) -> Plan:
    """A plan over `period`, pre-filled with the latest plan's targets and income."""
    if latest is None:
        return Plan.covering(period, {})
    return Plan.covering(period, dict(latest.targets), expected_income=latest.expected_income)


def editable(plan: Plan, today: date) -> bool:
    """Targets can be fixed until the end of the plan's first month; then close it early."""
    return today < plan.start.next().first_day()


def close_early(plan: Plan, last_month: Month, reason: str | None = None) -> Plan:
    """The plan ended after `last_month`, before its end, because life changed."""
    if not plan.start <= last_month < plan.end:
        raise ValueError("a plan closes early before its last month")
    return replace(plan, end=last_month, close_reason=reason)


def replacement(closed: Plan) -> Plan:
    """The plan for the rest of a plan closed early, pre-filled with its targets."""
    if not closed.closed_early:
        raise ValueError("only a plan closed early is replaced")
    return Plan(
        closed.period,
        dict(closed.targets),
        closed.end.next(),
        closed.period.end,
        closed.expected_income,
    )


def _monthly_targets(
    plan: Plan, categories: Sequence[tuple[UUID, UUID | None, str]]
) -> dict[UUID, Decimal]:
    """Each category's monthly target; a parent without one sums its children's."""
    result = {cid: plan.targets[cid] for cid, _, _ in categories if cid in plan.targets}
    for cid, parent, _ in categories:
        if parent is None and cid not in plan.targets:
            kids = [plan.targets[k] for k, p, _ in categories if p == cid and k in plan.targets]
            if kids:
                result[cid] = sum(kids, ZERO)
    return result


def envelopes(
    plan: Plan, categories: Sequence[tuple[UUID, UUID | None, str]]
) -> dict[UUID, Decimal]:
    """Monthly target x the plan's months, per category with a target (invariant 9)."""
    n = len(plan.months)
    return {cid: target * n for cid, target in _monthly_targets(plan, categories).items()}


def target_history(plans: Iterable[Plan]) -> dict[UUID, list[tuple[Month, Decimal | None]]]:
    """The plans as the budget matrix's target history: no target outside a plan."""
    ordered = sorted(plans, key=lambda p: p.start)
    ids = {cid for plan in ordered for cid in plan.targets}
    history: dict[UUID, list[tuple[Month, Decimal | None]]] = {cid: [] for cid in ids}
    for i, plan in enumerate(ordered):
        for cid in ids:
            history[cid].append((plan.start, plan.targets.get(cid)))
        following = ordered[i + 1].start if i + 1 < len(ordered) else None
        if following != plan.end.next():
            for cid in ids:
                history[cid].append((plan.end.next(), None))
    return history


def elapsed_share(plan: Plan, today: date) -> Decimal:
    """Completed months plus the current month prorated by days, over the plan's months."""
    current = Month.of(today)
    done = ZERO
    for month in plan.months:
        if month < current:
            done += 1
        elif month == current:
            done += Decimal(today.day) / calendar.monthrange(month.year, month.month)[1]
    return done / len(plan.months)


@dataclass(frozen=True)
class ReviewRow:
    category_id: UUID | None
    name: str
    parent_id: UUID | None
    level: int
    monthly_target: Decimal | None
    envelope: Decimal | None
    spent: Decimal
    gap: Decimal | None
    """spent - envelope."""
    gap_ratio: Decimal | None
    pace: Decimal | None
    """The envelope prorated to the time elapsed; the envelope itself once the plan is over."""
    status: BudgetStatus
    """Spent compared with the pace."""
    projection: Decimal | None
    """Linear projection of the spending at the end of the plan."""
    drift: Decimal | None
    """projection - envelope."""
    drifting: bool
    """Projected above the envelope (beyond the band) while the plan runs."""
    months_over: int = 0
    months_on: int = 0
    months_under: int = 0
    target_from_children: bool = False

    @property
    def pace_gap_ratio(self) -> Decimal | None:
        """(spent - pace) / pace: the gap the status is judged on; the gap ratio once over."""
        return (self.spent - self.pace) / self.pace if self.pace else None


@dataclass(frozen=True)
class Review:
    plan: Plan
    elapsed: Decimal
    finished: bool
    rows: list[ReviewRow]
    total: ReviewRow
    uncategorised: Decimal
    income: Decimal
    savings: Decimal
    savings_rate: Decimal | None
    planned_savings: Decimal | None
    drifting_rows: list[ReviewRow] = field(default_factory=list)
    """Drifting categories, the largest projected overrun first."""

    @property
    def provisional(self) -> bool:
        """Spending left to categorise may still change the result."""
        return self.uncategorised != 0


def _review_row(
    category_id: UUID | None,
    name: str,
    parent_id: UUID | None,
    level: int,
    cells: Sequence[Cell],
    elapsed: Decimal,
    current: Month,
    band: Decimal,
    from_children: bool = False,
) -> ReviewRow:
    spent = sum((c.spent for c in cells), ZERO)
    monthly = cells[0].target if cells else None
    envelope = None if monthly is None else monthly * len(cells)
    finished = elapsed == 1
    pace = None if envelope is None else quantize(envelope * elapsed)
    projection = quantize(spent / elapsed) if elapsed else None
    drift = None if envelope is None or projection is None else projection - envelope
    drifting = (
        not finished
        and envelope is not None
        and projection is not None
        and budget_status(projection, envelope, band) is BudgetStatus.OVER
    )
    completed = [c.status for c in cells if c.month < current]
    return ReviewRow(
        category_id,
        name,
        parent_id,
        level,
        monthly,
        envelope,
        spent,
        None if envelope is None else spent - envelope,
        (spent - envelope) / envelope if envelope else None,
        pace,
        budget_status(spent, pace, band),
        projection,
        drift,
        drifting,
        completed.count(BudgetStatus.OVER),
        completed.count(BudgetStatus.ON),
        completed.count(BudgetStatus.UNDER),
        from_children,
    )


def review_plan(
    plan: Plan,
    categories: Sequence[tuple[UUID, UUID | None, str]],
    spending: Mapping[tuple[UUID | None, Month], Decimal],
    income: Mapping[Month, Decimal],
    today: date,
    band: Decimal = DEFAULT_BAND,
) -> Review:
    """Where the plan stands on `today`: during the plan, or its final result once over."""
    matrix = build_matrix(categories, target_history([plan]), spending, plan.months, band)
    elapsed = elapsed_share(plan, today)
    current = Month.of(today)
    rows = [
        _review_row(
            r.category_id,
            r.name,
            r.parent_id,
            r.level,
            r.cells,
            elapsed,
            current,
            band,
            r.target_from_children,
        )
        for r in matrix.rows
    ]
    total = _review_row(None, "Total", None, 0, matrix.total.cells, elapsed, current, band)
    earned = sum((income.get(m, ZERO) for m in plan.months), ZERO)
    savings = earned - total.spent
    planned = (
        None
        if plan.expected_income is None or total.envelope is None
        else plan.expected_income * len(plan.months) - total.envelope
    )
    rate = savings_rate(earned, savings)
    drifting = sorted((r for r in rows if r.drifting), key=lambda r: -(r.drift or ZERO))
    return Review(
        plan,
        elapsed,
        elapsed == 1,
        rows,
        total,
        sum((c.spent for c in matrix.uncategorised.cells), ZERO),
        earned,
        savings,
        rate,
        planned,
        drifting,
    )


@dataclass(frozen=True)
class CumulativePoint:
    day: date
    spent: Decimal | None
    """Spending from the plan's first day to this one; None after today."""
    envelope: Decimal
    """The envelope line: the envelope prorated as the pace is."""


def cumulative(
    plan: Plan, daily: Mapping[date, Decimal], envelope: Decimal, today: date
) -> list[CumulativePoint]:
    """One point per day of the plan, for the cumulative chart."""
    points = []
    running = ZERO
    day = plan.start.first_day()
    last = plan.end.next().first_day()
    while day < last:
        running += daily.get(day, ZERO)
        line = quantize(envelope * elapsed_share(plan, day))
        points.append(CumulativePoint(day, running if day <= today else None, line))
        day += timedelta(days=1)
    return points


@dataclass(frozen=True)
class ComparisonRow:
    category_id: UUID | None
    name: str
    parent_id: UUID | None
    level: int
    target_a: Decimal | None
    target_b: Decimal | None
    average_a: Decimal | None
    """Monthly average spent over the elapsed part of plan a."""
    average_b: Decimal | None
    change: Decimal | None
    """average_b - average_a."""
    change_ratio: Decimal | None


def _average(review: Review, spent: Decimal) -> Decimal | None:
    months = review.elapsed * len(review.plan.months)
    return quantize(spent / months) if months else None


def compare(a: Review, b: Review) -> list[ComparisonRow]:
    """Two plans side by side on monthly figures, so a quarter compares with a year."""
    rows_a = {r.category_id: r for r in a.rows}
    result = []
    for row_b in [*b.rows, b.total]:
        row_a = a.total if row_b is b.total else rows_a.get(row_b.category_id)
        avg_a = None if row_a is None else _average(a, row_a.spent)
        avg_b = _average(b, row_b.spent)
        diff = None if avg_a is None or avg_b is None else avg_b - avg_a
        ratio = None if avg_a is None or avg_b is None else change(avg_b, avg_a)
        result.append(
            ComparisonRow(
                row_b.category_id,
                row_b.name,
                row_b.parent_id,
                row_b.level,
                None if row_a is None else row_a.monthly_target,
                row_b.monthly_target,
                avg_a,
                avg_b,
                diff,
                ratio,
            )
        )
    return result
