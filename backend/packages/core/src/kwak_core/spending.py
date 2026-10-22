"""A month's spending figures (F-DSH-4, invariant §8.14): income, spent, saved and the rest.

Lines are signed (negative is spent or put aside, positive received); the figures are positive
amounts. The income is the sum of the month's income lines (F-INC-1).
"""

from collections.abc import Collection, Iterable, Mapping
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


def month_figures(pieces: Iterable[Piece], kinds: Mapping[UUID, CategoryKind]) -> MonthFigures:
    income = spent = saved = ZERO
    for piece in pieces:
        kind = kinds[piece.category_id]
        if kind is CategoryKind.INCOME:
            income += piece.amount
        elif kind is CategoryKind.SAVINGS:
            saved -= piece.amount
        else:
            spent -= piece.amount
    return MonthFigures(income, spent, saved)


class LineKindError(ValueError):
    """The line's amount does not fit its categories."""


def check_line_kinds(amount: Decimal, kinds: Collection[CategoryKind]) -> None:
    """A line (all its parts) is income or spending, never both (F-LIN-3): an expense is an
    outflow, an income an inflow; a savings line goes either way."""
    if CategoryKind.INCOME in kinds and len(set(kinds)) > 1:
        raise LineKindError("a line is income or spending, not both")
    if amount > 0 and CategoryKind.EXPENSE in kinds:
        raise LineKindError("an expense is an outflow: a refund is an income line")
    if amount < 0 and CategoryKind.INCOME in kinds:
        raise LineKindError("an income is an inflow")


def stored_amount(typed: Decimal, kind: CategoryKind | None) -> Decimal:
    """An amount typed as spent, put aside or received, signed as stored: negative unless its
    category is an income one (F-ENT-2)."""
    return typed if kind is CategoryKind.INCOME else -typed


def cumulative_by_day(spent: Mapping[date, Decimal], month: Month) -> list[tuple[date, Decimal]]:
    """The month's spending added up day by day (F-DSH-5), every day of the month."""
    day, end, total, out = month.first_day(), month.next().first_day(), ZERO, []
    while day < end:
        total += spent.get(day, ZERO)
        out.append((day, total))
        day += timedelta(days=1)
    return out
