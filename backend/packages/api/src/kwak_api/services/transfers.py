"""Transfers between own accounts: suggested from matching pairs, confirmed by the user."""

from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from kwak_core.accounts import CASH_TYPES
from kwak_core.ids import uuid7
from kwak_core.transfers import LINK_DAYS, Movement, find_transfer_pairs, link_candidates
from sqlalchemy import select
from sqlalchemy.orm import Session

from kwak_api.models import Account, Transaction, User
from kwak_api.services import transactions
from kwak_api.services.accounts import visible_accounts


class TransferError(ValueError):
    """The two transactions cannot form a transfer."""


class AlreadyLinkedError(Exception):
    pass


def _cash_accounts(db: Session, viewer: User) -> dict[UUID, Account]:
    return {
        a.id: a for a in visible_accounts(db, viewer, include_closed=True) if a.type in CASH_TYPES
    }


def suggestions(db: Session, viewer: User) -> list[tuple[Transaction, Transaction]]:
    """Likely transfers among unlinked transactions of accounts the viewer can see."""
    accounts = _cash_accounts(db, viewer)
    candidates = {
        t.id: t
        for t in db.scalars(
            select(Transaction).where(
                Transaction.account_id.in_(accounts),
                Transaction.transfer_group_id.is_(None),
                ~Transaction.parts.any(),
            )
        )
    }
    pairs = find_transfer_pairs(
        Movement(t.id, t.account_id, t.booked_on, t.amount) for t in candidates.values()
    )
    return [(candidates[out], candidates[inn]) for out, inn in pairs]


def find(db: Session, viewer: User, transaction_id: UUID) -> Transaction | None:
    transaction = db.get(Transaction, transaction_id)
    if transaction is None or transaction.account_id not in _cash_accounts(db, viewer):
        return None
    return transaction


def link(db: Session, outflow: Transaction, inflow: Transaction) -> UUID:
    if outflow.transfer_group_id or inflow.transfer_group_id:
        raise AlreadyLinkedError
    if outflow.account_id == inflow.account_id:
        raise TransferError("a transfer moves money between two different accounts")
    if outflow.parts or inflow.parts:
        raise TransferError("a split transaction cannot be a side of a transfer")
    if not (outflow.amount < 0 < inflow.amount) or outflow.amount + inflow.amount != 0:
        raise TransferError("a transfer is an outflow and an inflow of the same amount")
    group = uuid7()
    for t in (outflow, inflow):
        t.transfer_group_id = group
        t.category_id = None
        t.budget_month = None  # a transfer counts in its booking month (F-TX-7)
    db.flush()
    return group


def enter(
    db: Session,
    source: Account,
    destination: Account,
    *,
    booked_on: date,
    amount: Decimal,
    outflow_label: str,
    inflow_label: str,
) -> tuple[UUID, Transaction, Transaction]:
    """Enter both sides of a transfer by hand, already linked (F-TX-9)."""
    if source.id == destination.id:
        raise TransferError("a transfer moves money between two different accounts")
    if amount <= 0:
        raise TransferError("the amount of a transfer is positive")
    outflow = transactions.create(
        db, source, booked_on=booked_on, amount=-amount, label=outflow_label
    )
    inflow = transactions.create(
        db, destination, booked_on=booked_on, amount=amount, label=inflow_label
    )
    return link(db, outflow, inflow), outflow, inflow


def candidates(db: Session, viewer: User, transaction: Transaction) -> list[Transaction]:
    """Unlinked transactions that could form a transfer with this one ("Link to…")."""
    if transaction.transfer_group_id is not None:
        raise AlreadyLinkedError
    accounts = _cash_accounts(db, viewer)
    window = timedelta(days=LINK_DAYS)
    others = {
        t.id: t
        for t in db.scalars(
            select(Transaction).where(
                Transaction.account_id.in_(accounts),
                Transaction.transfer_group_id.is_(None),
                ~Transaction.parts.any(),
                Transaction.amount == -transaction.amount,
                Transaction.booked_on.between(
                    transaction.booked_on - window, transaction.booked_on + window
                ),
            )
        )
    }
    side = Movement(
        transaction.id, transaction.account_id, transaction.booked_on, transaction.amount
    )
    return [
        others[i]
        for i in link_candidates(
            side, (Movement(t.id, t.account_id, t.booked_on, t.amount) for t in others.values())
        )
    ]


def unlink(db: Session, viewer: User, group_id: UUID) -> bool:
    accounts = _cash_accounts(db, viewer)
    sides = list(db.scalars(select(Transaction).where(Transaction.transfer_group_id == group_id)))
    if not sides or any(t.account_id not in accounts for t in sides):
        return False
    for t in sides:
        t.transfer_group_id = None
    db.flush()
    return True


def accept_all(db: Session, viewer: User) -> int:
    pairs = suggestions(db, viewer)
    for outflow, inflow in pairs:
        link(db, outflow, inflow)
    return len(pairs)


def counterparts(db: Session, viewer: User, transactions: list[Transaction]) -> dict[UUID, str]:
    """For each linked transaction, the name of the account on the other side."""
    groups = {t.transfer_group_id for t in transactions if t.transfer_group_id}
    if not groups:
        return {}
    accounts = _cash_accounts(db, viewer)
    sides = list(db.scalars(select(Transaction).where(Transaction.transfer_group_id.in_(groups))))
    names = {}
    for t in transactions:
        if t.transfer_group_id is None:
            continue
        other = next(
            (s for s in sides if s.transfer_group_id == t.transfer_group_id and s.id != t.id), None
        )
        if other is not None:
            account = accounts.get(other.account_id)
            names[t.id] = account.name if account else "another account"
    return names
