"""The period of a spending report (F-DSH-2): the months it covers and the ones it compares
them with, and how a change is measured."""

from dataclasses import dataclass
from decimal import Decimal

from kwak_core.budget import Month, month_range


def previous_period(start: Month, end: Month) -> tuple[Month, Month]:
    """The period of the same length that ends the month before `start`."""
    length = len(month_range(start, end))
    first = start
    for _ in range(length):
        first = first.previous()
    return first, start.previous()


@dataclass(frozen=True)
class ReportPeriod:
    start: Month
    end: Month
    """The last month covered: never after the current one."""
    previous_start: Month
    previous_end: Month
    to_date: bool
    """The period runs past the current month: it is shown so far."""
    compared: bool = True
    """False when the previous period reaches before the first month with a line: part of
    it would count as empty, so it is not compared at all."""

    @property
    def months(self) -> int:
        return len(month_range(self.start, self.end))


def report_period(
    start: Month, end: Month, *, current: Month, since: Month | None = None
) -> ReportPeriod:
    """The months a report covers and the ones it compares them with.

    A running period stops at the current month and is compared with the same months of the
    period before (this year so far against the same months last year), so the averages and
    changes compare like with like.
    """
    if end < start:
        raise ValueError("the period ends before it starts")
    if since is not None and end < since:
        raise ValueError("the period is over before the first month with a line")
    # Months before the first line are not months of zero: skip them.
    start = start if since is None else max(start, since)
    if current < start:
        raise ValueError("the period has not started yet")
    covered_end = min(end, current)
    previous_start, _ = previous_period(start, end)
    previous_end = previous_start
    for _ in range(len(month_range(start, covered_end)) - 1):
        previous_end = previous_end.next()
    compared = since is None or previous_start >= since
    return ReportPeriod(start, covered_end, previous_start, previous_end, end > current, compared)


def relative_change(current: Decimal, reference: Decimal) -> Decimal | None:
    """Change against the reference's size: from -500 to +200 is +140 %, an improvement.
    None from a zero reference."""
    return (current - reference) / abs(reference) if reference else None
