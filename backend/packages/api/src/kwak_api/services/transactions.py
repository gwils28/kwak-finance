"""Listing, entering and editing transactions (F-TX-4)."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from kwak_core.accounts import CASH_TYPES
from kwak_core.imports import normalize_label
from sqlalchemy import func, select
from sqlalchemy import update as sql_update
from sqlalchemy.orm import Session

from kwak_api.models import Account, Category, Transaction, User
from kwak_api.services.accounts import find_visible_account, visible_accounts
from kwak_api.services.rules import categorise_new


class ImportedTransactionError(Exception):
    """Imported rows mirror the bank: correct them by rolling the import back."""


@dataclass
class TransactionFilter:
    account_id: UUID | None = None
    date_from: date | None = None
    date_to: date | None = None
    q: str | None = None
    category_id: UUID | None = None
    uncategorised: bool = False


def _check_entry(account: Account, booked_on: date, amount: Decimal, label: str) -> str:
    if account.type not in CASH_TYPES:
        raise ValueError("transactions can only be entered on checking and savings accounts")
    if account.closed_on is not None:
        raise ValueError("this account is closed")
    if booked_on < account.opening_date:
        raise ValueError("the date is before the account's opening date")
    if amount == 0:
        raise ValueError("the amount cannot be zero")
    label = " ".join(label.split())
    if not label:
        raise ValueError("a label is required")
    return label


def search(
    db: Session, viewer: User, filters: TransactionFilter, *, limit: int, offset: int
) -> tuple[list[tuple[Transaction, Account]], int]:
    """Transactions of the accounts the viewer can see, newest first, and their total count."""
    accounts = {a.id: a for a in visible_accounts(db, viewer, include_closed=True)}
    ids = [filters.account_id] if filters.account_id in accounts else []
    if filters.account_id is None:
        ids = list(accounts)
    query = select(Transaction).where(Transaction.account_id.in_(ids))
    if filters.date_from:
        query = query.where(Transaction.booked_on >= filters.date_from)
    if filters.date_to:
        query = query.where(Transaction.booked_on <= filters.date_to)
    if filters.q and filters.q.strip():
        needle = (
            normalize_label(filters.q).replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")
        )
        query = query.where(
            func.unaccent(Transaction.label_norm).like(func.unaccent(f"%{needle}%"))
        )
    if filters.category_id:
        query = query.where(Transaction.category_id == filters.category_id)
    if filters.uncategorised:
        query = query.where(Transaction.category_id.is_(None))
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    page = db.scalars(
        query.order_by(Transaction.booked_on.desc(), Transaction.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return [(t, accounts[t.account_id]) for t in page], total


def find_visible(
    db: Session, viewer: User, transaction_id: UUID
) -> tuple[Transaction, Account] | None:
    transaction = db.get(Transaction, transaction_id)
    if transaction is None:
        return None
    account = find_visible_account(db, viewer, transaction.account_id)
    return (transaction, account) if account else None


def create(
    db: Session, account: Account, *, booked_on: date, amount: Decimal, label: str
) -> Transaction:
    label = _check_entry(account, booked_on, amount, label)
    transaction = Transaction(
        account_id=account.id,
        booked_on=booked_on,
        amount=amount,
        label_raw=label,
        label_norm=normalize_label(label),
    )
    categorise_new(db, account.household_id, [transaction])
    db.add(transaction)
    db.flush()
    return transaction


def _manual_only(transaction: Transaction) -> None:
    if transaction.fingerprint is not None:
        raise ImportedTransactionError(
            "imported transactions mirror the bank statement: roll back the import to correct them"
        )


def update(
    db: Session,
    transaction: Transaction,
    account: Account,
    *,
    booked_on: date | None,
    amount: Decimal | None,
    label: str | None,
) -> None:
    """Change what the transaction says. Imported rows mirror the bank and cannot change."""
    if booked_on is None and amount is None and label is None:
        return
    _manual_only(transaction)
    label = _check_entry(
        account,
        booked_on or transaction.booked_on,
        transaction.amount if amount is None else amount,
        label or transaction.label_raw,
    )
    transaction.booked_on = booked_on or transaction.booked_on
    transaction.amount = transaction.amount if amount is None else amount
    transaction.label_raw = label
    transaction.label_norm = normalize_label(label)
    db.flush()


def set_category(db: Session, transaction: Transaction, category: Category | None) -> None:
    """Any transaction, imported or not, can be categorised: it changes no amount."""
    transaction.category_id = category.id if category else None
    db.flush()


def categorise(
    db: Session, viewer: User, transaction_ids: list[UUID], category: Category | None
) -> int:
    """Set the category of every listed transaction the viewer can see; returns how many."""
    visible = [a.id for a in visible_accounts(db, viewer, include_closed=True)]
    result = db.execute(
        sql_update(Transaction)
        .where(Transaction.id.in_(transaction_ids), Transaction.account_id.in_(visible))
        .values(category_id=category.id if category else None)
        .returning(Transaction.id)
    )
    return len(result.all())


def delete(db: Session, transaction: Transaction) -> None:
    _manual_only(transaction)
    db.delete(transaction)
    db.flush()
