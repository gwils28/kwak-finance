"""Spending KPIs (F-DSH-4, 5).

Spending and income use the budget matrix's rules, so the two pages agree: expense
categories count net of refunds, income categories net of reversals, and an uncategorised
transaction counts by its sign. Hence net = income - spent = the sum of the month's
transactions (transfers excluded upstream), plus what savings categories received: that money
is kept, not spent (invariant §8.14).

A view narrower than the household (one member's accounts, the joint ones) also counts the
transfers that cross its edge: money paid in from, or out to, an account outside the view.
A transfer between two accounts of the view still nets to zero (invariant §8.3).
"""

import calendar
from collections import defaultdict
from collections.abc import Collection, Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from kwak_core.categories import CategoryKind

ZERO = Decimal(0)


@dataclass(frozen=True)
class Flow:
    category_id: UUID | None
    amount: Decimal


@dataclass(frozen=True)
class MonthFigures:
    spent: Decimal
    income: Decimal
    paid_in: Decimal = ZERO
    """Transfers from accounts outside the view."""
    paid_out: Decimal = ZERO
    """Transfers to accounts outside the view."""
    saved: Decimal = ZERO
    """Net amount put in savings categories: part of the net, never spent."""

    @property
    def inflow(self) -> Decimal:
        """What the view received: the base of its savings rate."""
        return self.income + self.paid_in

    @property
    def net(self) -> Decimal:
        return self.inflow - self.spent - self.paid_out


def month_figures(flows: Iterable[Flow], kinds: Mapping[UUID, CategoryKind]) -> MonthFigures:
    spent = income = saved = ZERO
    for flow in flows:
        kind = kinds.get(flow.category_id) if flow.category_id else None
        if kind is CategoryKind.SAVINGS:
            saved -= flow.amount
        elif kind is CategoryKind.EXPENSE or (kind is None and flow.amount < 0):
            spent -= flow.amount
        else:
            income += flow.amount
    return MonthFigures(spent, income, saved=saved)


@dataclass(frozen=True)
class TransferLeg:
    group_id: UUID
    account_id: UUID
    amount: Decimal


def crossing(legs: Iterable[TransferLeg], scope: Collection[UUID]) -> tuple[Decimal, Decimal]:
    """(paid in, paid out) of the scope's accounts by transfers with an account outside it.

    `legs` holds every leg of the transfers involved, including the ones outside the scope.
    """
    groups: dict[UUID, list[TransferLeg]] = defaultdict(list)
    for leg in legs:
        groups[leg.group_id].append(leg)
    paid_in = paid_out = ZERO
    for group in groups.values():
        if all(leg.account_id in scope for leg in group):
            continue
        for leg in group:
            if leg.account_id not in scope:
                continue
            if leg.amount > 0:
                paid_in += leg.amount
            else:
                paid_out -= leg.amount
    return paid_in, paid_out


def savings_rate(income: Decimal, net: Decimal) -> Decimal | None:
    """Share of income left after spending; None without income."""
    return net / income if income > 0 else None


def change(current: Decimal, reference: Decimal) -> Decimal | None:
    """Relative change: 0.1 = 10 % more than the reference; None from a zero reference."""
    return (current - reference) / reference if reference else None


@dataclass(frozen=True)
class TopCategory:
    category_id: UUID
    spent: Decimal
    share: Decimal | None
    """Of the month's total spending."""


def top_categories(
    spending: Mapping[UUID, Decimal],
    parents: Mapping[UUID, UUID],
    *,
    total: Decimal,
    limit: int = 5,
) -> list[TopCategory]:
    """Top-level categories by spending, their subcategories included."""
    rolled: dict[UUID, Decimal] = {}
    for category, spent in spending.items():
        top = parents.get(category, category)
        rolled[top] = rolled.get(top, ZERO) + spent
    ranked = sorted(
        ((c, s) for c, s in rolled.items() if s > 0), key=lambda item: (-item[1], str(item[0]))
    )
    return [TopCategory(c, s, s / total if total > 0 else None) for c, s in ranked[:limit]]


def cumulative_by_day(
    year: int, month: int, daily: Mapping[date, Decimal]
) -> list[tuple[date, Decimal]]:
    """Running spending total for every day of the month."""
    running = ZERO
    series = []
    for day in range(1, calendar.monthrange(year, month)[1] + 1):
        when = date(year, month, day)
        running += daily.get(when, ZERO)
        series.append((when, running))
    return series
