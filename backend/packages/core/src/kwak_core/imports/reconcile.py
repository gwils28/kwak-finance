"""Reconciling manual entries with a statement (F-TX-8).

Most transactions are entered by hand during the month and the bank's statement comes later:
a statement row that matches a manual entry (same account, same amount, at most MATCH_DAYS
apart) takes the entry over instead of adding the transaction twice (§8.17). The caller
passes the rows still to import and the account's manual entries not yet reconciled.
"""

from collections.abc import Collection, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from kwak_core.imports.model import ParsedRow

MATCH_DAYS = 5


@dataclass(frozen=True)
class Entry:
    """A manual entry of the account, not yet reconciled."""

    id: UUID
    booked_on: date
    amount: Decimal
    entered_at: datetime


@dataclass
class Reconciliation:
    matches: dict[int, UUID] = field(default_factory=dict)
    """Row line -> the entry it takes over."""
    unmatched: list[Entry] = field(default_factory=list)
    """Entries within the statement's dates that no row took: a typo, or not booked yet."""


def reconcile(
    rows: Sequence[ParsedRow],
    entries: Sequence[Entry],
    *,
    refused: Collection[tuple[int, UUID]] = (),
    period: tuple[date, date] | None = None,
) -> Reconciliation:
    """Match rows and entries one to one: the closest dates first, then the earliest entered.

    `refused` holds the (row line, entry) matches the user undid; `period` is the statement's
    first and last date (default: the rows').
    """
    candidates = sorted(
        (
            (abs((r.booked_on - e.booked_on).days), e.entered_at, r.line, e)
            for r in rows
            for e in entries
            if r.amount == e.amount
            and abs((r.booked_on - e.booked_on).days) <= MATCH_DAYS
            and (r.line, e.id) not in refused
        ),
        key=lambda c: (c[0], c[1], c[2], str(c[3].id)),
    )
    result = Reconciliation()
    taken: set[UUID] = set()
    for _, _, line, e in candidates:
        if line not in result.matches and e.id not in taken:
            result.matches[line] = e.id
            taken.add(e.id)
    if period is None and rows:
        period = (min(r.booked_on for r in rows), max(r.booked_on for r in rows))
    if period is not None:
        first, last = period
        result.unmatched = sorted(
            (e for e in entries if e.id not in taken and first <= e.booked_on <= last),
            key=lambda e: (e.booked_on, e.entered_at),
        )
    return result
