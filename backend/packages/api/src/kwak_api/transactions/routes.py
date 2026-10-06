from datetime import date
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from kwak_core.money import require_cents
from pydantic import AfterValidator, BaseModel

from kwak_api.auth.routes import CurrentSession, Db
from kwak_api.models import Account, Transaction
from kwak_api.services import accounts as account_service
from kwak_api.services import transactions as service

router = APIRouter(prefix="/api", tags=["transactions"])

Cents = Annotated[Decimal, AfterValidator(require_cents)]
NOT_FOUND = HTTPException(status.HTTP_404_NOT_FOUND, "transaction not found")


class TransactionOut(BaseModel):
    id: UUID
    account_id: UUID
    account_name: str
    booked_on: date
    amount: Decimal
    label: str
    source: Literal["import", "manual"]
    """Imported transactions are read-only: they mirror the bank statement."""

    @classmethod
    def of(cls, transaction: Transaction, account: Account) -> "TransactionOut":
        return cls(
            id=transaction.id,
            account_id=account.id,
            account_name=account.name,
            booked_on=transaction.booked_on,
            amount=transaction.amount,
            label=transaction.label_raw,
            source="import" if transaction.fingerprint else "manual",
        )


class TransactionPage(BaseModel):
    items: list[TransactionOut]
    total: int


class TransactionIn(BaseModel):
    account_id: UUID
    booked_on: date
    amount: Cents
    """Negative = outflow, as a string with at most 2 decimals: "-12.50"."""
    label: str


class TransactionPatch(BaseModel):
    booked_on: date | None = None
    amount: Cents | None = None
    label: str | None = None


def _unprocessable(exc: ValueError) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc))


def _conflict(exc: service.ImportedTransactionError) -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, str(exc))


@router.get("/transactions")
def list_transactions(
    user_session: CurrentSession,
    db: Db,
    account_id: UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    q: Annotated[str | None, Query(max_length=100, description="Words in the label")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> TransactionPage:
    filters = service.TransactionFilter(account_id, date_from, date_to, q)
    rows, total = service.search(db, user_session.user, filters, limit=limit, offset=offset)
    return TransactionPage(items=[TransactionOut.of(t, a) for t, a in rows], total=total)


@router.post("/transactions", status_code=status.HTTP_201_CREATED)
def create_transaction(body: TransactionIn, user_session: CurrentSession, db: Db) -> TransactionOut:
    account = account_service.find_visible_account(db, user_session.user, body.account_id)
    if account is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "account not found")
    try:
        transaction = service.create(
            db, account, booked_on=body.booked_on, amount=body.amount, label=body.label
        )
    except ValueError as exc:
        raise _unprocessable(exc) from None
    return TransactionOut.of(transaction, account)


@router.patch("/transactions/{transaction_id}")
def update_transaction(
    transaction_id: UUID, body: TransactionPatch, user_session: CurrentSession, db: Db
) -> TransactionOut:
    found = service.find_visible(db, user_session.user, transaction_id)
    if found is None:
        raise NOT_FOUND
    transaction, account = found
    try:
        service.update(
            db, transaction, account, booked_on=body.booked_on, amount=body.amount, label=body.label
        )
    except service.ImportedTransactionError as exc:
        raise _conflict(exc) from None
    except ValueError as exc:
        raise _unprocessable(exc) from None
    return TransactionOut.of(transaction, account)


@router.delete("/transactions/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transaction(transaction_id: UUID, user_session: CurrentSession, db: Db) -> None:
    found = service.find_visible(db, user_session.user, transaction_id)
    if found is None:
        raise NOT_FOUND
    try:
        service.delete(db, found[0])
    except service.ImportedTransactionError as exc:
        raise _conflict(exc) from None
