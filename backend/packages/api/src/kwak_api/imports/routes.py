from datetime import date, datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from pydantic import BaseModel

from kwak_api.auth.routes import CurrentSession, Db, Now
from kwak_api.models import Account, ImportBatch, User
from kwak_api.services import accounts as account_service
from kwak_api.services import imports as service

router = APIRouter(prefix="/api", tags=["imports"])

Upload = Annotated[UploadFile, File(description="Bank export (CSV)")]
NOT_FOUND = HTTPException(status.HTTP_404_NOT_FOUND, "account not found")


class Period(BaseModel):
    start: date
    end: date


class BankBalance(BaseModel):
    on: date
    amount: Decimal


class PreviewRow(BaseModel):
    line: int
    booked_on: date
    label: str
    amount: Decimal
    status: service.RowStatus


class RowErrorOut(BaseModel):
    line: int
    """0 when the problem concerns the whole file."""
    message: str


class PreviewCounts(BaseModel):
    new: int
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


def _rejected(exc: service.ImportRejectedError) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc))


@router.post("/accounts/{account_id}/imports/preview")
def preview_import(
    account_id: UUID, file: Upload, user_session: CurrentSession, db: Db
) -> ImportPreview:
    """Parse the file and classify every row; nothing is stored."""
    account = _account(db, user_session.user, account_id)
    try:
        analysis = service.analyse(db, account, _read(file))
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
            duplicate=analysis.count(service.RowStatus.DUPLICATE),
            before_opening=analysis.count(service.RowStatus.BEFORE_OPENING),
            error=len(statement.errors),
        ),
        rows=[
            PreviewRow(line=r.line, booked_on=r.booked_on, label=r.label, amount=r.amount, status=s)
            for r, s, _ in analysis.rows
        ],
        errors=[RowErrorOut(line=e.line, message=e.message) for e in statement.errors],
        already_imported_at=analysis.already_imported_at,
    )


@router.post("/accounts/{account_id}/imports", status_code=status.HTTP_201_CREATED)
def create_import(
    account_id: UUID, file: Upload, user_session: CurrentSession, db: Db, now: Now
) -> ImportBatchOut:
    """Store the file's new rows. Rows already stored are skipped, so this is safe to repeat."""
    account = _account(db, user_session.user, account_id)
    try:
        batch, check = service.commit(
            db,
            account,
            user_session.user,
            file_name=file.filename or "statement.csv",
            data=_read(file),
            now=now,
        )
    except service.ImportRejectedError as exc:
        raise _rejected(exc) from None
    return ImportBatchOut.of(batch, check)


@router.get("/accounts/{account_id}/imports")
def list_imports(account_id: UUID, user_session: CurrentSession, db: Db) -> list[ImportBatchOut]:
    account = _account(db, user_session.user, account_id)
    return [ImportBatchOut.of(b) for b in service.batches(db, account)]


@router.delete("/imports/{batch_id}", status_code=status.HTTP_204_NO_CONTENT)
def rollback_import(batch_id: UUID, user_session: CurrentSession, db: Db, now: Now) -> None:
    """Delete the transactions this import added. The import stays listed as rolled back."""
    batch = db.get(ImportBatch, batch_id)
    visible = batch and account_service.find_visible_account(
        db, user_session.user, batch.account_id
    )
    if batch is None or not visible or batch.rolled_back_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no import to roll back with this id")
    service.rollback(db, batch, now)
