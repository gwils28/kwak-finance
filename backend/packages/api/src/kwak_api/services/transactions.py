"""Listing, entering and editing transactions (F-TX-4)."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from kwak_core.accounts import CASH_TYPES
from kwak_core.budget import Month
from kwak_core.budget_month import check_manual_month
from kwak_core.imports import normalize_label
from kwak_core.splits import Part, resize
from kwak_core.splits import split as split_parts
from kwak_core.transfers import Movement, SideEdit, mirror_edit
from sqlalchemy import and_, func, or_, select
from sqlalchemy import update as sql_update
from sqlalchemy.orm import Session

from kwak_api.models import Account, Category, Transaction, TransactionPart, User
from kwak_api.services import budget_month
from kwak_api.services.accounts import find_visible_account, visible_accounts
from kwak_api.services.rules import categorise_new


class TransferCategoryError(Exception):
    """A transfer has no category: unlink it first."""


class SplitCategoryError(Exception):
    """A split transaction's categories are its parts': remove the split first."""


class TransferSplitError(Exception):
    """A transfer cannot be split: unlink it first."""


class ImportedTransactionError(Exception):
    """Imported rows mirror the bank: correct them by rolling the import back."""


class HiddenSideError(Exception):
    """The other side of the transfer is on an account the user cannot see: only the label
    of their side can change. Raised before any check of that side, so nothing leaks."""


@dataclass
class TransactionFilter:
    account_id: UUID | None = None
    date_from: date | None = None
    date_to: date | None = None
    q: str | None = None
    category_id: UUID | None = None
    uncategorised: bool = False
    budget_month: Month | None = None


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
        pattern = func.unaccent(f"%{needle}%")
        # The note too (F-TX-4), compared as the label is: in capitals, without accents.
        query = query.where(
            or_(
                func.unaccent(Transaction.label_norm).like(pattern),
                func.unaccent(
                    func.regexp_replace(func.upper(Transaction.note), r"\s+", " ", "g")
                ).like(pattern),
            )
        )
    if filters.budget_month:
        query = query.where(budget_month.in_months(filters.budget_month, filters.budget_month))
    if filters.category_id:
        # A split transaction is found through any of its parts (F-TX-4).
        query = query.where(
            or_(
                Transaction.category_id == filters.category_id,
                Transaction.parts.any(TransactionPart.category_id == filters.category_id),
            )
        )
    if filters.uncategorised:
        # Transfers are not "to categorise": they are neither spending nor income. A split
        # one is, while one of its parts has no category.
        query = query.where(
            Transaction.transfer_group_id.is_(None),
            or_(
                and_(Transaction.category_id.is_(None), ~Transaction.parts.any()),
                Transaction.parts.any(TransactionPart.category_id.is_(None)),
            ),
        )
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
    viewer: User,
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
    if booked_on and transaction.budget_month:
        try:
            check_manual_month(booked_on, Month.of(transaction.budget_month))
        except ValueError:
            raise ValueError(
                "the budget month set by hand would be more than one month from this date"
            ) from None
    other = _other_side(db, transaction)
    if other is not None and (booked_on or amount is not None):
        if find_visible_account(db, viewer, other.account_id) is None:
            raise HiddenSideError
        mirrored = mirror_edit(
            _movement(transaction),
            _movement(other),
            SideEdit(amount=amount, booked_on=booked_on),
            other_manual=other.fingerprint is None,
        )
        if mirrored != SideEdit():
            other_account = db.get_one(Account, other.account_id)
            _check_entry(
                other_account,
                mirrored.booked_on or other.booked_on,
                other.amount if mirrored.amount is None else mirrored.amount,
                other.label_raw,
            )
            other.booked_on = mirrored.booked_on or other.booked_on
            other.amount = other.amount if mirrored.amount is None else mirrored.amount
    if amount is not None and transaction.parts:
        # The last part takes the difference (F-TX-4); SplitError is a ValueError.
        _set_parts(transaction, resize(_core_parts(transaction), amount))
    transaction.booked_on = booked_on or transaction.booked_on
    transaction.amount = transaction.amount if amount is None else amount
    transaction.label_raw = label
    transaction.label_norm = normalize_label(label)
    db.flush()


def _movement(t: Transaction) -> Movement:
    return Movement(t.id, t.account_id, t.booked_on, t.amount)


def _other_side(db: Session, transaction: Transaction) -> Transaction | None:
    """The other side of the transfer the transaction belongs to, if any."""
    if transaction.transfer_group_id is None:
        return None
    return db.scalar(
        select(Transaction).where(
            Transaction.transfer_group_id == transaction.transfer_group_id,
            Transaction.id != transaction.id,
        )
    )


class TransferMonthError(Exception):
    """A transfer counts in its booking month, as both its legs must (F-TX-7)."""


def set_budget_month(db: Session, transaction: Transaction, month: Month | None) -> None:
    """Set by hand the month the transaction counts in, or go back to the category's rule
    (None). Imported transactions too: it changes no amount."""
    if transaction.transfer_group_id is not None:
        raise TransferMonthError
    if month is not None:
        check_manual_month(transaction.booked_on, month)
    transaction.budget_month = month.first_day() if month else None
    db.flush()


def set_category(db: Session, transaction: Transaction, category: Category | None) -> None:
    """Any transaction, imported or not, can be categorised: it changes no amount."""
    if category is not None and transaction.transfer_group_id is not None:
        raise TransferCategoryError
    if category is not None and transaction.parts:
        raise SplitCategoryError
    transaction.category_id = category.id if category else None
    db.flush()


def categorise(
    db: Session, viewer: User, transaction_ids: list[UUID], category: Category | None
) -> int:
    """Set the category of every listed transaction the viewer can see; returns how many."""
    visible = [a.id for a in visible_accounts(db, viewer, include_closed=True)]
    result = db.execute(
        sql_update(Transaction)
        .where(
            Transaction.id.in_(transaction_ids),
            Transaction.account_id.in_(visible),
            Transaction.transfer_group_id.is_(None),
            ~Transaction.parts.any(),
        )
        .values(category_id=category.id if category else None)
        .returning(Transaction.id)
    )
    return len(result.all())


def _core_parts(transaction: Transaction) -> list[Part]:
    return [Part(p.category_id, p.amount) for p in transaction.parts]


def _set_parts(transaction: Transaction, parts: list[Part]) -> None:
    # Updated in place, position by position: the unique (transaction, position) index would
    # refuse new rows inserted before the old ones are deleted.
    rows = transaction.parts
    del rows[len(parts) :]
    for position, part in enumerate(parts):
        if position == len(rows):
            rows.append(TransactionPart(position=position))
        rows[position].category_id = part.category_id
        rows[position].amount = part.amount


def split(
    db: Session,
    transaction: Transaction,
    given: list[tuple[Category | None, Decimal]],
    rest: Category | None,
) -> None:
    """Spread the transaction over categories: the given parts, then the rest (F-TX-4).
    Imported transactions too: it changes no amount."""
    if transaction.transfer_group_id is not None:
        raise TransferSplitError
    parts = split_parts(
        transaction.amount,
        [Part(c.id if c else None, amount) for c, amount in given],
        rest.id if rest else None,
    )
    _set_parts(transaction, parts)
    transaction.category_id = None
    db.flush()


def unsplit(db: Session, transaction: Transaction) -> None:
    """Back to a single category: to categorise until one is chosen."""
    transaction.parts.clear()
    db.flush()


def set_note(db: Session, transaction: Transaction, note: str | None) -> None:
    """Any transaction, imported or not, can carry a note: it changes no amount."""
    note = note.strip() if note else None
    transaction.note = note or None
    db.flush()


def delete(db: Session, viewer: User, transaction: Transaction) -> None:
    """Delete a manual entry. A transfer goes with its other side when that one is a manual
    entry too; a side from a statement is only unlinked (F-TX-9)."""
    _manual_only(transaction)
    other = _other_side(db, transaction)
    if other is not None and find_visible_account(db, viewer, other.account_id) is None:
        raise HiddenSideError
    if other is not None and other.fingerprint is None:
        db.delete(other)
    elif other is not None:
        other.transfer_group_id = None
    db.delete(transaction)
    db.flush()
