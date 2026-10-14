from datetime import date
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from kwak_core.audit import AuditAction
from kwak_core.budget import Month
from kwak_core.money import require_cents
from pydantic import AfterValidator, BaseModel, Field

from kwak_api.auth.routes import CurrentSession, Db, Now
from kwak_api.models import Account, Category, Transaction
from kwak_api.services import accounts as account_service
from kwak_api.services import audit
from kwak_api.services import budget_month as budget_month_service
from kwak_api.services import categories as category_service
from kwak_api.services import transactions as service
from kwak_api.services import transfers as transfer_service

router = APIRouter(prefix="/api", tags=["transactions"])

Cents = Annotated[Decimal, AfterValidator(require_cents)]
NOT_FOUND = HTTPException(status.HTTP_404_NOT_FOUND, "transaction not found")


def _month(text: str | None) -> str | None:
    if text is not None:
        Month.parse(text)  # ValueError: a validation error
    return text


class PartOut(BaseModel):
    category_id: UUID | None
    """null: to categorise (its category was deleted)."""
    category_name: str | None
    amount: Decimal


class TransactionOut(BaseModel):
    id: UUID
    account_id: UUID
    account_name: str
    booked_on: date
    amount: Decimal
    label: str
    source: Literal["import", "manual"]
    """Imported transactions mirror the bank: only their category can change."""
    bank_label: str | None = None
    """The bank's label of a manual entry reconciled with a statement row (F-TX-8)."""
    category_id: UUID | None
    category_name: str | None
    transfer_group_id: UUID | None
    """Set when this is one side of a transfer between own accounts."""
    transfer_account_name: str | None
    """The account on the other side of the transfer."""
    budget_month: str
    """YYYY-MM: the month it counts in for the budget (F-TX-7), by default its booking month."""
    budget_month_set: bool
    """The budget month was set by hand on this transaction."""
    parts: list[PartOut]
    """Set when the transaction is split (F-TX-4): its categories, adding up to its amount.
    `category_id` is then null."""
    note: str | None

    @classmethod
    def of(
        cls,
        transaction: Transaction,
        account: Account,
        categories: dict[UUID, Category],
        counterparts: dict[UUID, str] | None = None,
    ) -> "TransactionOut":
        category = categories.get(transaction.category_id) if transaction.category_id else None
        return cls(
            id=transaction.id,
            account_id=account.id,
            account_name=account.name,
            booked_on=transaction.booked_on,
            amount=transaction.amount,
            label=transaction.label_raw,
            source="import" if transaction.fingerprint else "manual",
            bank_label=transaction.bank_label,
            category_id=category.id if category else None,
            category_name=category.name if category else None,
            transfer_group_id=transaction.transfer_group_id,
            transfer_account_name=(counterparts or {}).get(transaction.id),
            budget_month=str(budget_month_service.month_of(transaction, categories)),
            budget_month_set=transaction.budget_month is not None,
            parts=[
                PartOut(
                    category_id=p.category_id,
                    category_name=categories[p.category_id].name
                    if p.category_id in categories
                    else None,
                    amount=p.amount,
                )
                for p in transaction.parts
            ],
            note=transaction.note,
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
    category_id: UUID | None = None
    """Its category; by default the rules choose (F-CAT-2)."""
    note: str | None = Field(default=None, max_length=500)
    """Free text, searched with the label (F-TX-4)."""


class TransactionPatch(BaseModel):
    """Only the fields present change. `category_id: null` makes it "to categorise" again."""

    booked_on: date | None = None
    amount: Cents | None = None
    label: str | None = None
    category_id: UUID | None = None
    budget_month: Annotated[str | None, AfterValidator(_month)] = None
    """YYYY-MM, at most one month from the date: the month it counts in for the budget.
    null: back to its booking month, or the next one by its category (F-CAT-5)."""
    note: str | None = Field(default=None, max_length=500)
    """Free text, searched with the label; null or empty removes it. Imported rows too."""


class PartIn(BaseModel):
    category_id: UUID | None
    amount: Cents
    """Of the transaction's sign: "-60.00" for an outflow."""


MAX_PARTS = 20


class SplitIn(BaseModel):
    parts: list[PartIn] = Field(min_length=1, max_length=MAX_PARTS - 1)
    """Every part but the last: 20 parts at most, the rest included."""
    rest_category_id: UUID | None
    """The last part's category: it takes what the others leave."""


class Categorise(BaseModel):
    transaction_ids: list[UUID]
    category_id: UUID | None
    """null = "to categorise"."""


class Categorised(BaseModel):
    updated: int
    """Transactions changed; ids the user cannot see are skipped."""


def _categories(db: Db, household_id: UUID) -> dict[UUID, Category]:
    return {c.id: c for c in category_service.tree(db, household_id)}


def _category(db: Db, household_id: UUID, category_id: UUID | None) -> Category | None:
    if category_id is None:
        return None
    category = category_service.find(db, household_id, category_id)
    if category is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "unknown category")
    return category


def _unprocessable(exc: ValueError) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc))


HIDDEN_SIDE = HTTPException(
    status.HTTP_409_CONFLICT, "the other side of this transfer is on an account you cannot see"
)


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
    category_id: UUID | None = None,
    uncategorised: Annotated[bool, Query(description="Only transactions to categorise")] = False,
    budget_month: Annotated[
        str | None,
        Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$", description="YYYY-MM: counted in this month"),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> TransactionPage:
    filters = service.TransactionFilter(
        account_id,
        date_from,
        date_to,
        q,
        category_id,
        uncategorised,
        Month.parse(budget_month) if budget_month else None,
    )
    rows, total = service.search(db, user_session.user, filters, limit=limit, offset=offset)
    categories = _categories(db, user_session.user.household_id)
    others = transfer_service.counterparts(db, user_session.user, [t for t, _ in rows])
    return TransactionPage(
        items=[TransactionOut.of(t, a, categories, others) for t, a in rows], total=total
    )


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
    if body.category_id is not None:
        category = _category(db, user_session.user.household_id, body.category_id)
        service.set_category(db, transaction, category)
    if body.note:
        service.set_note(db, transaction, body.note)
    return TransactionOut.of(transaction, account, _categories(db, user_session.user.household_id))


@router.patch("/transactions/{transaction_id}")
def update_transaction(
    transaction_id: UUID, body: TransactionPatch, user_session: CurrentSession, db: Db
) -> TransactionOut:
    found = service.find_visible(db, user_session.user, transaction_id)
    if found is None:
        raise NOT_FOUND
    transaction, account = found
    household_id = user_session.user.household_id
    try:
        service.update(
            db,
            user_session.user,
            transaction,
            account,
            booked_on=body.booked_on,
            amount=body.amount,
            label=body.label,
        )
    except service.ImportedTransactionError as exc:
        raise _conflict(exc) from None
    except service.HiddenSideError:
        raise HIDDEN_SIDE from None
    except ValueError as exc:
        raise _unprocessable(exc) from None
    if "note" in body.model_fields_set:
        service.set_note(db, transaction, body.note)
    if "category_id" in body.model_fields_set:
        try:
            service.set_category(db, transaction, _category(db, household_id, body.category_id))
        except service.TransferCategoryError:
            raise HTTPException(
                status.HTTP_409_CONFLICT, "a transfer has no category: unlink it first"
            ) from None
        except service.SplitCategoryError:
            raise HTTPException(
                status.HTTP_409_CONFLICT, "a split transaction's categories are its parts'"
            ) from None
    if "budget_month" in body.model_fields_set:
        month = Month.parse(body.budget_month) if body.budget_month else None
        try:
            service.set_budget_month(db, transaction, month)
        except service.TransferMonthError:
            raise HTTPException(
                status.HTTP_409_CONFLICT, "a transfer counts in its booking month"
            ) from None
        except ValueError as exc:
            raise _unprocessable(exc) from None
    return TransactionOut.of(transaction, account, _categories(db, household_id))


@router.put("/transactions/{transaction_id}/split")
def split_transaction(
    transaction_id: UUID, body: SplitIn, user_session: CurrentSession, db: Db
) -> TransactionOut:
    """Spread a transaction over categories (F-TX-4): the parts given, then the rest."""
    found = service.find_visible(db, user_session.user, transaction_id)
    if found is None:
        raise NOT_FOUND
    transaction, account = found
    household_id = user_session.user.household_id
    given = [(_category(db, household_id, p.category_id), p.amount) for p in body.parts]
    try:
        service.split(db, transaction, given, _category(db, household_id, body.rest_category_id))
    except service.TransferSplitError:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "a transfer cannot be split: unlink it first"
        ) from None
    except ValueError as exc:
        raise _unprocessable(exc) from None
    return TransactionOut.of(transaction, account, _categories(db, household_id))


@router.delete("/transactions/{transaction_id}/split")
def unsplit_transaction(
    transaction_id: UUID, user_session: CurrentSession, db: Db
) -> TransactionOut:
    """Back to a single category, to categorise until one is chosen."""
    found = service.find_visible(db, user_session.user, transaction_id)
    if found is None:
        raise NOT_FOUND
    transaction, account = found
    service.unsplit(db, transaction)
    return TransactionOut.of(transaction, account, _categories(db, user_session.user.household_id))


@router.post("/transactions/categorise")
def categorise_transactions(body: Categorise, user_session: CurrentSession, db: Db) -> Categorised:
    """Bulk categorisation (F-CAT-3)."""
    category = _category(db, user_session.user.household_id, body.category_id)
    updated = service.categorise(db, user_session.user, body.transaction_ids, category)
    return Categorised(updated=updated)


@router.delete("/transactions/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transaction(
    transaction_id: UUID, user_session: CurrentSession, db: Db, now: Now
) -> None:
    found = service.find_visible(db, user_session.user, transaction_id)
    if found is None:
        raise NOT_FOUND
    transaction, account = found
    label, amount, booked_on = transaction.label_raw, transaction.amount, transaction.booked_on
    try:
        service.delete(db, user_session.user, transaction)
    except service.ImportedTransactionError as exc:
        raise _conflict(exc) from None
    except service.HiddenSideError:
        raise HIDDEN_SIDE from None
    audit.record(
        db,
        user_session.user,
        AuditAction.TRANSACTION_DELETED,
        now,
        accounts=[account],
        label=label,
        amount=amount,
        date=booked_on.isoformat(),
    )
