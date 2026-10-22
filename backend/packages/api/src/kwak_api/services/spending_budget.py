"""The spending's budget since v1.0 (§4.5, F-DSH-4): targets, the month, the matrix, the year.

Every figure by month counts lines in the month of their date (F-LIN-2), a split line in each
of its parts' categories (F-LIN-4).
"""

from collections import defaultdict
from collections.abc import Sequence
from decimal import Decimal
from uuid import UUID

from kwak_core.budget import Month, month_range
from kwak_core.categories import CategoryKind
from kwak_core.income import income_of
from kwak_core.spending import MonthFigures
from sqlalchemy import func, select, union_all
from sqlalchemy.orm import Session

from kwak_api.models import (
    MonthlyIncome,
    SpendingCategory,
    SpendingLine,
    SpendingLinePart,
    SpendingTarget,
)
from kwak_api.services import spending

ZERO = Decimal(0)

Targets = dict[UUID, list[tuple[Month, Decimal | None]]]


def targets(db: Session, household_id: UUID) -> Targets:
    rows = db.execute(
        select(SpendingTarget.category_id, SpendingTarget.from_month, SpendingTarget.amount)
        .join(SpendingCategory, SpendingCategory.id == SpendingTarget.category_id)
        .where(SpendingCategory.household_id == household_id)
        .order_by(SpendingTarget.category_id, SpendingTarget.from_month)
    )
    out: Targets = defaultdict(list)
    for category, month, amount in rows:
        out[category].append((Month.of(month), amount))
    return dict(out)


def _target_row(db: Session, category: SpendingCategory, month: Month) -> SpendingTarget | None:
    return db.scalar(
        select(SpendingTarget).where(
            SpendingTarget.category_id == category.id,
            SpendingTarget.from_month == month.first_day(),
        )
    )


def set_target(
    db: Session, category: SpendingCategory, month: Month, amount: Decimal | None
) -> None:
    row = _target_row(db, category, month)
    if row is None:
        db.add(SpendingTarget(category_id=category.id, from_month=month.first_day(), amount=amount))
    else:
        row.amount = amount
    db.flush()


def remove_target(db: Session, category: SpendingCategory, month: Month) -> None:
    row = _target_row(db, category, month)
    if row is not None:
        db.delete(row)
        db.flush()


Spending = dict[tuple[UUID | None, Month], Decimal]
"""What each category spent (or saved) by month, positive."""


def spending_by_month(db: Session, household_id: UUID, first: Month, last: Month) -> Spending:
    """Lines with a category of their own, plus the parts of split lines."""
    start, end = first.first_day(), last.next().first_day()
    in_period = (
        SpendingLine.household_id == household_id,
        SpendingLine.day >= start,
        SpendingLine.day < end,
    )
    own = select(
        SpendingLine.category_id.label("category_id"),
        SpendingLine.day.label("day"),
        SpendingLine.amount.label("amount"),
    ).where(*in_period, SpendingLine.category_id.is_not(None))
    parts = (
        select(
            SpendingLinePart.category_id.label("category_id"),
            SpendingLine.day.label("day"),
            SpendingLinePart.amount.label("amount"),
        )
        .join(SpendingLine, SpendingLine.id == SpendingLinePart.line_id)
        .where(*in_period)
    )
    pieces = union_all(own, parts).subquery()
    month = func.date_trunc("month", pieces.c.day)
    rows = db.execute(
        select(pieces.c.category_id, month, -func.sum(pieces.c.amount)).group_by(
            pieces.c.category_id, month
        )
    )
    return {(category, Month.of(m)): total for category, m, total in rows}


def first_month(db: Session, household_id: UUID) -> Month | None:
    """The first month with a line or an income: months before it are not months of zero."""
    firsts = [
        db.scalar(
            select(func.min(SpendingLine.day)).where(SpendingLine.household_id == household_id)
        ),
        db.scalar(
            select(func.min(MonthlyIncome.month)).where(MonthlyIncome.household_id == household_id)
        ),
    ]
    known = [d for d in firsts if d is not None]
    return Month.of(min(known)) if known else None


def counted(months: Sequence[Month], first: Month | None) -> list[Month]:
    return [m for m in months if first is not None and m >= first]


def figures_by_month(
    db: Session, household_id: UUID, months: Sequence[Month], kinds: dict[UUID, CategoryKind]
) -> dict[Month, MonthFigures]:
    """Each month's income (carried forward), spent and saved."""
    if not months:
        return {}
    by_category = spending_by_month(db, household_id, months[0], months[-1])
    incomes = spending.incomes(db, household_id)
    totals: dict[tuple[Month, CategoryKind], Decimal] = defaultdict(Decimal)
    for (category, month), amount in by_category.items():
        if category is not None:
            totals[month, kinds[category]] += amount
    out = {}
    for m in months:
        income = income_of(m, incomes)
        out[m] = MonthFigures(
            income.amount if income else ZERO,
            totals[m, CategoryKind.EXPENSE],
            totals[m, CategoryKind.SAVINGS],
        )
    return out


def kinds(db: Session, household_id: UUID) -> dict[UUID, CategoryKind]:
    return {c.id: c.kind for c in spending.categories(db, household_id)}


def average(
    db: Session, household_id: UUID, month: Month, kinds: dict[UUID, CategoryKind]
) -> MonthFigures | None:
    """The average of the 12 months before `month`, from the first month with data."""
    before = counted(
        month_range(Month(month.year - 1, month.month), month.previous()),
        first_month(db, household_id),
    )
    if not before:
        return None
    total = sum(figures_by_month(db, household_id, before, kinds).values(), MonthFigures.zero())
    n = Decimal(len(before))
    return MonthFigures(total.income / n, total.spent / n, total.saved / n)
