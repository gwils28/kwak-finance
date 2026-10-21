"""Fixed expenses (F-FIX, invariant §8.16): occurrences to confirm in each month's grid.

Nothing is created by itself: an occurrence is confirmed by a line created from it, or by a
line typed by hand with the same label and category.
"""

import calendar
import enum
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from kwak_core.budget import Month
from kwak_core.labels import normalise
from kwak_core.money import quantize


class FixedFrequency(enum.StrEnum):
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"


STEP = {FixedFrequency.MONTHLY: 1, FixedFrequency.QUARTERLY: 3, FixedFrequency.YEARLY: 12}


@dataclass(frozen=True)
class FixedExpense:
    id: UUID
    label: str
    category_id: UUID
    amount: Decimal
    """Signed as a line: negative is spent or put aside."""
    frequency: FixedFrequency
    day: int
    first: Month
    last: Month | None = None
    paused: bool = False


@dataclass(frozen=True)
class LineRef:
    """A line of the month, as far as fixed expenses care."""

    id: UUID
    label: str
    category_id: UUID | None
    """None for a split line, which no hand matching takes."""
    day: date
    from_item: UUID | None = None
    """The fixed expense it was created from, when confirmed from the grid."""


class FixedStatus(enum.StrEnum):
    TO_CONFIRM = "to_confirm"
    CONFIRMED = "confirmed"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class Occurrence:
    item_id: UUID
    due: date
    amount: Decimal
    status: FixedStatus
    line_id: UUID | None = None


def _months_between(a: Month, b: Month) -> int:
    return (b.year - a.year) * 12 + b.month - a.month


def is_due(item: FixedExpense, month: Month) -> bool:
    if item.paused or month < item.first or (item.last is not None and month > item.last):
        return False
    return _months_between(item.first, month) % STEP[item.frequency] == 0


def due_date(item: FixedExpense, month: Month) -> date:
    last_day = calendar.monthrange(month.year, month.month)[1]
    return date(month.year, month.month, min(item.day, last_day))


def monthly_equivalent(amount: Decimal, frequency: FixedFrequency) -> Decimal:
    return quantize(amount / STEP[frequency])


def occurrences(
    items: Sequence[FixedExpense],
    month: Month,
    lines: Sequence[LineRef],
    skipped: Collection[UUID],
) -> list[Occurrence]:
    """The month's occurrences, by due date.

    A line created from an item confirms it first; then a skipped occurrence stays skipped;
    then each one left takes the hand-typed line of the same label and category closest to
    its date (then the earliest), that no other occurrence took.
    """
    due = sorted(((due_date(i, month), i) for i in items if is_due(i, month)), key=lambda d: d[0])
    found: dict[UUID, Occurrence] = {}
    taken: set[UUID] = set()
    for day, item in due:
        line = next((ln for ln in lines if ln.from_item == item.id and ln.id not in taken), None)
        if line is not None:
            taken.add(line.id)
            found[item.id] = Occurrence(item.id, day, item.amount, FixedStatus.CONFIRMED, line.id)
        elif item.id in skipped:
            found[item.id] = Occurrence(item.id, day, item.amount, FixedStatus.SKIPPED)
    for day, item in due:
        if item.id in found:
            continue
        label = normalise(item.label)
        candidates = [
            ln
            for ln in lines
            if ln.from_item is None
            and ln.id not in taken
            and ln.category_id == item.category_id
            and normalise(ln.label) == label
        ]
        if candidates:
            line = min(candidates, key=lambda ln: (abs(ln.day - day), ln.day))
            taken.add(line.id)
            found[item.id] = Occurrence(item.id, day, item.amount, FixedStatus.CONFIRMED, line.id)
        else:
            found[item.id] = Occurrence(item.id, day, item.amount, FixedStatus.TO_CONFIRM)
    return [found[item.id] for _, item in due]


def projected_rest(rest: Decimal, occurrences: Sequence[Occurrence]) -> Decimal:
    """The month's rest once the occurrences still to confirm are paid (F-FIX-4)."""
    still = [o.amount for o in occurrences if o.status is FixedStatus.TO_CONFIRM]
    return rest + sum(still, Decimal(0))
