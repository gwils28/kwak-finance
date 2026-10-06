from datetime import date
from decimal import Decimal
from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from kwak_core.accounts import AccountType, Visibility
from kwak_core.money import require_cents
from pydantic import AfterValidator, BaseModel, StringConstraints

from kwak_api.auth.routes import CurrentSession, Db
from kwak_api.models import Account
from kwak_api.services import accounts as service

router = APIRouter(prefix="/api", tags=["accounts"])

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Cents = Annotated[Decimal, AfterValidator(require_cents)]
NOT_FOUND = HTTPException(status.HTTP_404_NOT_FOUND, "account not found")


class AccountIn(BaseModel):
    name: Name
    institution_name: Name
    type: AccountType
    visibility: Visibility
    opening_balance: Cents
    """Balance on opening_date, as a string with at most 2 decimals: "1234.56"."""
    opening_date: date


class AccountPatch(BaseModel):
    """Only the fields present are changed. `closed_on: null` reopens the account."""

    name: Name | None = None
    institution_name: Name | None = None
    type: AccountType | None = None
    visibility: Visibility | None = None
    opening_balance: Cents | None = None
    opening_date: date | None = None
    closed_on: date | None = None


class AccountOut(BaseModel):
    id: UUID
    name: str
    institution: str
    type: AccountType
    visibility: Visibility
    owner_id: UUID
    owner_name: str
    opening_balance: Decimal
    opening_date: date
    closed_on: date | None

    @classmethod
    def of(cls, account: Account) -> "AccountOut":
        return cls(
            id=account.id,
            name=account.name,
            institution=account.institution.name,
            type=account.type,
            visibility=account.visibility,
            owner_id=account.owner_id,
            owner_name=account.owner.display_name,
            opening_balance=account.opening_balance,
            opening_date=account.opening_date,
            closed_on=account.closed_on,
        )


def _unprocessable(exc: ValueError) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc))


DUPLICATE = HTTPException(
    status.HTTP_409_CONFLICT, "this institution already has an account with this name"
)


@router.get("/accounts")
def list_accounts(
    user_session: CurrentSession, db: Db, include_closed: Annotated[bool, Query()] = False
) -> list[AccountOut]:
    accounts = service.visible_accounts(db, user_session.user, include_closed=include_closed)
    return [AccountOut.of(a) for a in accounts]


@router.post("/accounts", status_code=status.HTTP_201_CREATED)
def create_account(body: AccountIn, user_session: CurrentSession, db: Db) -> AccountOut:
    try:
        account = service.create_account(
            db, user_session.user, service.AccountInput(**body.model_dump())
        )
    except ValueError as exc:
        raise _unprocessable(exc) from None
    except service.DuplicateAccountError:
        raise DUPLICATE from None
    return AccountOut.of(account)


@router.patch("/accounts/{account_id}")
def update_account(
    account_id: UUID, body: AccountPatch, user_session: CurrentSession, db: Db
) -> AccountOut:
    account = service.find_visible_account(db, user_session.user, account_id)
    if account is None:
        raise NOT_FOUND
    changes = cast(service.AccountChanges, body.model_dump(exclude_unset=True))
    for required in (
        "name",
        "institution_name",
        "type",
        "visibility",
        "opening_balance",
        "opening_date",
    ):
        if changes.get(required, ...) is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"{required} cannot be null")
    try:
        service.update_account(db, user_session.user, account, changes)
    except PermissionError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from None
    except ValueError as exc:
        raise _unprocessable(exc) from None
    except service.DuplicateAccountError:
        raise DUPLICATE from None
    return AccountOut.of(account)


@router.get("/institutions")
def list_institutions(user_session: CurrentSession, db: Db) -> list[str]:
    """Names already used in the household, for autocompletion."""
    return service.institution_names(db, user_session.user.household_id)
