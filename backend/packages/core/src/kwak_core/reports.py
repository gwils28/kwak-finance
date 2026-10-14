"""Reports over a period of budget months (F-DSH-2, invariant §8.18).

A report sorts a period's transactions into three sections by the home page's rules
(kwak_core.kpis): income, spending and savings, each category counted net in its natural
direction. An uncategorised outflow is spending and an inflow income, as "to categorise".
"""

import enum
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from uuid import UUID

from kwak_core.analysis import first_counted
from kwak_core.budget import Month, month_range
from kwak_core.categories import CategoryKind
from kwak_core.kpis import Flow, MonthFigures

ZERO = Decimal(0)


class Section(enum.StrEnum):
    INCOME = "income"
    SPENDING = "spending"
    SAVINGS = "savings"


type LineKey = tuple[Section, UUID | None]


def by_category(
    flows: Iterable[Flow], kinds: Mapping[UUID, CategoryKind]
) -> dict[LineKey, Decimal]:
    """What each category received (income), spent net of refunds (spending) or put aside
    net of withdrawals (savings); None: to categorise."""
    lines: dict[LineKey, Decimal] = defaultdict(Decimal)
    for flow in flows:
        kind = kinds.get(flow.category_id) if flow.category_id else None
        if kind is CategoryKind.SAVINGS:
            lines[Section.SAVINGS, flow.category_id] -= flow.amount
        elif kind is CategoryKind.EXPENSE or (kind is None and flow.amount < 0):
            lines[Section.SPENDING, flow.category_id] -= flow.amount
        else:
            lines[Section.INCOME, flow.category_id] += flow.amount
    return dict(lines)


@dataclass(frozen=True)
class ReportRow:
    section: Section
    category_id: UUID | None
    """None: to categorise."""
    amount: Decimal
    previous: Decimal
    """Over the previous period of the same length."""
    children: tuple["ReportRow", ...] = field(default=())
    """The subcategories; the rest of `amount` was booked in the category itself."""


def _order(row: ReportRow) -> tuple[bool, Decimal, Decimal, str]:
    return (row.category_id is None, -row.amount, -row.previous, str(row.category_id))


def report_rows(
    current: Mapping[LineKey, Decimal],
    previous: Mapping[LineKey, Decimal],
    parents: Mapping[UUID, UUID],
) -> list[ReportRow]:
    """Top-level categories by section (income, spending, savings), largest first and to
    categorise last, each with its subcategories. Lines empty in both periods are left out."""
    keys = {k for k in (*current, *previous) if current.get(k) or previous.get(k)}
    own: dict[LineKey, ReportRow] = {
        k: ReportRow(k[0], k[1], current.get(k, ZERO), previous.get(k, ZERO)) for k in keys
    }
    children: dict[LineKey, list[ReportRow]] = defaultdict(list)
    tops: set[LineKey] = set()
    for (section, category), row in own.items():
        parent = parents.get(category) if category else None
        if parent is None:
            tops.add((section, category))
        else:
            children[section, parent].append(row)
            tops.add((section, parent))
    rows = []
    for key in tops:
        kids = sorted(children[key], key=_order)
        mine = own.get(key)
        rows.append(
            ReportRow(
                key[0],
                key[1],
                sum((r.amount for r in kids), mine.amount if mine else ZERO),
                sum((r.previous for r in kids), mine.previous if mine else ZERO),
                tuple(kids),
            )
        )
    sections = list(Section)
    return sorted(rows, key=lambda r: (sections.index(r.section), *_order(r)))


def total_figures(months: Iterable[MonthFigures]) -> MonthFigures:
    total = MonthFigures(ZERO, ZERO)
    for m in months:
        total = MonthFigures(
            total.spent + m.spent,
            total.income + m.income,
            total.paid_in + m.paid_in,
            total.paid_out + m.paid_out,
            total.saved + m.saved,
        )
    return total


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
    """False when the previous period reaches before the analyses start: part of it would
    count as empty, so it is not compared at all."""

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
        raise ValueError("the period is over before the analyses start")
    # Months before the analyses start count as empty (kwak_core.analysis): skip them.
    start = first_counted(start, since)
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
