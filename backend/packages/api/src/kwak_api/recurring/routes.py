from datetime import date
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from kwak_core.accounts import Scope
from kwak_core.money import require_cents
from kwak_core.recurring import Frequency, Occurrence, OccurrenceStatus, RecurringError, entry_date
from pydantic import AfterValidator, BaseModel, Field

from kwak_api.auth.routes import CurrentSession, Db, Now
from kwak_api.models import Category, RecurringItem, User
from kwak_api.services import accounts as account_service
from kwak_api.services import categories as category_service
from kwak_api.services import recurring as service

router = APIRouter(prefix="/api/recurring", tags=["recurring"])

Cents = Annotated[Decimal, AfterValidator(require_cents)]
NOT_FOUND = HTTPException(status.HTTP_404_NOT_FOUND, "recurring item not found")


class RecurringIn(BaseModel):
    account_id: UUID
    category_id: UUID | None = None
    label: str = Field(max_length=100)
    """Matched anywhere in the transactions' labels, ignoring case, spacing and accents."""
    amount: Cents
    """Signed, as a transaction's: -950.00 for rent. For an estimated item, the amount expected
    until it has occurrences to average."""
    frequency: Frequency
    day: int
    """0 (Monday) to 6 for a weekly item, else the day of the month (1-31)."""
    start_on: date
    """Quarterly and yearly items repeat from this date's month."""
    end_on: date | None = None
    estimated: bool = False
    """The amount varies: expect the average of the last 3 occurrences."""
    paused: bool = False


class RecurringPatch(BaseModel):
    """Only the fields present change."""

    account_id: UUID | None = None
    category_id: UUID | None = None
    label: str | None = Field(default=None, max_length=100)
    amount: Cents | None = None
    frequency: Frequency | None = None
    day: int | None = None
    start_on: date | None = None
    end_on: date | None = None
    estimated: bool | None = None
    paused: bool | None = None


class OccurrenceOut(BaseModel):
    item_id: UUID
    due: date
    expected: Decimal
    """The item's amount, or the average of its last 3 occurrences when estimated."""
    status: OccurrenceStatus
    """Upcoming until 5 days after `due`, then late while no transaction fulfils it."""
    transaction_id: UUID | None
    """The transaction that fulfilled it."""
    enter_on: date
    """The date "Enter it" proposes: the expected one, or today if it is still to come."""

    @classmethod
    def of(cls, occurrence: Occurrence, today: date) -> "OccurrenceOut":
        return cls(
            item_id=occurrence.item_id,
            due=occurrence.due,
            expected=occurrence.expected,
            status=occurrence.status,
            transaction_id=occurrence.transaction_id,
            enter_on=entry_date(occurrence.due, today),
        )


class RecurringOut(BaseModel):
    id: UUID
    account_id: UUID
    account_name: str
    category_id: UUID | None
    category_name: str | None
    label: str
    amount: Decimal
    frequency: Frequency
    day: int
    start_on: date
    end_on: date | None
    estimated: bool
    paused: bool
    next: OccurrenceOut | None
    """The first upcoming occurrence; null when paused or ended."""
    recent: list[OccurrenceOut]
    """The last 12 occurrences due by today, newest first."""

    @classmethod
    def of(cls, view: service.ItemView, names: dict[UUID, str], today: date) -> "RecurringOut":
        item = view.item
        return cls(
            id=item.id,
            account_id=item.account_id,
            account_name=item.account.name,
            category_id=item.category_id,
            category_name=names.get(item.category_id) if item.category_id else None,
            label=item.label,
            amount=item.amount,
            frequency=item.frequency,
            day=item.day,
            start_on=item.start_on,
            end_on=item.end_on,
            estimated=item.estimated,
            paused=item.paused,
            next=OccurrenceOut.of(view.next, today) if view.next else None,
            recent=[OccurrenceOut.of(o, today) for o in view.recent],
        )


class UpcomingOccurrence(OccurrenceOut):
    label: str
    account_id: UUID
    account_name: str
    category_id: UUID | None
    estimated: bool


class UpcomingOut(BaseModel):
    occurrences: list[UpcomingOccurrence]
    """Late ones first (due in the last 31 days), then the upcoming ones to the month's end."""
    current_balance: Decimal
    """Of the scope's cash accounts."""
    projected_balance: Decimal
    """The current balance plus every occurrence listed (F-REC-4)."""


class SuggestionOut(BaseModel):
    account_id: UUID
    account_name: str
    label: str
    """The series' label, in capitals and without accents."""
    amount: Decimal
    """The last amount, or the average of the last 3 when estimated."""
    estimated: bool
    frequency: Frequency
    day: int
    start_on: date
    """The first transaction of the series."""
    category_id: UUID | None
    """The category most of its transactions have."""
    count: int


class Dismiss(BaseModel):
    account_id: UUID
    label: str


def _names(db: Db, household_id: UUID) -> dict[UUID, str]:
    return {c.id: c.name for c in category_service.tree(db, household_id)}


def _category(db: Db, user: User, category_id: UUID | None) -> Category | None:
    if category_id is None:
        return None
    category = category_service.find(db, user.household_id, category_id)
    if category is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "unknown category")
    return category


def _fields(db: Db, user: User, body: RecurringIn) -> service.Fields:
    account = account_service.find_visible_account(db, user, body.account_id)
    if account is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "unknown account")
    return service.Fields(
        account=account,
        category=_category(db, user, body.category_id),
        label=body.label,
        amount=body.amount,
        frequency=body.frequency,
        day=body.day,
        start_on=body.start_on,
        end_on=body.end_on,
        estimated=body.estimated,
        paused=body.paused,
    )


def _invalid(exc: RecurringError) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc))


def _out(db: Db, user: User, item_id: UUID, today: date) -> RecurringOut:
    view = next(v for v in service.overview(db, user, today) if v.item.id == item_id)
    return RecurringOut.of(view, _names(db, user.household_id), today)


def _find(db: Db, user: User, item_id: UUID) -> RecurringItem:
    item = service.find(db, user, item_id)
    if item is None:
        raise NOT_FOUND
    return item


@router.get("")
def list_recurring(user_session: CurrentSession, db: Db, now: Now) -> list[RecurringOut]:
    """The items on accounts the user can see, with their next and past occurrences."""
    user = user_session.user
    names = _names(db, user.household_id)
    today = now.date()
    return [RecurringOut.of(v, names, today) for v in service.overview(db, user, today)]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_recurring(
    body: RecurringIn, user_session: CurrentSession, db: Db, now: Now
) -> RecurringOut:
    user = user_session.user
    try:
        item = service.create(db, user, _fields(db, user, body))
    except RecurringError as exc:
        raise _invalid(exc) from None
    return _out(db, user, item.id, now.date())


@router.patch("/{item_id}")
def update_recurring(
    item_id: UUID, body: RecurringPatch, user_session: CurrentSession, db: Db, now: Now
) -> RecurringOut:
    user = user_session.user
    item = _find(db, user, item_id)
    given = body.model_fields_set
    merged = RecurringIn(
        account_id=body.account_id or item.account_id,
        category_id=body.category_id if "category_id" in given else item.category_id,
        label=body.label if body.label is not None else item.label,
        amount=body.amount if body.amount is not None else item.amount,
        frequency=body.frequency or item.frequency,
        day=body.day if body.day is not None else item.day,
        start_on=body.start_on or item.start_on,
        end_on=body.end_on if "end_on" in given else item.end_on,
        estimated=body.estimated if body.estimated is not None else item.estimated,
        paused=body.paused if body.paused is not None else item.paused,
    )
    try:
        service.update(db, item, _fields(db, user, merged))
    except RecurringError as exc:
        raise _invalid(exc) from None
    return _out(db, user, item.id, now.date())


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_recurring(item_id: UUID, user_session: CurrentSession, db: Db) -> None:
    """Past transactions stay; only the expectation goes."""
    db.delete(_find(db, user_session.user, item_id))


@router.put("/{item_id}/skips/{due}", status_code=status.HTTP_204_NO_CONTENT)
def skip_occurrence(item_id: UUID, due: date, user_session: CurrentSession, db: Db) -> None:
    """The occurrence due on this date is no longer expected (F-REC-3)."""
    item = _find(db, user_session.user, item_id)
    if not service.is_due(item, due):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, f"the item is not due on {due.isoformat()}"
        )
    service.skip(db, item, due)


@router.delete("/{item_id}/skips/{due}", status_code=status.HTTP_204_NO_CONTENT)
def unskip_occurrence(item_id: UUID, due: date, user_session: CurrentSession, db: Db) -> None:
    service.unskip(db, _find(db, user_session.user, item_id), due)


@router.get("/upcoming")
def upcoming_recurring(
    user_session: CurrentSession, db: Db, now: Now, scope: Scope = Scope.HOUSEHOLD
) -> UpcomingOut:
    """What is still expected this month, and the balance it leads to (F-REC-4)."""
    today = now.date()
    result = service.upcoming(db, user_session.user, scope, today)
    occurrences = []
    for o in result.occurrences:
        item = result.items[o.item_id]
        occurrences.append(
            UpcomingOccurrence(
                **OccurrenceOut.of(o, today).model_dump(),
                label=item.label,
                account_id=item.account_id,
                account_name=item.account.name,
                category_id=item.category_id,
                estimated=item.estimated,
            )
        )
    return UpcomingOut(
        occurrences=occurrences,
        current_balance=result.current_balance,
        projected_balance=result.projected_balance,
    )


@router.get("/suggestions")
def recurring_suggestions(user_session: CurrentSession, db: Db, now: Now) -> list[SuggestionOut]:
    """Regular series of the last 6 months to confirm as items (F-REC-2)."""
    return [
        SuggestionOut(
            account_id=v.account.id,
            account_name=v.account.name,
            label=v.suggestion.label,
            amount=v.suggestion.amount,
            estimated=v.suggestion.estimated,
            frequency=v.suggestion.frequency,
            day=v.suggestion.day,
            start_on=v.start_on,
            category_id=v.category_id,
            count=len(v.suggestion.transaction_ids),
        )
        for v in service.suggestions(db, user_session.user, now.date())
    ]


@router.post("/suggestions/dismiss", status_code=status.HTTP_204_NO_CONTENT)
def dismiss_suggestion(body: Dismiss, user_session: CurrentSession, db: Db) -> None:
    """This series is not suggested again."""
    account = account_service.find_visible_account(db, user_session.user, body.account_id)
    if account is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "unknown account")
    service.dismiss(db, account, body.label)
