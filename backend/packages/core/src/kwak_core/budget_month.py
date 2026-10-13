"""The month a transaction counts in for the budget (F-TX-7, F-CAT-5).

A transaction keeps its real booking date, which balances, imports and the transaction list
use. Every figure by month uses its *budget month* instead: the booking month, the next one
when its category shifts it (a salary paid on the 20th for the next month's spending), or the
month set by hand on the transaction, at most one month away. A transfer between two own
accounts always counts in its booking month, as both its legs must (invariant §8.15).
"""

import calendar
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

from kwak_core.budget import Month

DEFAULT_SHIFT_DAY = 15
NEVER = 0
"""A subcategory's own setting meaning "never shifted", whatever its parent says."""


@dataclass(frozen=True)
class Booked:
    booked_on: date
    manual: Month | None = None
    """The budget month set by hand, if any."""
    transfer: bool = False


def check_shift_day(day: int) -> None:
    """A category shifts from a day of the month (1-31), or never (0)."""
    if not NEVER <= day <= 31:
        raise ValueError("the shift day must be a day of the month, 1 to 31 (0: never)")


def shift_day(own: int | None, parent: int | None) -> int | None:
    """The day a category shifts from: its own setting, else its parent's; None: never."""
    day = own if own is not None else parent
    return None if day in (None, NEVER) else day


def check_manual_month(booked_on: date, month: Month) -> None:
    own = Month.of(booked_on)
    if month not in (own.previous(), own, own.next()):
        raise ValueError("a budget month set by hand is at most one month away from the date")


def budget_month(item: Booked, *, shift_from: int | None = None) -> Month:
    own = Month.of(item.booked_on)
    if item.transfer:
        return own
    if item.manual is not None:
        return item.manual
    if shift_from is not None and item.booked_on.day >= shift_from:
        return own.next()
    return own


def budget_day(booked_on: date, month: Month) -> date:
    """Where a transaction sits in a day-by-day chart of its budget month: its own date, or the
    edge of the month it was moved to (the first day of a later month, the last of an earlier
    one)."""
    own = Month.of(booked_on)
    if month == own:
        return booked_on
    if month > own:
        return month.first_day()
    return date(month.year, month.month, calendar.monthrange(month.year, month.month)[1])


def months_moved(
    items: Iterable[Booked], *, before: int | None, after: int | None
) -> tuple[int, set[Month]]:
    """What changing a category's shift day does: how many of its transactions change month,
    and every month that gains or loses one (to tell which plan reviews change)."""
    moved = 0
    months: set[Month] = set()
    for item in items:
        old = budget_month(item, shift_from=before)
        new = budget_month(item, shift_from=after)
        if old != new:
            moved += 1
            months |= {old, new}
    return moved, months
