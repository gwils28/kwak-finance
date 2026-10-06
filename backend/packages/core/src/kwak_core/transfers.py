"""Transfers between the household's own accounts (F-TX-5, invariant §8.3).

A transfer is an outflow on one account and an inflow of the same amount on another, a
few days apart. Detection only suggests pairs: the user confirms them.
"""

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

MAX_DAYS_APART = 3


@dataclass(frozen=True)
class Movement:
    id: UUID
    account_id: UUID
    booked_on: date
    amount: Decimal


def find_transfer_pairs(
    movements: Iterable[Movement], *, max_days: int = MAX_DAYS_APART
) -> list[tuple[UUID, UUID]]:
    """(outflow id, inflow id) pairs; each movement is used at most once.

    Outflows are taken oldest first; each takes the closest unused inflow of the opposite
    amount on another account. Ties break on date then id, so the result does not depend on
    the input order.
    """
    items = list(movements)
    outflows = sorted((m for m in items if m.amount < 0), key=lambda m: (m.booked_on, m.id))
    # Inflows by amount: each outflow only looks at inflows that could match it.
    inflows: dict[Decimal, list[Movement]] = defaultdict(list)
    for m in items:
        if m.amount > 0:
            inflows[m.amount].append(m)
    used: set[UUID] = set()
    pairs = []
    for out in outflows:
        candidates = [
            m
            for m in inflows.get(-out.amount, ())
            if m.id not in used
            and m.account_id != out.account_id
            and abs((m.booked_on - out.booked_on).days) <= max_days
        ]
        if not candidates:
            continue
        best = min(
            candidates, key=lambda m: (abs((m.booked_on - out.booked_on).days), m.booked_on, m.id)
        )
        used.add(best.id)
        pairs.append((out.id, best.id))
    return pairs
