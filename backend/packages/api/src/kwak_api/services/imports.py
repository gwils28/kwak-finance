"""Import bank files into an account: preview first, then commit (F-TX-1, 2, 3, 6)."""

import enum
import hashlib
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from kwak_core.accounts import CASH_TYPES
from kwak_core.balances import balance_on
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
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from kwak_api.models import Account, ImportBatch, Transaction, User

MAX_FILE_BYTES = 2_000_000  # a year of daily card payments is ~50 kB


class ImportRejectedError(ValueError):
    """The file cannot be imported into this account at all."""


class RowStatus(enum.StrEnum):
    NEW = "new"
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


def analyse(db: Session, account: Account, data: bytes) -> Analysis:
    """Parse the file and classify every row against what the account already holds."""
    _check_importable(account)
    bank_format = detect_format(data)
    if bank_format is None:
        raise ImportRejectedError(
            "unrecognised file format: export a CSV of the operations from Société Générale"
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
    file_sha256 = hashlib.sha256(data).hexdigest()
    already = db.scalar(
        select(func.min(ImportBatch.created_at)).where(
            ImportBatch.account_id == account.id,
            ImportBatch.file_sha256 == file_sha256,
            ImportBatch.rolled_back_at.is_(None),
            ImportBatch.imported_count > 0,
        )
    )
    return Analysis(bank_format, statement, rows, file_sha256, already)


def commit(
    db: Session, account: Account, user: User, *, file_name: str, data: bytes, now: datetime
) -> tuple[ImportBatch, BalanceCheck | None]:
    analysis = analyse(db, account, data)
    statement = analysis.statement
    batch = ImportBatch(
        account_id=account.id,
        user_id=user.id,
        format_key=analysis.bank_format.key,
        file_name=file_name[:255],
        file_sha256=analysis.file_sha256,
        imported_count=analysis.count(RowStatus.NEW),
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
    db.add_all(
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
    )
    db.flush()
    return batch, balance_check(db, account, batch)


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
    db.execute(delete(Transaction).where(Transaction.import_batch_id == batch.id))
    batch.rolled_back_at = now
