"""Recurring items (F-REC): expected transactions, their occurrences and what is still to come.

An item never creates a transaction: a transaction of the item's account whose label matches
(as a rule's, F-CAT-2), with the expected sign and amount, at most TOLERANCE days from a due
date fulfils that occurrence (§8.16). A transfer item expects a linked transfer from its
account to another one instead, whatever the label (F-TX-9). Detection suggests weekly and
monthly series, transfers left out.
"""

import calendar
import enum
from collections import defaultdict
from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from itertools import pairwise
from statistics import median
from uuid import UUID

from kwak_core.accounts import CASH_TYPES, AccountType
from kwak_core.rules import fold

TOLERANCE = 5
"""Days between a due date and the transaction that fulfils it; then the occurrence is late."""
AMOUNT_TOLERANCE = Decimal("0.10")
FIXED_TOLERANCE = Decimal("0.01")
DETECTION_DAYS = 183
LATE_WINDOW = 31
"""Days back the upcoming list (F-REC-4) still shows a late occurrence."""
CENT = Decimal("0.01")


class Frequency(enum.StrEnum):
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"


_MONTHS = {Frequency.MONTHLY: 1, Frequency.QUARTERLY: 3, Frequency.YEARLY: 12}


@dataclass(frozen=True)
class Item:
    id: UUID
    account_id: UUID
    label: str
    amount: Decimal
    """Signed, as a transaction's; for an estimated item, the amount until there is history."""
    frequency: Frequency
    day: int
    """0 (Monday) to 6 for a weekly item, else 1-31: the last day stands in for a missing one."""
    start: date
    """Due from this date; quarterly and yearly items repeat from its month."""
    end: date | None = None
    estimated: bool = False
    """The amount is the average of the last 3 occurrences (e.g. electricity)."""
    paused: bool = False
    destination_id: UUID | None = None
    """Set for a transfer item: the account it pays into. Its amount is then the outflow of
    `account_id` and its label is not matched."""
    category_id: UUID | None = None


@dataclass(frozen=True)
class Booked:
    """A transaction, as recurring items see it. Of a linked transfer, the caller passes only
    the outflow side, with the account it went to."""

    id: UUID
    account_id: UUID
    booked_on: date
    amount: Decimal
    label: str
    transfer_to: UUID | None = None


class OccurrenceStatus(enum.StrEnum):
    FULFILLED = "fulfilled"
    UPCOMING = "upcoming"
    LATE = "late"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class Occurrence:
    item_id: UUID
    due: date
    expected: Decimal
    status: OccurrenceStatus
    transaction_id: UUID | None = None


class RecurringError(ValueError):
    """An item that cannot be followed: no label, no amount, or a day out of range."""


def check_item(item: Item) -> None:
    if item.destination_id is not None:
        if item.destination_id == item.account_id:
            raise RecurringError("a transfer moves money between two different accounts")
        if item.amount > 0:
            raise RecurringError("a transfer item's amount is what leaves its account")
        if item.category_id is not None:
            raise RecurringError("a transfer item has no category")
    elif not item.label.strip():
        raise RecurringError("a recurring item needs a label")
    if item.amount == 0:
        raise RecurringError("a recurring item needs an amount")
    days = range(7) if item.frequency is Frequency.WEEKLY else range(1, 32)
    if item.day not in days:
        raise RecurringError(f"day {item.day} is out of range for a {item.frequency} item")
    if item.end is not None and item.end < item.start:
        raise RecurringError("a recurring item cannot end before it starts")


def check_transfer_accounts(source: AccountType, destination: AccountType) -> None:
    """A transfer item moves money between two checking or savings accounts (F-TX-9)."""
    if {source, destination} - CASH_TYPES:
        raise RecurringError("a transfer moves money between checking or savings accounts")


def _clamp(year: int, month: int, day: int) -> date:
    return date(year, month, min(day, calendar.monthrange(year, month)[1]))


def due_dates(item: Item, first: date, last: date) -> list[date]:
    """The item's due dates from `first` to `last`, both included."""
    if item.paused:
        return []
    first = max(first, item.start)
    if item.end is not None:
        last = min(last, item.end)
    if first > last:
        return []
    if item.frequency is Frequency.WEEKLY:
        day = first + timedelta(days=(item.day - first.weekday()) % 7)
        return [day + timedelta(weeks=w) for w in range((last - day).days // 7 + 1)]
    step = _MONTHS[item.frequency]
    dates: list[date] = []
    index = item.start.year * 12 + item.start.month - 1
    while True:
        due = _clamp(index // 12, index % 12 + 1, item.day)
        if due > last:
            return dates
        if due >= first:
            dates.append(due)
        index += step


def estimate(amounts: Sequence[Decimal]) -> Decimal | None:
    """The average of the last 3 amounts (oldest first), in cents."""
    recent = list(amounts)[-3:]
    if not recent:
        return None
    return (sum(recent, Decimal(0)) / len(recent)).quantize(CENT, rounding=ROUND_HALF_UP)


def _fits(item: Item, txn: Booked) -> bool:
    if txn.account_id != item.account_id or txn.transfer_to != item.destination_id:
        return False
    if item.destination_id is None and fold(item.label) not in fold(txn.label):
        return False
    if (txn.amount < 0) != (item.amount < 0):
        return False
    # An estimated amount varies (a seasonal bill): the sign is enough.
    return item.estimated or abs(txn.amount - item.amount) <= AMOUNT_TOLERANCE * abs(item.amount)


def occurrences(
    items: Iterable[Item],
    transactions: Iterable[Booked],
    first: date,
    last: date,
    *,
    today: date,
    skipped: Collection[tuple[UUID, date]] = (),
) -> list[Occurrence]:
    """Every occurrence from `first` to `last`, by due date. A transaction fulfils one at most
    and each occurrence takes the closest one; give some history before `today` so estimated
    amounts have their last occurrences."""
    items = list(items)
    txns = list(transactions)
    dues = [(i, d) for i in items for d in due_dates(i, first, last)]
    candidates = sorted(
        (
            (abs((t.booked_on - d).days), d, t.booked_on, str(t.id), k, t)
            for k, (i, d) in enumerate(dues)
            if (i.id, d) not in skipped
            for t in txns
            if abs((t.booked_on - d).days) <= TOLERANCE and _fits(i, t)
        ),
        key=lambda c: c[:4],
    )
    taken: dict[int, Booked] = {}
    used: set[UUID] = set()
    for *_, k, t in candidates:
        if k not in taken and t.id not in used:
            taken[k] = t
            used.add(t.id)

    history: dict[UUID, list[Decimal]] = defaultdict(list)
    result = []
    for k, (i, d) in sorted(enumerate(dues), key=lambda kd: (kd[1][1], str(kd[1][0].id))):
        expected = (estimate(history[i.id]) if i.estimated else None) or i.amount
        if (txn := taken.get(k)) is not None:
            history[i.id].append(txn.amount)
            result.append(Occurrence(i.id, d, expected, OccurrenceStatus.FULFILLED, txn.id))
        elif (i.id, d) in skipped:
            result.append(Occurrence(i.id, d, expected, OccurrenceStatus.SKIPPED))
        else:
            late = today > d + timedelta(days=TOLERANCE)
            status = OccurrenceStatus.LATE if late else OccurrenceStatus.UPCOMING
            result.append(Occurrence(i.id, d, expected, status))
    return result


def entry_date(due: date, today: date) -> date:
    """The date "Enter it" proposes: the expected one, or today if that is still to come."""
    return min(due, today)


def upcoming(expected: Iterable[Occurrence], *, today: date) -> list[Occurrence]:
    """The open occurrences from LATE_WINDOW days ago to the end of the month, late first."""
    end = _clamp(today.year, today.month, 31)
    since = today - timedelta(days=LATE_WINDOW)
    open_ = (OccurrenceStatus.UPCOMING, OccurrenceStatus.LATE)
    return sorted(
        (o for o in expected if o.status in open_ and since <= o.due <= end),
        key=lambda o: (o.status is not OccurrenceStatus.LATE, o.due, str(o.item_id)),
    )


def scope_amount(item: Item, expected: Decimal, accounts: Collection[UUID]) -> Decimal:
    """What an occurrence brings to a scope's accounts: a transfer item takes its amount from
    its account and gives it to its destination, so it nets to zero when both are in scope."""
    amount = expected if item.account_id in accounts else Decimal(0)
    if item.destination_id is not None and item.destination_id in accounts:
        amount -= expected
    return amount


def projected_balance(
    current: Decimal,
    expected: Iterable[Occurrence],
    *,
    items: Mapping[UUID, Item] | None = None,
    accounts: Collection[UUID] | None = None,
) -> Decimal:
    """The current balance plus what the upcoming and late occurrences will bring (§8.16).
    With the items and the scope's accounts, each counts by `scope_amount`."""
    open_ = (OccurrenceStatus.UPCOMING, OccurrenceStatus.LATE)
    total = Decimal(0)
    for o in expected:
        if o.status not in open_:
            continue
        if items is None or accounts is None:
            total += o.expected
        else:
            total += scope_amount(items[o.item_id], o.expected, accounts)
    return current + total


@dataclass(frozen=True)
class Suggestion:
    account_id: UUID
    label: str
    """The folded label the series shares."""
    amount: Decimal
    estimated: bool
    frequency: Frequency
    day: int
    transaction_ids: list[UUID] = field(default_factory=list)


def _frequency(days: list[date]) -> Frequency | None:
    gaps = [(b - a).days for a, b in pairwise(days)]
    if all(5 <= g <= 9 for g in gaps):
        return Frequency.WEEKLY
    if all(25 <= g <= 36 for g in gaps):
        return Frequency.MONTHLY
    return None


def detect(
    transactions: Iterable[Booked],
    *,
    today: date,
    dismissed: Collection[tuple[UUID, str]] = (),
    known: Collection[UUID] = (),
) -> list[Suggestion]:
    """Weekly or monthly series of the last 6 months: at least 3 transactions of one account
    with the same label, at a regular interval, the amounts within 10 % (fixed within 1 %).

    `dismissed` holds the (account, folded label) series the user dismissed; a series with a
    transaction in `known` (one fulfilling an item) is already followed."""
    since = today - timedelta(days=DETECTION_DAYS)
    groups: dict[tuple[UUID, str], list[Booked]] = defaultdict(list)
    for t in transactions:
        if t.transfer_to is None and since <= t.booked_on <= today:
            groups[(t.account_id, fold(t.label))].append(t)
    suggestions = []
    for (account, label), series in sorted(groups.items(), key=lambda g: (str(g[0][0]), g[0][1])):
        series.sort(key=lambda t: (t.booked_on, str(t.id)))
        if len(series) < 3 or (account, label) in dismissed:
            continue
        if any(t.id in known for t in series):
            continue
        frequency = _frequency([t.booked_on for t in series])
        amounts = [t.amount for t in series]
        middle = Decimal(median(amounts))
        if frequency is None or middle == 0:
            continue
        spread = max(abs(a - middle) for a in amounts) / abs(middle)
        if spread >= AMOUNT_TOLERANCE or any((a < 0) != (middle < 0) for a in amounts):
            continue
        estimated = spread > FIXED_TOLERANCE
        last = series[-1]
        suggestions.append(
            Suggestion(
                account,
                label,
                (estimate(amounts) or last.amount) if estimated else last.amount,
                estimated,
                frequency,
                last.booked_on.weekday() if frequency is Frequency.WEEKLY else last.booked_on.day,
                [t.id for t in series],
            )
        )
    return suggestions
