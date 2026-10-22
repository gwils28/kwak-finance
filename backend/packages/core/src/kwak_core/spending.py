"""A month's spending figures (F-DSH-4, invariant §8.14): income, spent, saved and the rest.

Lines are signed (negative is spent or put aside); the figures are positive amounts.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from kwak_core.budget import Month
from kwak_core.categories import CategoryKind

ZERO = Decimal(0)


@dataclass(frozen=True)
class Piece:
    """A line, or one part of a split line."""

    category_id: UUID
    amount: Decimal


@dataclass(frozen=True)
class MonthFigures:
    income: Decimal
    spent: Decimal
    saved: Decimal
    """Net of what was taken back from savings."""

    @classmethod
    def zero(cls) -> "MonthFigures":
        return cls(ZERO, ZERO, ZERO)

    @property
    def rest(self) -> Decimal:
        return self.income - self.spent - self.saved

    @property
    def savings_rate(self) -> Decimal | None:
        """(income - spent) / income: what was not spent, saved or left over."""
        return (self.income - self.spent) / self.income if self.income > 0 else None

    def __add__(self, other: "MonthFigures") -> "MonthFigures":
        return MonthFigures(
            self.income + other.income, self.spent + other.spent, self.saved + other.saved
        )


def month_figures(
    income: Decimal, pieces: Iterable[Piece], kinds: Mapping[UUID, CategoryKind]
) -> MonthFigures:
    spent = saved = ZERO
    for piece in pieces:
        if kinds[piece.category_id] is CategoryKind.SAVINGS:
            saved -= piece.amount
        else:
            spent -= piece.amount
    return MonthFigures(income, spent, saved)


def cumulative_by_day(spent: Mapping[date, Decimal], month: Month) -> list[tuple[date, Decimal]]:
    """The month's spending added up day by day (F-DSH-5), every day of the month."""
    day, end, total, out = month.first_day(), month.next().first_day(), ZERO, []
    while day < end:
        total += spent.get(day, ZERO)
        out.append((day, total))
        day += timedelta(days=1)
    return out
