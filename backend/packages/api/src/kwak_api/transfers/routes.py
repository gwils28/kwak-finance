from datetime import date
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from kwak_core.money import require_cents
from pydantic import AfterValidator, BaseModel

from kwak_api.auth.routes import CurrentSession, Db
from kwak_api.models import Transaction
from kwak_api.services import transfers as service
from kwak_api.services.accounts import find_visible_account, visible_accounts

router = APIRouter(prefix="/api/transfers", tags=["transfers"])

Cents = Annotated[Decimal, AfterValidator(require_cents)]


class TransferSide(BaseModel):
    id: UUID
    account_id: UUID
    account_name: str
    booked_on: date
    amount: Decimal
    label: str


class TransferSuggestion(BaseModel):
    outflow: TransferSide
    inflow: TransferSide


class TransferIn(BaseModel):
    outflow_id: UUID
    inflow_id: UUID


class TransferOut(BaseModel):
    group_id: UUID


class TransferEntryIn(BaseModel):
    source_account_id: UUID
    destination_account_id: UUID
    booked_on: date
    amount: Cents
    """Positive: what leaves the source account and reaches the destination."""
    outflow_label: str
    """The source side's label, e.g. "Transfer to Joint account"."""
    inflow_label: str
    """The destination side's label, e.g. "Transfer from My account"."""


class TransferEntryOut(BaseModel):
    group_id: UUID
    outflow: TransferSide
    inflow: TransferSide


class Linked(BaseModel):
    linked: int


class AcceptSuggestions(BaseModel):
    pass


def _side(t: Transaction, names: dict[UUID, str]) -> TransferSide:
    return TransferSide(
        id=t.id,
        account_id=t.account_id,
        account_name=names.get(t.account_id, ""),
        booked_on=t.booked_on,
        amount=t.amount,
        label=t.label_raw,
    )


@router.get("/suggestions")
def transfer_suggestions(user_session: CurrentSession, db: Db) -> list[TransferSuggestion]:
    """Pairs that look like a transfer between two of your accounts (same amount, 3 days)."""
    names = {a.id: a.name for a in visible_accounts(db, user_session.user, include_closed=True)}
    return [
        TransferSuggestion(outflow=_side(out, names), inflow=_side(inn, names))
        for out, inn in service.suggestions(db, user_session.user)
    ]


@router.post("", status_code=status.HTTP_201_CREATED)
def link_transfer(body: TransferIn, user_session: CurrentSession, db: Db) -> TransferOut:
    """Mark two transactions as one transfer: no longer spending, income or to categorise."""
    outflow = service.find(db, user_session.user, body.outflow_id)
    inflow = service.find(db, user_session.user, body.inflow_id)
    if outflow is None or inflow is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "transaction not found")
    try:
        group = service.link(db, outflow, inflow)
    except service.TransferError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None
    except service.AlreadyLinkedError:
        raise HTTPException(status.HTTP_409_CONFLICT, "already part of a transfer") from None
    return TransferOut(group_id=group)


@router.post("/entries", status_code=status.HTTP_201_CREATED)
def enter_transfer(body: TransferEntryIn, user_session: CurrentSession, db: Db) -> TransferEntryOut:
    """Enter a transfer by hand: both sides, already linked (F-TX-9)."""
    user = user_session.user
    source = find_visible_account(db, user, body.source_account_id)
    destination = find_visible_account(db, user, body.destination_account_id)
    if source is None or destination is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "account not found")
    try:
        group, outflow, inflow = service.enter(
            db,
            source,
            destination,
            booked_on=body.booked_on,
            amount=body.amount,
            outflow_label=body.outflow_label,
            inflow_label=body.inflow_label,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None
    names = {source.id: source.name, destination.id: destination.name}
    return TransferEntryOut(
        group_id=group,
        outflow=_side(outflow, names),
        inflow=_side(inflow, names),
    )


@router.get("/candidates/{transaction_id}")
def transfer_candidates(
    transaction_id: UUID, user_session: CurrentSession, db: Db
) -> list[TransferSide]:
    """What this transaction could be linked to: the opposite amount on another of your
    accounts, within 31 days, closest first ("Link to…")."""
    transaction = service.find(db, user_session.user, transaction_id)
    if transaction is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "transaction not found")
    try:
        found = service.candidates(db, user_session.user, transaction)
    except service.AlreadyLinkedError:
        raise HTTPException(status.HTTP_409_CONFLICT, "already part of a transfer") from None
    names = {a.id: a.name for a in visible_accounts(db, user_session.user, include_closed=True)}
    return [_side(t, names) for t in found]


@router.post("/accept-suggestions")
def accept_transfer_suggestions(
    body: AcceptSuggestions, user_session: CurrentSession, db: Db
) -> Linked:
    """Link every current suggestion."""
    return Linked(linked=service.accept_all(db, user_session.user))


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
def unlink_transfer(group_id: UUID, user_session: CurrentSession, db: Db) -> None:
    if not service.unlink(db, user_session.user, group_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "transfer not found")
