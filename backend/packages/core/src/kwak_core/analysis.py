"""Where the household's analyses start (F-ADM-4).

The owner may set a first month: before it, history is incomplete (accounts added later,
statements without the everyday entries), so every analysis treats those months as empty:
averages, comparisons, reports and the detection of recurring items. Transactions, balances
and budget plans are untouched.
"""

from collections.abc import Sequence
from datetime import date

from kwak_core.budget import Month


def counted_months(months: Sequence[Month], start: Month | None) -> list[Month]:
    return [m for m in months if start is None or m >= start]


def first_counted(month: Month, start: Month | None) -> Month:
    return month if start is None else max(month, start)


def counted_day(day: date, start: Month | None) -> date:
    """The first day an analysis looks at, from `day` on."""
    return day if start is None else max(day, start.first_day())
