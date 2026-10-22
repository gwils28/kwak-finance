"""The spending's budget since v1.0 (§4.5, F-DSH-4): targets, the month, the matrix, the year.

Every figure by month counts lines in the month of their date (F-LIN-2), a split line in each
of its parts' categories (F-LIN-4).
"""

from collections import defaultdict
from collections.abc import Collection, Sequence
from datetime import date
from decimal import Decimal
from uuid import UUID

from kwak_core.budget import Month, month_range
from kwak_core.categories import CategoryKind
from kwak_core.spending import MonthFigures
from sqlalchemy import case, func, select, union_all
from sqlalchemy.orm import Session

from kwak_api.models import (
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
"""What each category spent, saved or received by month, positive."""


def spending_by_month(db: Session, household_id: UUID, first: Month, last: Month) -> Spending:
    """Lines with a category of their own, plus the parts of split lines; an income category
    counts what it received, the others what they spent or put aside."""
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
    sign = case((SpendingCategory.kind == CategoryKind.INCOME, 1), else_=-1)
    rows = db.execute(
        select(pieces.c.category_id, month, sign * func.sum(pieces.c.amount))
        .join(SpendingCategory, SpendingCategory.id == pieces.c.category_id)
        .group_by(pieces.c.category_id, month, SpendingCategory.kind)
    )
    return {(category, Month.of(m)): total for category, m, total in rows}


def expense_by_day(
    db: Session, household_id: UUID, month: Month, expenses: Collection[UUID]
) -> dict[date, Decimal]:
    """What the expense categories spent each day of the month, split parts included."""
    start, end = month.first_day(), month.next().first_day()
    in_month = (
        SpendingLine.household_id == household_id,
        SpendingLine.day >= start,
        SpendingLine.day < end,
    )
    own = select(SpendingLine.day.label("day"), SpendingLine.amount.label("amount")).where(
        *in_month, SpendingLine.category_id.in_(expenses)
    )
    parts = (
        select(SpendingLine.day.label("day"), SpendingLinePart.amount.label("amount"))
        .join(SpendingLine, SpendingLine.id == SpendingLinePart.line_id)
        .where(*in_month, SpendingLinePart.category_id.in_(expenses))
    )
    pieces = union_all(own, parts).subquery()
    rows = db.execute(select(pieces.c.day, -func.sum(pieces.c.amount)).group_by(pieces.c.day))
    return {day: total for day, total in rows}


def first_month(db: Session, household_id: UUID) -> Month | None:
    """The first month with a line, income included: months before it are not months of zero."""
    first = db.scalar(
        select(func.min(SpendingLine.day)).where(SpendingLine.household_id == household_id)
    )
    return Month.of(first) if first is not None else None


def counted(months: Sequence[Month], first: Month | None) -> list[Month]:
    return [m for m in months if first is not None and m >= first]


def figures_by_month(
    db: Session, household_id: UUID, months: Sequence[Month], kinds: dict[UUID, CategoryKind]
) -> dict[Month, MonthFigures]:
    """Each month's income, spent and saved."""
    if not months:
        return {}
    by_category = spending_by_month(db, household_id, months[0], months[-1])
    totals: dict[tuple[Month, CategoryKind], Decimal] = defaultdict(Decimal)
    for (category, month), amount in by_category.items():
        if category is not None:
            totals[month, kinds[category]] += amount
    out = {}
    for m in months:
        out[m] = MonthFigures(
            totals[m, CategoryKind.INCOME],
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
