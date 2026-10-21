"""The year (F-BUD-10, invariant §8.9): targets to date and for the full year, per category.

The current month counts its full target, so a running month leans under. The months above,
on and below their target count the completed months only.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from kwak_core.budget import (
    DEFAULT_BAND,
    BudgetStatus,
    Month,
    budget_status,
    month_range,
    target_for,
)

ZERO = Decimal(0)
_ABOVE = {BudgetStatus.OVER, BudgetStatus.AHEAD}
_BELOW = {BudgetStatus.UNDER, BudgetStatus.BEHIND}


@dataclass(frozen=True)
class YearLine:
    category_id: UUID
    target_to_date: Decimal | None
    target_full: Decimal | None
    spent_to_date: Decimal
    gap: Decimal | None
    gap_ratio: Decimal | None
    status: BudgetStatus
    above: int
    on: int
    below: int


def months_to_date(year: int, today: date) -> list[Month]:
    """January to this month for the current year, the whole of a past one, none ahead."""
    if year > today.year:
        return []
    last = Month.of(today) if year == today.year else Month(year, 12)
    return month_range(Month(year, 1), last)


def _sum(values: list[Decimal | None]) -> Decimal | None:
    known = [v for v in values if v is not None]
    return sum(known, ZERO) if known else None


def year_lines(
    year: int,
    today: date,
    category_ids: Sequence[UUID],
    targets: Mapping[UUID, Sequence[tuple[Month, Decimal | None]]],
    spending: Mapping[tuple[UUID, Month], Decimal],
    band: Decimal = DEFAULT_BAND,
    *,
    minimum: bool = False,
) -> list[YearLine]:
    """One line per category; `spending` is positive (saved, for savings `minimum` objectives)."""
    to_date = months_to_date(year, today)
    completed = [m for m in to_date if m < Month.of(today)]
    lines = []
    for category in category_ids:
        history = targets.get(category, ())
        target_to_date = _sum([target_for(history, m) for m in to_date])
        target_full = _sum([target_for(history, Month(year, k)) for k in range(1, 13)])
        spent = sum((spending.get((category, m), ZERO) for m in to_date), ZERO)
        gap = spent - target_to_date if target_to_date is not None else None
        ratio = gap / target_to_date if gap is not None and target_to_date else None
        statuses = [
            budget_status(
                spending.get((category, m), ZERO), target_for(history, m), band, minimum=minimum
            )
            for m in completed
        ]
        lines.append(
            YearLine(
                category,
                target_to_date,
                target_full,
                spent,
                gap,
                ratio,
                budget_status(spent, target_to_date, band, minimum=minimum),
                sum(s in _ABOVE for s in statuses),
                sum(s is BudgetStatus.ON for s in statuses),
                sum(s in _BELOW for s in statuses),
            )
        )
    return lines
