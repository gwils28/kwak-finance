"""Reports on the spending lines since v1.0 (F-DSH-2, invariant §8.13).

A report sorts a period's lines by category in three sections, income, spending and savings,
and draws where the income of each category went: spending by category, savings, and the
unallocated rest. A shortfall comes in as a deficit, money taken back from savings as such, so
both sides of the flows always add up to the same total.
"""

import enum
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from kwak_core.budget import Month, target_for

ZERO = Decimal(0)


class FlowKind(enum.StrEnum):
    INCOME = "income"
    SPENDING = "spending"
    SAVED = "saved"
    FROM_SAVINGS = "from_savings"
    """Taken back from savings."""
    UNALLOCATED = "unallocated"
    DEFICIT = "deficit"


class Side(enum.StrEnum):
    IN = "in"
    OUT = "out"


@dataclass(frozen=True)
class Flow:
    kind: FlowKind
    side: Side
    amount: Decimal
    """Always positive: the side says which way it goes."""
    category_id: UUID | None = None
    over: bool = False
    """Spending over its category's targets for the period."""


def report_flows(
    *,
    income: Mapping[UUID, Decimal],
    spent: Mapping[UUID, Decimal],
    saved: Decimal,
    over: Collection[UUID],
) -> list[Flow]:
    """`income` by income category, `spent` by expense category; `saved` net of withdrawals,
    negative when savings were drawn on. Zero amounts are left out."""
    flows = [
        Flow(FlowKind.INCOME, Side.IN, amount, category)
        for category, amount in income.items()
        if amount
    ]
    flows += [
        Flow(FlowKind.SPENDING, Side.OUT, amount, category, over=category in over)
        for category, amount in spent.items()
        if amount
    ]
    if saved > 0:
        flows.append(Flow(FlowKind.SAVED, Side.OUT, saved))
    elif saved < 0:
        flows.append(Flow(FlowKind.FROM_SAVINGS, Side.IN, -saved))
    left = sum((f.amount for f in flows if f.side is Side.IN), ZERO)
    right = sum((f.amount for f in flows if f.side is Side.OUT), ZERO)
    if left > right:
        flows.append(Flow(FlowKind.UNALLOCATED, Side.OUT, left - right))
    elif right > left:
        flows.append(Flow(FlowKind.DEFICIT, Side.IN, right - left))
    return flows


def period_lines(
    current: Mapping[UUID, Decimal], previous: Mapping[UUID, Decimal]
) -> list[tuple[UUID, Decimal, Decimal]]:
    """Each category's amount over the period and the one before, largest first; a category
    empty in both is left out."""
    keys = {k for k in (*current, *previous) if current.get(k) or previous.get(k)}
    lines = [(k, current.get(k, ZERO), previous.get(k, ZERO)) for k in keys]
    return sorted(lines, key=lambda line: (-line[1], -line[2], str(line[0])))


def overspent(
    spending: Mapping[tuple[UUID, Month], Decimal],
    targets: Mapping[UUID, Sequence[tuple[Month, Decimal | None]]],
    months: Sequence[Month],
) -> set[UUID]:
    """The categories that spent more than their targets over the months that had one."""
    over = set()
    for category, history in targets.items():
        judged = [(m, t) for m in months if (t := target_for(history, m)) is not None]
        if not judged:
            continue
        spent = sum((spending.get((category, m), ZERO) for m, _ in judged), ZERO)
        if spent > sum((t for _, t in judged), ZERO):
            over.add(category)
    return over
