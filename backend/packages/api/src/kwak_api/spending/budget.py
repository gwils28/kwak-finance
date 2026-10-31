"""The spending's budget since v1.0 (§4.5, F-DSH-4): targets, the month, the matrix, the year.

Spent and saved are positive amounts here; ratios have four decimals (0.1 = 10 %).
"""

from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, status
from kwak_core.budget import DEFAULT_BAND, BudgetStatus, Cell, Month, Row, build_matrix, month_range
from kwak_core.categories import CategoryKind
from kwak_core.fixed import FixedStatus, projected_rest
from kwak_core.money import quantize, require_cents
from kwak_core.progress import ProgressStatus, SavingsStatus, month_progress, savings_progress
from kwak_core.spending import MonthFigures, cumulative_by_day, top_categories
from kwak_core.year import YearLine, months_to_date, year_lines
from pydantic import AfterValidator, BaseModel, Field

from kwak_api.auth.routes import CurrentSession, Db, Now
from kwak_api.models import SpendingCategory
from kwak_api.services import spending
from kwak_api.services import spending_budget as service
from kwak_api.spending.routes import MonthText, _category, _month, _unprocessable

router = APIRouter(prefix="/api/spending", tags=["spending"])

RATIO = Decimal("0.0001")
MAX_MONTHS = 120
DEFAULT_MONTHS = 12
YEARS = range(1900, 2201)
ZERO = Decimal(0)


def _change(current: Decimal, reference: Decimal) -> Decimal | None:
    """Against the size of the reference: from -500 to +200 is +140 %; None from zero."""
    return _ratio((current - reference) / abs(reference)) if reference else None


def _ratio(value: Decimal | None) -> Decimal | None:
    return None if value is None else value.quantize(RATIO, rounding=ROUND_HALF_UP)


def _cents(value: Decimal | None) -> Decimal | None:
    return None if value is None else quantize(value)


# Targets (F-BUD-1, 9)


class SpendingTargetOut(BaseModel):
    category_id: UUID
    from_month: str
    amount: Decimal | None
    """None: no target from this month on."""


def _cents_or_none(value: Decimal | None) -> Decimal | None:
    return None if value is None else require_cents(value)


class SpendingTargetIn(BaseModel):
    amount: Annotated[
        Decimal | None, Field(ge=0, lt=Decimal("1e12")), AfterValidator(_cents_or_none)
    ]
    """None: no target from this month on."""


@router.get("/targets")
def list_targets(user_session: CurrentSession, db: Db) -> list[SpendingTargetOut]:
    """Each category's targets (objectives for savings), by the month they start."""
    return [
        SpendingTargetOut(category_id=category, from_month=str(month), amount=amount)
        for category, history in service.targets(db, user_session.user.household_id).items()
        for month, amount in history
    ]


@router.put("/targets/{category_id}/{month}")
def set_target(
    category_id: UUID, month: str, body: SpendingTargetIn, user_session: CurrentSession, db: Db
) -> SpendingTargetOut:
    """From `month` on, until the next change (F-BUD-1); an income category has none."""
    category = _category(db, user_session, category_id)
    if category.kind is CategoryKind.INCOME:
        raise _unprocessable("an income category has no target")
    wanted = _month(month)
    service.set_target(db, category, wanted, body.amount)
    return SpendingTargetOut(category_id=category.id, from_month=str(wanted), amount=body.amount)


@router.delete("/targets/{category_id}/{month}", status_code=status.HTTP_204_NO_CONTENT)
def remove_target(category_id: UUID, month: str, user_session: CurrentSession, db: Db) -> None:
    """The month follows the earlier target again."""
    service.remove_target(db, _category(db, user_session, category_id), _month(month))


# The month (F-DSH-4, F-BUD-2, F-FIX-4)


class SpendingFiguresOut(BaseModel):
    income: Decimal
    spent: Decimal
    saved: Decimal
    rest: Decimal
    """income - spent - saved."""
    savings_rate: Decimal | None
    """(income - spent) / income; None without income."""

    @classmethod
    def of(cls, f: MonthFigures) -> "SpendingFiguresOut":
        return cls(
            income=quantize(f.income),
            spent=quantize(f.spent),
            saved=quantize(f.saved),
            rest=quantize(f.rest),
            savings_rate=_ratio(f.savings_rate),
        )


class SpendingChangesOut(BaseModel):
    """Relative changes, None from a zero reference."""

    income: Decimal | None
    spent: Decimal | None
    saved: Decimal | None
    rest: Decimal | None

    @classmethod
    def between(cls, current: MonthFigures, reference: MonthFigures) -> "SpendingChangesOut":
        return cls(
            income=_change(current.income, reference.income),
            spent=_change(current.spent, reference.spent),
            saved=_change(current.saved, reference.saved),
            rest=_change(current.rest, reference.rest),
        )


class SpendingMonthChangesOut(BaseModel):
    vs_previous: SpendingChangesOut
    vs_average: SpendingChangesOut | None


class SpendingTopOut(BaseModel):
    category_id: UUID
    spent: Decimal
    share: Decimal | None
    """Of the month's spending."""


class SpendingProgressLineOut(BaseModel):
    category_id: UUID
    name: str
    spent: Decimal
    target: Decimal
    remaining: Decimal
    """Negative once over."""
    share: Decimal | None
    status: ProgressStatus
    pace: Decimal | None
    """The share of the month elapsed; None for a one-off category or another month."""


class SpendingSavingsLineOut(BaseModel):
    category_id: UUID
    name: str
    saved: Decimal
    objective: Decimal
    remaining: Decimal
    """Negative once beyond the objective."""
    share: Decimal | None
    status: SavingsStatus


class SpendingProgressOut(BaseModel):
    warn_at: Decimal
    lines: list[SpendingProgressLineOut]
    savings: list[SpendingSavingsLineOut]
    """The savings categories with an objective this month (F-BUD-9), least advanced first."""


class SpendingDayOut(BaseModel):
    day: date
    spent: Decimal
    """Spent from the first of the month to this day included."""


class SpendingMonthOut(BaseModel):
    month: str
    figures: SpendingFiguresOut
    previous: SpendingFiguresOut
    average: SpendingFiguresOut | None
    """Of the 12 months before, from the first month with a line."""
    changes: SpendingMonthChangesOut
    top: list[SpendingTopOut]
    projected_rest: Decimal
    """The rest once the fixed expenses still to confirm are paid (F-FIX-4)."""
    to_confirm: int
    progress: SpendingProgressOut
    cumulative: list[SpendingDayOut]
    """The spending added up day by day, every day of the month (F-DSH-5)."""
    target_total: Decimal | None
    """The month's expense targets added up; None without any."""


Section = list[tuple[UUID, None, str]]


def _section(categories: list[SpendingCategory], kind: CategoryKind) -> Section:
    return [(c.id, None, c.name) for c in categories if c.kind is kind]


def _sections(categories: list[SpendingCategory]) -> tuple[Section, Section]:
    return _section(categories, CategoryKind.EXPENSE), _section(categories, CategoryKind.SAVINGS)


@router.get("/month")
def month_summary(
    user_session: CurrentSession,
    db: Db,
    now: Now,
    month: Annotated[MonthText, Query(description="YYYY-MM")],
) -> SpendingMonthOut:
    household_id = user_session.user.household_id
    wanted = _month(month)
    categories = spending.categories(db, household_id)
    kinds = {c.id: c.kind for c in categories}
    figures = service.figures_by_month(db, household_id, [wanted.previous(), wanted], kinds)
    current, previous = figures[wanted], figures[wanted.previous()]
    average = service.average(db, household_id, wanted, kinds)

    by_category = service.spending_by_month(db, household_id, wanted, wanted)
    expenses, savings = _sections(categories)
    spent = {c: by_category.get((c, wanted), ZERO) for c, _, _ in expenses}
    top = top_categories(spent, total=current.spent)

    matrix = build_matrix(
        expenses, service.targets(db, household_id), by_category, [wanted], savings=savings
    )
    household = user_session.user.household
    progress = month_progress(
        matrix,
        today=now.date(),
        settings={c.id: c.one_off for c in categories},
        warn_at=household.warn_at,
    )

    occurrences = [o for _, o in spending.occurrences(db, household_id, wanted)]
    return SpendingMonthOut(
        month=str(wanted),
        figures=SpendingFiguresOut.of(current),
        previous=SpendingFiguresOut.of(previous),
        average=SpendingFiguresOut.of(average) if average else None,
        changes=SpendingMonthChangesOut(
            vs_previous=SpendingChangesOut.between(current, previous),
            vs_average=SpendingChangesOut.between(current, average) if average else None,
        ),
        top=[
            SpendingTopOut(category_id=t.category_id, spent=t.spent, share=_ratio(t.share))
            for t in top
        ],
        projected_rest=quantize(projected_rest(current.rest, occurrences)),
        to_confirm=sum(o.status is FixedStatus.TO_CONFIRM for o in occurrences),
        cumulative=[
            SpendingDayOut(day=day, spent=quantize(total))
            for day, total in cumulative_by_day(
                service.expense_by_day(db, household_id, wanted, [c for c, _, _ in expenses]),
                wanted,
            )
        ],
        target_total=matrix.total.cells[0].target,
        progress=SpendingProgressOut(
            warn_at=household.warn_at,
            lines=[
                SpendingProgressLineOut(
                    category_id=p.category_id,
                    name=p.name,
                    spent=p.spent,
                    target=p.target,
                    remaining=p.remaining,
                    share=_ratio(p.share),
                    status=p.status,
                    pace=_ratio(p.pace),
                )
                for p in progress
            ],
            savings=[
                SpendingSavingsLineOut(
                    category_id=s.category_id,
                    name=s.name,
                    saved=s.saved,
                    objective=s.objective,
                    remaining=s.remaining,
                    share=_ratio(s.share),
                    status=s.status,
                )
                for s in savings_progress(matrix)
            ],
        ),
    )


# The matrix (F-BUD-6)


class SpendingCellOut(BaseModel):
    month: str
    spent: Decimal
    target: Decimal | None
    gap: Decimal | None
    gap_ratio: Decimal | None
    status: BudgetStatus

    @classmethod
    def of(cls, c: Cell) -> "SpendingCellOut":
        return cls(
            month=str(c.month),
            spent=quantize(c.spent),
            target=c.target,
            gap=_cents(c.gap),
            gap_ratio=_ratio(c.gap_ratio),
            status=c.status,
        )


class SpendingMatrixRowOut(BaseModel):
    category_id: UUID | None
    name: str
    target: Decimal | None
    """The target in force in the last month shown."""
    cells: list[SpendingCellOut]

    @classmethod
    def of(cls, row: Row) -> "SpendingMatrixRowOut":
        return cls(
            category_id=row.category_id,
            name=row.name,
            target=row.target,
            cells=[SpendingCellOut.of(c) for c in row.cells],
        )


class SpendingMatrixOut(BaseModel):
    months: list[str]
    rows: list[SpendingMatrixRowOut]
    total: SpendingMatrixRowOut
    savings: list[SpendingMatrixRowOut]
    savings_total: SpendingMatrixRowOut
    income: list[SpendingMatrixRowOut]
    """What each income category received; they have no target."""
    income_total: SpendingMatrixRowOut
    figures: list[SpendingFiguresOut]
    """Each month's income, spent, saved and rest."""


@router.get("/matrix")
def spending_matrix(
    user_session: CurrentSession,
    db: Db,
    now: Now,
    first: Annotated[MonthText | None, Query(description="YYYY-MM")] = None,
    last: Annotated[MonthText | None, Query(description="YYYY-MM")] = None,
) -> SpendingMatrixOut:
    """By default the last 12 months, this one included."""
    household_id = user_session.user.household_id
    end = _month(last) if last else Month.of(now.date())
    start = _month(first) if first else Month(end.year - 1, end.month).next()
    months = month_range(start, end)
    if not months or len(months) > MAX_MONTHS:
        raise _unprocessable(f"the period runs forward, {MAX_MONTHS} months at most")
    categories = spending.categories(db, household_id)
    expenses, savings = _sections(categories)
    by_category = service.spending_by_month(db, household_id, start, end)
    matrix = build_matrix(
        expenses,
        service.targets(db, household_id),
        by_category,
        months,
        DEFAULT_BAND,
        savings=savings,
    )
    income = build_matrix(_section(categories, CategoryKind.INCOME), {}, by_category, months)
    figures = service.figures_by_month(db, household_id, months, {c.id: c.kind for c in categories})
    return SpendingMatrixOut(
        months=[str(m) for m in months],
        rows=[SpendingMatrixRowOut.of(r) for r in matrix.rows],
        total=SpendingMatrixRowOut.of(matrix.total),
        savings=[SpendingMatrixRowOut.of(r) for r in matrix.savings],
        savings_total=SpendingMatrixRowOut.of(matrix.savings_total),
        income=[SpendingMatrixRowOut.of(r) for r in income.rows],
        income_total=SpendingMatrixRowOut.of(income.total),
        figures=[SpendingFiguresOut.of(figures[m]) for m in months],
    )


# The year (F-BUD-10)


class SpendingYearLineOut(BaseModel):
    category_id: UUID
    name: str
    target_to_date: Decimal | None
    """January to this month, the current month in full."""
    target_full: Decimal | None
    spent_to_date: Decimal
    """Spent, saved or received, by the line's section."""
    gap: Decimal | None
    gap_ratio: Decimal | None
    status: BudgetStatus
    above: int
    """Completed months above their target (ahead, for an objective)."""
    on: int
    below: int


class SpendingYearOut(BaseModel):
    year: int
    months: list[str]
    """The months counted to date."""
    expenses: list[SpendingYearLineOut]
    savings: list[SpendingYearLineOut]
    income: list[SpendingYearLineOut]
    """Without targets."""
    totals: SpendingFiguresOut


def _year_out(line: YearLine, names: dict[UUID, str]) -> SpendingYearLineOut:
    return SpendingYearLineOut(
        category_id=line.category_id,
        name=names[line.category_id],
        target_to_date=line.target_to_date,
        target_full=line.target_full,
        spent_to_date=quantize(line.spent_to_date),
        gap=_cents(line.gap),
        gap_ratio=_ratio(line.gap_ratio),
        status=line.status,
        above=line.above,
        on=line.on,
        below=line.below,
    )


@router.get("/year")
def spending_year(
    user_session: CurrentSession,
    db: Db,
    now: Now,
    year: Annotated[int | None, Query(ge=YEARS.start, lt=YEARS.stop)] = None,
) -> SpendingYearOut:
    """The current year by default; a past one whole."""
    household_id = user_session.user.household_id
    today: date = now.date()
    wanted = year if year is not None else today.year
    categories = spending.categories(db, household_id)
    names = {c.id: c.name for c in categories}
    kinds = {c.id: c.kind for c in categories}
    targets = service.targets(db, household_id)
    by_category = service.spending_by_month(db, household_id, Month(wanted, 1), Month(wanted, 12))
    to_date = months_to_date(wanted, today)

    def lines(kind: CategoryKind) -> list[SpendingYearLineOut]:
        ids = [c.id for c in categories if c.kind is kind]
        return [
            _year_out(line, names)
            for line in year_lines(
                wanted,
                today,
                ids,
                targets,
                by_category,
                minimum=kind is CategoryKind.SAVINGS,
            )
        ]

    totals = sum(
        service.figures_by_month(db, household_id, to_date, kinds).values(), MonthFigures.zero()
    )
    return SpendingYearOut(
        year=wanted,
        months=[str(m) for m in to_date],
        expenses=lines(CategoryKind.EXPENSE),
        savings=lines(CategoryKind.SAVINGS),
        income=lines(CategoryKind.INCOME),
        totals=SpendingFiguresOut.of(totals),
    )
