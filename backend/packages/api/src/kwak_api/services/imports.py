"""Import bank files into an account: preview first, then commit (F-TX-1, 2, 3, 6, 8)."""

import enum
import hashlib
from collections.abc import Collection
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from kwak_core.accounts import CASH_TYPES
from kwak_core.balances import balance_on
from kwak_core.budget import Month
from kwak_core.budget_month import check_manual_month
from kwak_core.imports import (
    BankFormat,
    ParsedRow,
    Statement,
    detect_format,
    normalize_label,
    parse_statement,
    plan_import,
)
from kwak_core.imports.dedup import fingerprint_rows
from kwak_core.imports.reconcile import MATCH_DAYS, Entry, reconcile
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from kwak_api.models import Account, ImportBatch, Transaction, User
from kwak_api.services.rules import categorise_new

MAX_FILE_BYTES = 2_000_000  # a year of daily card payments is ~50 kB


class ImportRejectedError(ValueError):
    """The file cannot be imported into this account at all."""


class RowStatus(enum.StrEnum):
    NEW = "new"
    ALREADY_ENTERED = "already_entered"
    """The row takes over a manual entry (F-TX-8)."""
    DUPLICATE = "duplicate"
    BEFORE_OPENING = "before_opening"


@dataclass
class Analysis:
    bank_format: BankFormat
    statement: Statement
    rows: list[tuple[ParsedRow, RowStatus, str]]
    """Every parsed row, with its status and fingerprint."""
    file_sha256: str
    already_imported_at: datetime | None
    entries: dict[int, Transaction] = field(default_factory=dict)
    """Row line -> the manual entry it takes over."""
    unmatched: list[Transaction] = field(default_factory=list)
    """Manual entries within the statement's dates that no row took."""

    def count(self, status: RowStatus) -> int:
        return sum(1 for _, s, _ in self.rows if s is status)


@dataclass
class BalanceCheck:
    on: date
    bank: Decimal
    computed: Decimal

    @property
    def difference(self) -> Decimal:
        return self.computed - self.bank


def _check_importable(account: Account) -> None:
    if account.type not in CASH_TYPES:
        raise ImportRejectedError("only checking and savings accounts take bank statements")
    if account.closed_on is not None:
        raise ImportRejectedError("this account is closed: reopen it to import")


def _manual_entries(db: Session, account: Account, start: date, end: date) -> list[Transaction]:
    """The account's manual entries not yet reconciled, near the statement's dates."""
    margin = timedelta(days=MATCH_DAYS)
    return list(
        db.scalars(
            select(Transaction).where(
                Transaction.account_id == account.id,
                Transaction.fingerprint.is_(None),
                Transaction.booked_on >= start - margin,
                Transaction.booked_on <= end + margin,
            )
        )
    )


def analyse(
    db: Session, account: Account, data: bytes, *, refused: Collection[tuple[int, UUID]] = ()
) -> Analysis:
    """Parse the file and classify every row against what the account already holds.

    `refused` holds the (row line, manual entry) matches the user undid in the preview."""
    _check_importable(account)
    bank_format = detect_format(data)
    if bank_format is None:
        raise ImportRejectedError(
            "unrecognised file format: export a CSV of the operations from Société Générale"
            " or Helios"
        )
    statement = parse_statement(bank_format, data)
    # Fingerprints over the whole file, in file order: occurrence ranks must not depend on
    # which rows are later skipped.
    prints = fingerprint_rows(statement.rows)
    existing = set(
        db.scalars(
            select(Transaction.fingerprint).where(
                Transaction.account_id == account.id, Transaction.fingerprint.in_(prints)
            )
        )
    )
    plan = plan_import(statement.rows, existing={p for p in existing if p})
    duplicates = {fp for fp, _ in plan.duplicates}
    rows = []
    for fp, row in zip(prints, statement.rows, strict=True):
        if row.booked_on < account.opening_date:
            status = RowStatus.BEFORE_OPENING
        elif fp in duplicates:
            status = RowStatus.DUPLICATE
        else:
            status = RowStatus.NEW
        rows.append((row, status, fp))
    entries, unmatched = _reconcile(db, account, statement, rows, refused)
    rows = [
        (row, RowStatus.ALREADY_ENTERED if row.line in entries else status, fp)
        for row, status, fp in rows
    ]
    file_sha256 = hashlib.sha256(data).hexdigest()
    already = db.scalar(
        select(func.min(ImportBatch.created_at)).where(
            ImportBatch.account_id == account.id,
            ImportBatch.file_sha256 == file_sha256,
            ImportBatch.rolled_back_at.is_(None),
            ImportBatch.imported_count > 0,
        )
    )
    return Analysis(bank_format, statement, rows, file_sha256, already, entries, unmatched)


def _reconcile(
    db: Session,
    account: Account,
    statement: Statement,
    rows: list[tuple[ParsedRow, RowStatus, str]],
    refused: Collection[tuple[int, UUID]],
) -> tuple[dict[int, Transaction], list[Transaction]]:
    new = [row for row, status, _ in rows if status is RowStatus.NEW]
    period = statement.period or (
        (min(r.booked_on for r, _, _ in rows), max(r.booked_on for r, _, _ in rows))
        if rows
        else None
    )
    if period is None:
        return {}, []
    manual = {t.id: t for t in _manual_entries(db, account, *period)}
    result = reconcile(
        new,
        [Entry(t.id, t.booked_on, t.amount, t.created_at) for t in manual.values()],
        refused=refused,
        period=period,
    )
    return (
        {line: manual[entry_id] for line, entry_id in result.matches.items()},
        [manual[e.id] for e in result.unmatched],
    )


def commit(
    db: Session,
    account: Account,
    user: User,
    *,
    file_name: str,
    data: bytes,
    now: datetime,
    refused: Collection[tuple[int, UUID]] = (),
) -> tuple[ImportBatch, BalanceCheck | None]:
    analysis = analyse(db, account, data, refused=refused)
    statement = analysis.statement
    batch = ImportBatch(
        account_id=account.id,
        user_id=user.id,
        format_key=analysis.bank_format.key,
        file_name=file_name[:255],
        file_sha256=analysis.file_sha256,
        imported_count=analysis.count(RowStatus.NEW),
        reconciled_count=analysis.count(RowStatus.ALREADY_ENTERED),
        duplicate_count=analysis.count(RowStatus.DUPLICATE),
        skipped_count=analysis.count(RowStatus.BEFORE_OPENING),
        error_count=len(statement.errors),
        period_start=statement.period[0] if statement.period else None,
        period_end=statement.period[1] if statement.period else None,
        bank_balance=statement.balance.amount if statement.balance else None,
        bank_balance_on=statement.balance.on if statement.balance else None,
        created_at=now,
    )
    db.add(batch)
    db.flush()
    new = [
        Transaction(
            account_id=account.id,
            booked_on=row.booked_on,
            amount=row.amount,
            label_raw=row.label,
            label_norm=normalize_label(row.label),
            fingerprint=fp,
            import_batch_id=batch.id,
        )
        for row, status, fp in analysis.rows
        if status is RowStatus.NEW
    ]
    for row, status, fp in analysis.rows:
        if status is RowStatus.ALREADY_ENTERED:
            _take_over(analysis.entries[row.line], row, fp, batch)
    categorise_new(db, account.household_id, new)
    db.add_all(new)
    db.flush()
    return batch, balance_check(db, account, batch)


def _take_over(entry: Transaction, row: ParsedRow, fp: str, batch: ImportBatch) -> None:
    """The entry keeps its label, category, transfer link and budget month set by hand, and
    takes the row's date; a hand-set month too far from that date goes back to automatic."""
    entry.entered_on = entry.booked_on
    entry.booked_on = row.booked_on
    entry.bank_label = row.label
    entry.fingerprint = fp
    entry.import_batch_id = batch.id
    if entry.budget_month is not None:
        try:
            check_manual_month(row.booked_on, Month.of(entry.budget_month))
        except ValueError:
            entry.budget_month = None


def balance_check(db: Session, account: Account, batch: ImportBatch) -> BalanceCheck | None:
    """Compare the balance the bank reports with the one computed from stored transactions."""
    if batch.bank_balance is None or batch.bank_balance_on is None:
        return None
    movements = db.execute(
        select(Transaction.booked_on, Transaction.amount).where(
            Transaction.account_id == account.id,
            Transaction.booked_on <= batch.bank_balance_on,
        )
    )
    computed = balance_on(account.opening_balance, movements, on=batch.bank_balance_on)
    return BalanceCheck(on=batch.bank_balance_on, bank=batch.bank_balance, computed=computed)


def balances(db: Session, account_ids: list[UUID]) -> dict[UUID, Decimal]:
    """Sum of the transactions of each account (0 when it has none)."""
    sums = db.execute(
        select(Transaction.account_id, func.sum(Transaction.amount))
        .where(Transaction.account_id.in_(account_ids))
        .group_by(Transaction.account_id)
    )
    totals = {account_id: Decimal(0) for account_id in account_ids}
    for account_id, total in sums:
        totals[account_id] = total
    return totals


def batches(db: Session, account: Account) -> list[ImportBatch]:
    return list(
        db.scalars(
            select(ImportBatch)
            .where(ImportBatch.account_id == account.id)
            .order_by(ImportBatch.created_at.desc())
        )
    )


def rollback(db: Session, batch: ImportBatch, now: datetime) -> None:
    """Delete the rows the import added and give back the manual entries it took over."""
    db.execute(
        update(Transaction)
        .where(Transaction.import_batch_id == batch.id, Transaction.entered_on.is_not(None))
        .values(
            booked_on=Transaction.entered_on,
            entered_on=None,
            bank_label=None,
            fingerprint=None,
            import_batch_id=None,
        )
    )
    # A deleted row takes its transfer with it: the other side stays, unlinked (F-TX-5), even
    # on an account the caller cannot see. Unlike deleting a manual entry, which a hidden side
    # refuses, the bank row is gone either way and a half transfer would count as nothing.
    groups = select(Transaction.transfer_group_id).where(
        Transaction.import_batch_id == batch.id, Transaction.transfer_group_id.is_not(None)
    )
    db.execute(
        update(Transaction)
        .where(Transaction.transfer_group_id.in_(groups))
        .values(transfer_group_id=None)
    )
    db.execute(delete(Transaction).where(Transaction.import_batch_id == batch.id))
    batch.rolled_back_at = now
