"""Transfers between the household's own accounts (F-TX-5, invariant §8.3).

A transfer is an outflow on one account and an inflow of the same amount on another, a
few days apart. Detection only suggests pairs: the user confirms them, links a pair by hand
("Link to…") or enters both sides at once (F-TX-9).
"""

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

MAX_DAYS_APART = 3
LINK_DAYS = 31


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


def link_candidates(
    side: Movement, movements: Iterable[Movement], *, max_days: int = LINK_DAYS
) -> list[UUID]:
    """Movements that can form a transfer with `side`, closest date first ("Link to…").

    The amount must be exactly opposite (invariant §8.3); only the date gap is wider than
    the detection's.
    """
    candidates = [
        m
        for m in movements
        if m.account_id != side.account_id
        and m.amount == -side.amount
        and abs((m.booked_on - side.booked_on).days) <= max_days
    ]
    candidates.sort(key=lambda m: (abs((m.booked_on - side.booked_on).days), m.booked_on, m.id))
    return [m.id for m in candidates]


class TransferEditError(ValueError):
    """The edit would break the transfer."""


@dataclass(frozen=True)
class SideEdit:
    """The fields of a transfer side that change; None keeps the current value."""

    amount: Decimal | None = None
    booked_on: date | None = None


def mirror_edit(side: Movement, other: Movement, edit: SideEdit, *, other_manual: bool) -> SideEdit:
    """What changes on the other side of a transfer when `side` is edited (F-TX-9).

    A manual other side follows: the opposite amount, its date moved by as many days. A side
    from a statement mirrors the bank, so the amount is locked and only `side`'s date moves.
    """
    amount = edit.amount
    if amount is not None:
        if amount == 0 or (amount < 0) != (side.amount < 0):
            raise TransferEditError("a transfer side keeps its direction")
        if amount == side.amount:
            amount = None
        elif not other_manual:
            raise TransferEditError("the other side comes from a statement: the amount is locked")
    if not other_manual:
        return SideEdit()
    return SideEdit(
        amount=None if amount is None else -amount,
        booked_on=None
        if edit.booked_on is None
        else other.booked_on + (edit.booked_on - side.booked_on),
    )
