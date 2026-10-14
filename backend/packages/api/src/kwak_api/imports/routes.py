from datetime import date, datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from kwak_core.audit import AuditAction
from pydantic import BaseModel

from kwak_api.auth.routes import CurrentSession, Db, Now
from kwak_api.models import Account, ImportBatch, Transaction, User
from kwak_api.services import accounts as account_service
from kwak_api.services import audit
from kwak_api.services import imports as service

router = APIRouter(prefix="/api", tags=["imports"])

Upload = Annotated[UploadFile, File(description="Bank export (CSV)")]
Refused = Annotated[
    list[str] | None,
    Form(description="Matches undone in the preview, as '<row line>:<manual entry id>' (F-TX-8)"),
]
NOT_FOUND = HTTPException(status.HTTP_404_NOT_FOUND, "account not found")


class Period(BaseModel):
    start: date
    end: date


class BankBalance(BaseModel):
    on: date
    amount: Decimal


class EnteredOut(BaseModel):
    """A manual entry, as the user entered it."""

    id: UUID
    booked_on: date
    label: str
    amount: Decimal

    @classmethod
    def of(cls, entry: Transaction) -> "EnteredOut":
        return cls(
            id=entry.id, booked_on=entry.booked_on, label=entry.label_raw, amount=entry.amount
        )


class PreviewRow(BaseModel):
    line: int
    booked_on: date
    label: str
    amount: Decimal
    status: service.RowStatus
    entry: EnteredOut | None = None
    """The manual entry the row takes over, when already_entered (F-TX-8)."""


class RowErrorOut(BaseModel):
    line: int
    """0 when the problem concerns the whole file."""
    message: str


class PreviewCounts(BaseModel):
    new: int
    already_entered: int
    duplicate: int
    before_opening: int
    error: int


class ImportPreview(BaseModel):
    format: str
    format_label: str
    period: Period | None
    bank_balance: BankBalance | None
    counts: PreviewCounts
    rows: list[PreviewRow]
    errors: list[RowErrorOut]
    already_imported_at: datetime | None
    """When this exact file was already imported into this account, if it was."""
    unmatched_entries: list[EnteredOut]
    """Manual entries within the statement's dates that no row took: a typo, or not booked by
    the bank yet."""


class BalanceCheckOut(BaseModel):
    on: date
    bank: Decimal
    computed: Decimal
    difference: Decimal
    """computed - bank: 0 when the account is reconciled."""


class ImportBatchOut(BaseModel):
    id: UUID
    format: str
    file_name: str
    created_at: datetime
    imported_count: int
    reconciled_count: int
    """Manual entries the rows took over instead of adding them twice (F-TX-8)."""
    duplicate_count: int
    skipped_count: int
    """Rows dated before the account's opening date."""
    error_count: int
    period: Period | None
    rolled_back_at: datetime | None
    balance_check: BalanceCheckOut | None = None

    @classmethod
    def of(cls, batch: ImportBatch, check: service.BalanceCheck | None = None) -> "ImportBatchOut":
        period = (
            Period(start=batch.period_start, end=batch.period_end)
            if batch.period_start and batch.period_end
            else None
        )
        return cls(
            id=batch.id,
            format=batch.format_key,
            file_name=batch.file_name,
            created_at=batch.created_at,
            imported_count=batch.imported_count,
            reconciled_count=batch.reconciled_count,
            duplicate_count=batch.duplicate_count,
            skipped_count=batch.skipped_count,
            error_count=batch.error_count,
            period=period,
            rolled_back_at=batch.rolled_back_at,
            balance_check=BalanceCheckOut(
                on=check.on, bank=check.bank, computed=check.computed, difference=check.difference
            )
            if check
            else None,
        )


def _account(db: Db, user: User, account_id: UUID) -> Account:
    account = account_service.find_visible_account(db, user, account_id)
    if account is None:
        raise NOT_FOUND
    return account


def _read(file: UploadFile) -> bytes:
    data = file.file.read(service.MAX_FILE_BYTES + 1)
    if len(data) > service.MAX_FILE_BYTES:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "file too large (2 MB at most)")
    return data


def _refused(values: list[str] | None) -> set[tuple[int, UUID]]:
    pairs = set()
    for value in values or []:
        line, _, entry = value.partition(":")
        try:
            pairs.add((int(line), UUID(entry)))
        except ValueError:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                f"invalid refused match {value!r}, expected '<row line>:<entry id>'",
            ) from None
    return pairs


def _rejected(exc: service.ImportRejectedError) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc))


@router.post("/accounts/{account_id}/imports/preview")
def preview_import(
    account_id: UUID, file: Upload, user_session: CurrentSession, db: Db, refused: Refused = None
) -> ImportPreview:
    """Parse the file and classify every row; nothing is stored."""
    account = _account(db, user_session.user, account_id)
    try:
        analysis = service.analyse(db, account, _read(file), refused=_refused(refused))
    except service.ImportRejectedError as exc:
        raise _rejected(exc) from None
    statement = analysis.statement
    return ImportPreview(
        format=analysis.bank_format.key,
        format_label=analysis.bank_format.label,
        period=Period(start=statement.period[0], end=statement.period[1])
        if statement.period
        else None,
        bank_balance=BankBalance(on=statement.balance.on, amount=statement.balance.amount)
        if statement.balance
        else None,
        counts=PreviewCounts(
            new=analysis.count(service.RowStatus.NEW),
            already_entered=analysis.count(service.RowStatus.ALREADY_ENTERED),
            duplicate=analysis.count(service.RowStatus.DUPLICATE),
            before_opening=analysis.count(service.RowStatus.BEFORE_OPENING),
            error=len(statement.errors),
        ),
        rows=[
            PreviewRow(
                line=r.line,
                booked_on=r.booked_on,
                label=r.label,
                amount=r.amount,
                status=s,
                entry=EnteredOut.of(e) if (e := analysis.entries.get(r.line)) else None,
            )
            for r, s, _ in analysis.rows
        ],
        errors=[RowErrorOut(line=e.line, message=e.message) for e in statement.errors],
        already_imported_at=analysis.already_imported_at,
        unmatched_entries=[EnteredOut.of(e) for e in analysis.unmatched],
    )


@router.post("/accounts/{account_id}/imports", status_code=status.HTTP_201_CREATED)
def create_import(
    account_id: UUID,
    file: Upload,
    user_session: CurrentSession,
    db: Db,
    now: Now,
    refused: Refused = None,
) -> ImportBatchOut:
    """Store the file's new rows; a row matching a manual entry takes it over (F-TX-8). Rows
    already stored are skipped, so this is safe to repeat."""
    account = _account(db, user_session.user, account_id)
    try:
        batch, check = service.commit(
            db,
            account,
            user_session.user,
            file_name=file.filename or "statement.csv",
            data=_read(file),
            now=now,
            refused=_refused(refused),
        )
    except service.ImportRejectedError as exc:
        raise _rejected(exc) from None
    audit.record(
        db,
        user_session.user,
        AuditAction.IMPORTED,
        now,
        accounts=[account],
        file=batch.file_name,
        added=batch.imported_count,
    )
    return ImportBatchOut.of(batch, check)


@router.get("/accounts/{account_id}/imports")
def list_imports(account_id: UUID, user_session: CurrentSession, db: Db) -> list[ImportBatchOut]:
    account = _account(db, user_session.user, account_id)
    return [ImportBatchOut.of(b) for b in service.batches(db, account)]


@router.delete("/imports/{batch_id}", status_code=status.HTTP_204_NO_CONTENT)
def rollback_import(batch_id: UUID, user_session: CurrentSession, db: Db, now: Now) -> None:
    """Delete the transactions this import added and give back the manual entries it took over.
    The import stays listed as rolled back."""
    batch = db.get(ImportBatch, batch_id)
    visible = batch and account_service.find_visible_account(
        db, user_session.user, batch.account_id
    )
    if batch is None or not visible or batch.rolled_back_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no import to roll back with this id")
    service.rollback(db, batch, now)
    audit.record(
        db,
        user_session.user,
        AuditAction.IMPORT_ROLLED_BACK,
        now,
        accounts=[visible],
        file=batch.file_name,
    )
