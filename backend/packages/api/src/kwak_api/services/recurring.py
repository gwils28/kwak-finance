"""Recurring items: CRUD, occurrences, suggestions and the upcoming list (F-REC)."""

from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from kwak_core import recurring as core
from kwak_core.accounts import CASH_TYPES, Scope
from kwak_core.recurring import Frequency, Occurrence
from kwak_core.rules import fold
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, joinedload

from kwak_api.models import (
    Account,
    Category,
    DismissedSuggestion,
    RecurringItem,
    RecurringSkip,
    Transaction,
    User,
)
from kwak_api.services.accounts import visible_accounts
from kwak_api.services.budget import scoped_accounts
from kwak_api.services.imports import balances

HISTORY_DAYS = 400
"""How far back occurrences are computed: a year of history, and the last 3 occurrences an
estimated monthly or quarterly amount averages."""
RECENT = 12
"""Past occurrences listed per item."""


@dataclass
class Fields:
    account: Account
    category: Category | None
    label: str
    amount: Decimal
    frequency: Frequency
    day: int
    start_on: date
    end_on: date | None
    estimated: bool
    paused: bool


def _core(item: RecurringItem) -> core.Item:
    return core.Item(
        id=item.id,
        account_id=item.account_id,
        label=item.label,
        amount=item.amount,
        frequency=item.frequency,
        day=item.day,
        start=item.start_on,
        end=item.end_on,
        estimated=item.estimated,
        paused=item.paused,
    )


def _apply(item: RecurringItem, fields: Fields) -> None:
    item.account = fields.account
    item.category_id = fields.category.id if fields.category else None
    item.label = " ".join(fields.label.split())
    item.amount = fields.amount
    item.frequency = fields.frequency
    item.day = fields.day
    item.start_on = fields.start_on
    item.end_on = fields.end_on
    item.estimated = fields.estimated
    item.paused = fields.paused
    core.check_item(_core(item))


def list_items(
    db: Session, viewer: User, accounts: list[UUID] | None = None
) -> list[RecurringItem]:
    """The items on accounts the viewer can see (or on `accounts`), by label."""
    if accounts is None:
        accounts = [a.id for a in visible_accounts(db, viewer, include_closed=True)]
    return list(
        db.scalars(
            select(RecurringItem)
            .where(
                RecurringItem.household_id == viewer.household_id,
                RecurringItem.account_id.in_(accounts),
            )
            .options(joinedload(RecurringItem.account))
            .order_by(RecurringItem.label, RecurringItem.id)
        )
    )


def find(db: Session, viewer: User, item_id: UUID) -> RecurringItem | None:
    return next((i for i in list_items(db, viewer) if i.id == item_id), None)


def create(db: Session, viewer: User, fields: Fields) -> RecurringItem:
    item = RecurringItem(household_id=viewer.household_id)
    _apply(item, fields)
    db.add(item)
    db.flush()
    return item


def update(db: Session, item: RecurringItem, fields: Fields) -> None:
    _apply(item, fields)
    db.flush()


def is_due(item: RecurringItem, day: date) -> bool:
    return core.due_dates(_core(item), day, day) == [day]


def skip(db: Session, item: RecurringItem, due: date) -> None:
    exists = db.scalar(
        select(RecurringSkip).where(RecurringSkip.item_id == item.id, RecurringSkip.due_on == due)
    )
    if exists is None:
        db.add(RecurringSkip(item_id=item.id, due_on=due))
        db.flush()


def unskip(db: Session, item: RecurringItem, due: date) -> None:
    db.execute(
        delete(RecurringSkip).where(RecurringSkip.item_id == item.id, RecurringSkip.due_on == due)
    )


def _booked(db: Session, accounts: list[UUID], first: date, last: date) -> list[core.Booked]:
    """The accounts' transactions between the dates, transfers left out (F-TX-5)."""
    if not accounts:
        return []
    rows = db.execute(
        select(
            Transaction.id,
            Transaction.account_id,
            Transaction.booked_on,
            Transaction.amount,
            Transaction.label_raw,
        ).where(
            Transaction.account_id.in_(accounts),
            Transaction.transfer_group_id.is_(None),
            Transaction.booked_on.between(first, last),
        )
    )
    return [core.Booked(*row) for row in rows]


def _occurrences(
    db: Session, items: list[RecurringItem], first: date, last: date, today: date
) -> list[Occurrence]:
    if not items:
        return []
    margin = timedelta(days=core.TOLERANCE)
    accounts = sorted({i.account_id for i in items})
    skipped = {
        (s.item_id, s.due_on)
        for s in db.scalars(
            select(RecurringSkip).where(RecurringSkip.item_id.in_([i.id for i in items]))
        )
    }
    return core.occurrences(
        [_core(i) for i in items],
        _booked(db, accounts, first - margin, last + margin),
        first,
        last,
        today=today,
        skipped=skipped,
    )


@dataclass
class ItemView:
    item: RecurringItem
    next: Occurrence | None
    recent: list[Occurrence]
    """Due by today, newest first."""


def overview(db: Session, viewer: User, today: date) -> list[ItemView]:
    items = list_items(db, viewer)
    # A yearly item's next occurrence can be a year away.
    found = _occurrences(
        db, items, today - timedelta(days=HISTORY_DAYS), today + timedelta(days=366), today
    )
    by_item: dict[UUID, list[Occurrence]] = {i.id: [] for i in items}
    for o in found:
        by_item[o.item_id].append(o)
    views = []
    for i in items:
        mine = by_item[i.id]
        upcoming = [o for o in mine if o.status is core.OccurrenceStatus.UPCOMING]
        past = [o for o in mine if o.due <= today and o not in upcoming]
        views.append(ItemView(i, upcoming[0] if upcoming else None, past[::-1][:RECENT]))
    return views


@dataclass
class Upcoming:
    occurrences: list[Occurrence]
    items: dict[UUID, RecurringItem]
    current_balance: Decimal
    projected_balance: Decimal


def upcoming(db: Session, viewer: User, scope: Scope, today: date) -> Upcoming:
    """F-REC-4: the scope's open occurrences to the month's end, and the balance they lead to."""
    accounts = scoped_accounts(db, viewer, scope)
    items = list_items(db, viewer, accounts)
    month_end = (today.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    found = _occurrences(db, items, today - timedelta(days=HISTORY_DAYS), month_end, today)
    listed = core.upcoming(found, today=today)
    openings = {a.id: a.opening_balance for a in visible_accounts(db, viewer, include_closed=True)}
    current = sum(
        (openings[a] + movement for a, movement in balances(db, accounts).items()), Decimal(0)
    )
    return Upcoming(
        occurrences=listed,
        items={i.id: i for i in items},
        current_balance=current,
        projected_balance=core.projected_balance(current, listed),
    )


@dataclass
class SuggestionView:
    suggestion: core.Suggestion
    account: Account
    start_on: date
    category_id: UUID | None


def suggestions(db: Session, viewer: User, today: date) -> list[SuggestionView]:
    """F-REC-2: regular series of the viewer's cash accounts, not dismissed nor followed yet."""
    accounts = {
        a.id: a for a in visible_accounts(db, viewer, include_closed=False) if a.type in CASH_TYPES
    }
    if not accounts:
        return []
    since = today - timedelta(days=core.DETECTION_DAYS)
    rows = list(
        db.execute(
            select(
                Transaction.id,
                Transaction.account_id,
                Transaction.booked_on,
                Transaction.amount,
                Transaction.label_raw,
                Transaction.category_id,
            ).where(
                Transaction.account_id.in_(accounts),
                Transaction.transfer_group_id.is_(None),
                Transaction.booked_on.between(since, today),
            )
        )
    )
    booked = [core.Booked(i, a, d, amount, label) for i, a, d, amount, label, _ in rows]
    categories = {r[0]: r[5] for r in rows}
    items = list_items(db, viewer, list(accounts))
    known = {
        o.transaction_id
        for o in _occurrences(db, items, since, today, today)
        if o.transaction_id is not None
    }
    dismissed = {
        (d.account_id, d.label)
        for d in db.scalars(
            select(DismissedSuggestion).where(DismissedSuggestion.account_id.in_(accounts))
        )
    }
    dates = {r[0]: r[2] for r in rows}
    views = []
    for s in core.detect(booked, today=today, dismissed=dismissed, known=known):
        counts = Counter(categories[t] for t in s.transaction_ids if categories[t])
        views.append(
            SuggestionView(
                s,
                accounts[s.account_id],
                min(dates[t] for t in s.transaction_ids),
                counts.most_common(1)[0][0] if counts else None,
            )
        )
    return views


def dismiss(db: Session, account: Account, label: str) -> None:
    label = fold(label)
    exists = db.scalar(
        select(DismissedSuggestion).where(
            DismissedSuggestion.account_id == account.id, DismissedSuggestion.label == label
        )
    )
    if exists is None:
        db.add(DismissedSuggestion(account_id=account.id, label=label))
        db.flush()
