"""The spending since v1.0 (§4.2 to 4.6): lines entered by hand, income and fixed expenses.

Amounts are signed as stored: negative is spent or put aside, positive taken back from savings.
"""

import re
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from kwak_core.audit import AuditAction
from kwak_core.budget import Month
from kwak_core.categories import CategoryKind
from kwak_core.fixed import FixedFrequency, FixedStatus
from kwak_core.income import check_income
from kwak_core.labels import remembered_category, suggest
from kwak_core.money import require_cents
from kwak_core.quickline import match_category, parse
from kwak_core.splits import Part
from kwak_core.users import Language
from pydantic import AfterValidator, BaseModel, Field, StringConstraints, model_validator

from kwak_api.auth.routes import CurrentSession, Db, Now
from kwak_api.household.routes import OwnerSession
from kwak_api.models import FixedExpense, SpendingCategory, SpendingLine
from kwak_api.services import audit
from kwak_api.services import spending as service

router = APIRouter(prefix="/api/spending", tags=["spending"])

MONTH = re.compile(r"[0-9]{4}-[0-9]{2}")
YEARS = range(1900, 2201)
NO_CATEGORY = HTTPException(status.HTTP_404_NOT_FOUND, "no such spending category")
NO_LINE = HTTPException(status.HTTP_404_NOT_FOUND, "no such line")
NO_FIXED = HTTPException(status.HTTP_404_NOT_FOUND, "no such fixed expense")
DUPLICATE = HTTPException(status.HTTP_409_CONFLICT, "another category has this name")

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]
Label = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
MonthText = Annotated[str, StringConstraints(max_length=7)]
# What NUMERIC(14, 2) holds, whole cents only.
Signed = Annotated[
    Decimal, Field(gt=Decimal("-1e12"), lt=Decimal("1e12")), AfterValidator(require_cents)
]


def _unprocessable(message: str) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, message)


def _month(text: str) -> Month:
    try:
        month = Month.parse(text) if MONTH.fullmatch(text) else None
    except ValueError:
        month = None
    if month is None or month.year not in YEARS:
        raise _unprocessable(f"invalid month {text!r}, expected YYYY-MM")
    return month


def _language(user_session: CurrentSession) -> Language:
    return user_session.user.language or Language.EN


# Categories (F-CAT-1, 4, 6)


class SpendingCategoryOut(BaseModel):
    id: UUID
    name: str
    kind: CategoryKind
    one_off: bool
    position: int

    @classmethod
    def of(cls, c: SpendingCategory) -> "SpendingCategoryOut":
        return cls(id=c.id, name=c.name, kind=c.kind, one_off=c.one_off, position=c.position)


class SpendingCategoryIn(BaseModel):
    name: Name
    kind: CategoryKind

    @model_validator(mode="after")
    def _spending_kind(self) -> "SpendingCategoryIn":
        if self.kind is CategoryKind.INCOME:
            raise ValueError("a spending category is an expense or a savings one")
        return self


class SpendingCategoryPatch(BaseModel):
    name: Name | None = None
    one_off: bool | None = None


def _category(db: Db, user_session: CurrentSession, category_id: UUID) -> SpendingCategory:
    category = service.find_category(db, user_session.user.household_id, category_id)
    if category is None:
        raise NO_CATEGORY
    return category


@router.get("/categories")
def list_spending_categories(user_session: CurrentSession, db: Db) -> list[SpendingCategoryOut]:
    return [
        SpendingCategoryOut.of(c) for c in service.categories(db, user_session.user.household_id)
    ]


@router.post("/categories", status_code=status.HTTP_201_CREATED)
def create_spending_category(
    body: SpendingCategoryIn, user_session: CurrentSession, db: Db
) -> SpendingCategoryOut:
    try:
        category = service.create_category(db, user_session.user.household_id, body.name, body.kind)
    except service.DuplicateCategoryError:
        raise DUPLICATE from None
    return SpendingCategoryOut.of(category)


@router.patch("/categories/{category_id}")
def update_spending_category(
    category_id: UUID, body: SpendingCategoryPatch, user_session: CurrentSession, db: Db
) -> SpendingCategoryOut:
    category = _category(db, user_session, category_id)
    if body.one_off is not None:
        if category.kind is not CategoryKind.EXPENSE:
            raise _unprocessable("only an expense category can be one-off")
        category.one_off = body.one_off
    if body.name is not None:
        category.name = " ".join(body.name.split())
    try:
        service.flush_unique(db)
    except service.DuplicateCategoryError:
        raise DUPLICATE from None
    return SpendingCategoryOut.of(category)


@router.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_spending_category(
    category_id: UUID,
    user_session: CurrentSession,
    db: Db,
    now: Now,
    move_to: Annotated[
        UUID | None, Query(description="Where its lines and fixed expenses go")
    ] = None,
) -> None:
    category = _category(db, user_session, category_id)
    target = None
    if move_to is not None:
        target = _category(db, user_session, move_to)
        if target.id == category.id or target.kind is not category.kind:
            raise _unprocessable("move them to another category of the same kind")
    name = category.name
    try:
        service.delete_category(db, category, target)
    except service.CategoryInUseError:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "it holds lines or fixed expenses: say where to move them"
        ) from None
    audit.record(
        db,
        user_session.user,
        AuditAction.SPENDING_CATEGORY_DELETED,
        now,
        name=name,
        moved_to=target.name if target else None,
    )


class SpendingRestoreOut(BaseModel):
    added: int


@router.post("/categories/restore")
def restore_spending_categories(user_session: OwnerSession, db: Db, now: Now) -> SpendingRestoreOut:
    """Add back the default categories missing by name."""
    added = service.restore_categories(
        db, user_session.user.household_id, user_session.user.language or Language.EN
    )
    audit.record(db, user_session.user, AuditAction.CATEGORIES_RESTORED, now, count=added)
    return SpendingRestoreOut(added=added)


# Lines (F-LIN, F-ENT-1, 4)


class PartIn(BaseModel):
    category_id: UUID
    amount: Signed


class SplitIn(BaseModel):
    parts: list[PartIn] = Field(min_length=1, max_length=20)
    """Every part but the last."""
    rest_category_id: UUID
    """The last part's category: it takes the rest."""


class LineIn(BaseModel):
    day: date
    label: Label
    amount: Signed
    category_id: UUID | None = None
    split: SplitIn | None = None
    fixed_expense_id: UUID | None = None
    """When confirming an occurrence of this fixed expense (F-FIX-2)."""

    @model_validator(mode="after")
    def _one_category(self) -> "LineIn":
        if (self.category_id is None) == (self.split is None):
            raise ValueError("give a category or a split, not both")
        if self.amount == 0:
            raise ValueError("a line is not zero")
        return self

    def data(self) -> service.LineData:
        if self.split is None:
            return service.LineData(
                self.day, self.label, self.amount, self.category_id, (), self.fixed_expense_id
            )
        given = [Part(p.category_id, p.amount) for p in self.split.parts]
        return service.LineData(
            self.day,
            self.label,
            self.amount,
            self.split.rest_category_id,
            given,
            self.fixed_expense_id,
        )


class PartOut(BaseModel):
    category_id: UUID
    amount: Decimal


class LineOut(BaseModel):
    id: UUID
    day: date
    label: str
    amount: Decimal
    category_id: UUID | None
    """None when split: see the parts."""
    parts: list[PartOut]
    fixed_expense_id: UUID | None
    entered_by: str
    entered_at: datetime

    @classmethod
    def of(cls, line: SpendingLine) -> "LineOut":
        return cls(
            id=line.id,
            day=line.day,
            label=line.label,
            amount=line.amount,
            category_id=line.category_id,
            parts=[PartOut(category_id=p.category_id, amount=p.amount) for p in line.parts],
            fixed_expense_id=line.fixed_expense_id,
            entered_by=line.entered_by.display_name,
            entered_at=line.created_at,
        )


class LastEntryOut(BaseModel):
    id: UUID
    day: date
    entered_at: datetime


class MonthLinesOut(BaseModel):
    month: str
    lines: list[LineOut]
    last_entry: LastEntryOut | None
    """The line entered last in the household, in any month (F-ENT-4)."""


@router.get("/lines")
def month_lines(
    user_session: CurrentSession,
    db: Db,
    month: Annotated[MonthText, Query(description="YYYY-MM")],
) -> MonthLinesOut:
    household = user_session.user.household_id
    wanted = _month(month)
    last = service.last_entry(db, household)
    return MonthLinesOut(
        month=str(wanted),
        lines=[LineOut.of(ln) for ln in service.lines_of_month(db, household, wanted)],
        last_entry=LastEntryOut(id=last.id, day=last.day, entered_at=last.created_at)
        if last
        else None,
    )


@router.post("/lines", status_code=status.HTTP_201_CREATED)
def create_line(body: LineIn, user_session: CurrentSession, db: Db, now: Now) -> LineOut:
    try:
        line = service.create_line(db, user_session.user, body.data(), now)
    except service.LineError as exc:
        raise _unprocessable(str(exc)) from None
    return LineOut.of(line)


def _line(db: Db, user_session: CurrentSession, line_id: UUID) -> SpendingLine:
    line = service.find_line(db, user_session.user.household_id, line_id)
    if line is None:
        raise NO_LINE
    return line


@router.put("/lines/{line_id}")
def replace_line(line_id: UUID, body: LineIn, user_session: CurrentSession, db: Db) -> LineOut:
    try:
        line = service.replace_line(db, _line(db, user_session, line_id), body.data())
    except service.LineError as exc:
        raise _unprocessable(str(exc)) from None
    return LineOut.of(line)


@router.delete("/lines/{line_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_line(line_id: UUID, user_session: CurrentSession, db: Db, now: Now) -> None:
    line = _line(db, user_session, line_id)
    audit.record(
        db,
        user_session.user,
        AuditAction.SPENDING_LINE_DELETED,
        now,
        label=line.label,
        amount=line.amount,
        date=line.day.isoformat(),
    )
    db.delete(line)


# Label memory and quick line (F-ENT-2, 3)


class LabelOut(BaseModel):
    label: str
    category_id: UUID | None
    """The category of the latest line entered with this label."""


@router.get("/labels")
def label_suggestions(
    user_session: CurrentSession,
    db: Db,
    now: Now,
    q: Annotated[str, Query(max_length=100)],
) -> list[LabelOut]:
    uses = service.label_uses(db, user_session.user.household_id)
    return [
        LabelOut(label=label, category_id=remembered_category(label, uses))
        for label in suggest(q, uses, now.date())
    ]


class QuickIn(BaseModel):
    text: Annotated[str, StringConstraints(max_length=200)]


class QuickOut(BaseModel):
    day: date | None
    """None: no date typed, the grid's default applies."""
    amount: Decimal | None
    """Signed as stored: what was typed as spent is negative."""
    label: str
    category_id: UUID | None
    category_word: str | None
    """The word after #, kept when it matched no category, to say so."""


@router.post("/quick")
def understand_quick_line(
    body: QuickIn, user_session: CurrentSession, db: Db, now: Now
) -> QuickOut:
    """How the quick line is understood (F-ENT-2); nothing is saved."""
    household = user_session.user.household_id
    line = parse(body.text, now.date(), _language(user_session))
    if line.category_word is not None:
        names = {c.id: c.name for c in service.categories(db, household)}
        category = match_category(line.category_word, names)
    else:
        category = remembered_category(line.label, service.label_uses(db, household))
    return QuickOut(
        day=line.day,
        amount=-line.amount if line.amount is not None else None,
        label=line.label,
        category_id=category,
        category_word=line.category_word,
    )


# Income (F-INC-1)


class IncomeOut(BaseModel):
    month: str
    amount: Decimal | None
    """None before the first income entered."""
    carried: bool
    """No income entered this month: the previous one carried forward."""


class IncomeIn(BaseModel):
    amount: Signed


@router.get("/income/{month}")
def month_income(month: str, user_session: CurrentSession, db: Db) -> IncomeOut:
    wanted = _month(month)
    income = service.income_of(db, user_session.user.household_id, wanted)
    return IncomeOut(
        month=str(wanted),
        amount=income.amount if income else None,
        carried=income.carried if income else False,
    )


@router.put("/income/{month}")
def set_month_income(month: str, body: IncomeIn, user_session: CurrentSession, db: Db) -> IncomeOut:
    wanted = _month(month)
    try:
        amount = check_income(body.amount)
    except ValueError as exc:
        raise _unprocessable(str(exc)) from None
    service.set_income(db, user_session.user.household_id, wanted, amount)
    return IncomeOut(month=str(wanted), amount=amount, carried=False)


@router.delete("/income/{month}", status_code=status.HTTP_204_NO_CONTENT)
def remove_month_income(month: str, user_session: CurrentSession, db: Db) -> None:
    """The month carries the previous income forward again."""
    service.remove_income(db, user_session.user.household_id, _month(month))


# Fixed expenses (F-FIX)


class FixedIn(BaseModel):
    label: Label
    category_id: UUID
    amount: Signed
    """Negative: spent or put aside each time."""
    frequency: FixedFrequency
    day: Annotated[int, Field(ge=1, le=31)]
    first_month: MonthText
    last_month: MonthText | None = None
    paused: bool = False


class FixedOut(BaseModel):
    id: UUID
    label: str
    category_id: UUID
    amount: Decimal
    frequency: FixedFrequency
    day: int
    first_month: str
    last_month: str | None
    paused: bool

    @classmethod
    def of(cls, item: FixedExpense) -> "FixedOut":
        return cls(
            id=item.id,
            label=item.label,
            category_id=item.category_id,
            amount=item.amount,
            frequency=item.frequency,
            day=item.day,
            first_month=str(Month.of(item.first_month)),
            last_month=str(Month.of(item.last_month)) if item.last_month else None,
            paused=item.paused,
        )


def _fill_fixed(db: Db, user_session: CurrentSession, item: FixedExpense, body: FixedIn) -> None:
    category = _category(db, user_session, body.category_id)
    if body.amount >= 0:
        raise _unprocessable("a fixed expense is spent or put aside: a negative amount")
    first = _month(body.first_month)
    last = _month(body.last_month) if body.last_month else None
    if last is not None and last < first:
        raise _unprocessable("its last month cannot come before its first")
    item.label, item.category_id, item.amount = body.label, category.id, body.amount
    item.frequency, item.day, item.paused = body.frequency, body.day, body.paused
    item.first_month = first.first_day()
    item.last_month = last.first_day() if last else None
    db.add(item)
    db.flush()


@router.get("/fixed")
def list_fixed(user_session: CurrentSession, db: Db) -> list[FixedOut]:
    return [FixedOut.of(i) for i in service.fixed_expenses(db, user_session.user.household_id)]


@router.post("/fixed", status_code=status.HTTP_201_CREATED)
def create_fixed(body: FixedIn, user_session: CurrentSession, db: Db) -> FixedOut:
    item = FixedExpense(household_id=user_session.user.household_id)
    _fill_fixed(db, user_session, item, body)
    return FixedOut.of(item)


def _fixed(db: Db, user_session: CurrentSession, fixed_id: UUID) -> FixedExpense:
    item = service.find_fixed(db, user_session.user.household_id, fixed_id)
    if item is None:
        raise NO_FIXED
    return item


@router.put("/fixed/{fixed_id}")
def replace_fixed(fixed_id: UUID, body: FixedIn, user_session: CurrentSession, db: Db) -> FixedOut:
    item = _fixed(db, user_session, fixed_id)
    _fill_fixed(db, user_session, item, body)
    return FixedOut.of(item)


@router.delete("/fixed/{fixed_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_fixed(fixed_id: UUID, user_session: CurrentSession, db: Db, now: Now) -> None:
    """The lines confirmed from it stay."""
    item = _fixed(db, user_session, fixed_id)
    audit.record(
        db,
        user_session.user,
        AuditAction.FIXED_EXPENSE_DELETED,
        now,
        label=item.label,
        amount=item.amount,
    )
    db.delete(item)


@router.put("/fixed/{fixed_id}/skips/{month}", status_code=status.HTTP_204_NO_CONTENT)
def skip_occurrence(fixed_id: UUID, month: str, user_session: CurrentSession, db: Db) -> None:
    service.set_skip(db, _fixed(db, user_session, fixed_id), _month(month), skipped=True)


@router.delete("/fixed/{fixed_id}/skips/{month}", status_code=status.HTTP_204_NO_CONTENT)
def unskip_occurrence(fixed_id: UUID, month: str, user_session: CurrentSession, db: Db) -> None:
    service.set_skip(db, _fixed(db, user_session, fixed_id), _month(month), skipped=False)


class FixedOccurrenceOut(BaseModel):
    fixed_expense_id: UUID
    label: str
    category_id: UUID
    due: date
    amount: Decimal
    status: FixedStatus
    line_id: UUID | None


@router.get("/fixed/occurrences")
def month_occurrences(
    user_session: CurrentSession,
    db: Db,
    month: Annotated[MonthText, Query(description="YYYY-MM")],
) -> list[FixedOccurrenceOut]:
    """The month's occurrences by due date: confirmed, skipped or still to confirm."""
    return [
        FixedOccurrenceOut(
            fixed_expense_id=item.id,
            label=item.label,
            category_id=item.category_id,
            due=o.due,
            amount=o.amount,
            status=o.status,
            line_id=o.line_id,
        )
        for item, o in service.occurrences(db, user_session.user.household_id, _month(month))
    ]
