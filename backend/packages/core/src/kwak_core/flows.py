"""Where the money of a period came from and went (F-DSH-2), for the plan review's Sankey.

Income and paid-in transfers come in; spending, paid-out transfers and savings go out; what
is left is unallocated, and a shortfall comes in as a deficit. Both sides always balance
(invariant §8.13). Amounts follow the KPI rules (kwak_core.kpis): categories count net, a
category netting the wrong way (a refund larger than its spending) crosses to the other side.
"""

import enum
from collections import defaultdict
from collections.abc import Collection, Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from kwak_core.kpis import TransferLeg

ZERO = Decimal(0)


class FlowKind(enum.StrEnum):
    INCOME = "income"
    SPENDING = "spending"
    UNCATEGORISED = "uncategorised"
    PAID_IN = "paid_in"
    PAID_OUT = "paid_out"
    SAVED = "saved"
    """Moved from spending accounts to savings ones, or put in savings categories."""
    FROM_SAVINGS = "from_savings"
    """Taken back from savings accounts."""
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


def _signed(kind: FlowKind, natural: Side, amount: Decimal, category: UUID | None = None) -> Flow:
    other = Side.OUT if natural is Side.IN else Side.IN
    return Flow(kind, natural if amount > 0 else other, abs(amount), category)


def money_flows(
    *,
    income: Mapping[UUID, Decimal],
    spending: Mapping[UUID, Decimal],
    uncategorised_in: Decimal,
    uncategorised_out: Decimal,
    paid_in: Decimal,
    paid_out: Decimal,
    saved: Decimal,
) -> list[Flow]:
    """`income` and `spending` are net per category; `saved` is negative when savings were
    drawn on. Zero amounts are left out."""
    flows = [_signed(FlowKind.INCOME, Side.IN, a, c) for c, a in income.items() if a]
    flows += [_signed(FlowKind.SPENDING, Side.OUT, a, c) for c, a in spending.items() if a]
    for kind, side, amount in (
        (FlowKind.UNCATEGORISED, Side.IN, uncategorised_in),
        (FlowKind.UNCATEGORISED, Side.OUT, uncategorised_out),
        (FlowKind.PAID_IN, Side.IN, paid_in),
        (FlowKind.PAID_OUT, Side.OUT, paid_out),
    ):
        if amount:
            flows.append(Flow(kind, side, amount))
    if saved:
        kind = FlowKind.SAVED if saved > 0 else FlowKind.FROM_SAVINGS
        flows.append(_signed(kind, Side.OUT, saved))
    left = sum((f.amount for f in flows if f.side is Side.IN), ZERO)
    right = sum((f.amount for f in flows if f.side is Side.OUT), ZERO)
    if left > right:
        flows.append(Flow(FlowKind.UNALLOCATED, Side.OUT, left - right))
    elif right > left:
        flows.append(Flow(FlowKind.DEFICIT, Side.IN, right - left))
    return flows


def saved(
    legs: Iterable[TransferLeg], scope: Collection[UUID], *, savings: Collection[UUID]
) -> Decimal:
    """Net amount moved, within the scope, from its other accounts into its savings ones.

    Transfers with an account outside the scope are paid in or out instead (kpis.crossing).
    """
    groups: dict[UUID, list[TransferLeg]] = defaultdict(list)
    for leg in legs:
        groups[leg.group_id].append(leg)
    total = ZERO
    for group in groups.values():
        if not all(leg.account_id in scope for leg in group):
            continue
        # Savings to savings nets to zero here: the money was already saved.
        total += sum((leg.amount for leg in group if leg.account_id in savings), ZERO)
    return total
