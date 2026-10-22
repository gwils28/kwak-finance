import re
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from kwak_core.audit import AuditAction
from kwak_core.budget import Month, month_range
from kwak_core.goals import GoalError
from kwak_core.money import quantize, require_cents
from kwak_core.visibility import Scope, Visibility
from kwak_core.wealth import WEALTH_COLOURS, Cell, WealthKind, WealthValueError, check_value
from pydantic import AfterValidator, BaseModel, Field, StringConstraints

from kwak_api.auth.routes import CurrentSession, Db, Now
from kwak_api.models import WealthCategory, WealthLine
from kwak_api.services import audit, goals
from kwak_api.services import wealth as service
from kwak_api.services.households import wealth_start

router = APIRouter(prefix="/api/wealth", tags=["wealth"])

MONTH = re.compile(r"[0-9]{4}-[0-9]{2}")
YEARS = range(1900, 2201)
MAX_MONTHS = 120
DEFAULT_MONTHS = 12
RATIO = Decimal("0.0001")
NOT_FOUND = HTTPException(status.HTTP_404_NOT_FOUND, "no such wealth line")
NO_CATEGORY = HTTPException(status.HTTP_404_NOT_FOUND, "no such wealth category")
DUPLICATE = HTTPException(status.HTTP_409_CONFLICT, "another category has this name")


CategoryName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]
LineName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
MonthText = Annotated[str, StringConstraints(max_length=7)]


def _colour(key: str) -> str:
    if key not in WEALTH_COLOURS:
        raise ValueError(f"unknown colour, expected one of {sorted(WEALTH_COLOURS)}")
    return key


Colour = Annotated[str, AfterValidator(_colour)]
# What NUMERIC(14, 2) holds, whole cents only.
Amount = Annotated[Decimal, Field(ge=0, lt=Decimal("1e12")), AfterValidator(require_cents)]


def _unprocessable(message: str) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, message)


def _month(text: str) -> Month:
    month = Month.parse(text) if MONTH.fullmatch(text) else None
    if month is None or month.year not in YEARS:
        raise _unprocessable(f"invalid month {text!r}, expected YYYY-MM")
    return month


def _parse_month(text: str) -> Month:
    try:
        return _month(text)
    except ValueError:
        raise _unprocessable(f"invalid month {text!r}, expected YYYY-MM") from None


def _ratio(value: Decimal | None) -> Decimal | None:
    return None if value is None else value.quantize(RATIO, rounding=ROUND_HALF_UP)


class WealthCategoryOut(BaseModel):
    id: UUID
    name: str
    kind: WealthKind
    colour: str
    """The key of its `wealth-<key>` colour token."""
    position: int

    @classmethod
    def of(cls, c: WealthCategory) -> "WealthCategoryOut":
        return cls(id=c.id, name=c.name, kind=c.kind, colour=c.colour, position=c.position)


class WealthCategoryIn(BaseModel):
    name: CategoryName
    kind: WealthKind = WealthKind.ASSET
    colour: Colour


class WealthCategoryPatch(BaseModel):
    name: CategoryName | None = None
    colour: Colour | None = None
    position: int | None = Field(default=None, ge=0)


@router.get("/categories")
def list_wealth_categories(user_session: CurrentSession, db: Db) -> list[WealthCategoryOut]:
    """In the matrix's order."""
    return [WealthCategoryOut.of(c) for c in service.categories(db, user_session.user.household_id)]


@router.post("/categories", status_code=status.HTTP_201_CREATED)
def create_wealth_category(
    body: WealthCategoryIn, user_session: CurrentSession, db: Db
) -> WealthCategoryOut:
    """New categories go last."""
    try:
        category = service.create_category(
            db,
            user_session.user.household_id,
            name=body.name,
            kind=body.kind,
            colour=body.colour,
        )
    except service.DuplicateCategoryError:
        raise DUPLICATE from None
    return WealthCategoryOut.of(category)


@router.patch("/categories/{category_id}")
def update_wealth_category(
    category_id: UUID, body: WealthCategoryPatch, user_session: CurrentSession, db: Db
) -> WealthCategoryOut:
    category = service.find_category(db, user_session.user.household_id, category_id)
    if category is None:
        raise NO_CATEGORY
    try:
        if body.name is not None:
            service.rename_category(db, category, body.name)
    except service.DuplicateCategoryError:
        raise DUPLICATE from None
    if body.colour is not None:
        category.colour = body.colour
    if body.position is not None:
        service.move_category(db, category, body.position)
    return WealthCategoryOut.of(category)


@router.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_wealth_category(
    category_id: UUID, user_session: CurrentSession, db: Db, now: Now
) -> None:
    """Only once it holds no line."""
    category = service.find_category(db, user_session.user.household_id, category_id)
    if category is None:
        raise NO_CATEGORY
    name = category.name
    try:
        service.delete_category(db, category)
    except service.CategoryInUseError:
        # Every line counts, private ones included: they would be lost otherwise.
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "it still holds lines (perhaps a member's private ones): move or delete them first",
        ) from None
    audit.record(db, user_session.user, AuditAction.WEALTH_CATEGORY_DELETED, now, name=name)


class WealthLineOut(BaseModel):
    id: UUID
    category_id: UUID
    name: str
    owner_id: UUID
    owner_name: str
    visibility: Visibility
    closed_from: str | None

    @classmethod
    def of(cls, line: WealthLine) -> "WealthLineOut":
        return cls(
            id=line.id,
            category_id=line.category_id,
            name=line.name,
            owner_id=line.owner_id,
            owner_name=line.owner.display_name,
            visibility=line.visibility,
            closed_from=str(Month.of(line.closed_from)) if line.closed_from else None,
        )


class WealthLineIn(BaseModel):
    category_id: UUID
    name: LineName
    visibility: Visibility = Visibility.SHARED


class WealthLinePatch(BaseModel):
    """Only the fields present change."""

    category_id: UUID | None = None
    name: LineName | None = None
    visibility: Visibility | None = None
    closed_from: MonthText | None = None
    """YYYY-MM, the first month it no longer holds anything; null to reopen it."""


def _line(db: Db, user_session: CurrentSession, line_id: UUID) -> WealthLine:
    line = service.find_line(db, user_session.user, line_id)
    if line is None:
        raise NOT_FOUND
    return line


def _category_of(db: Db, user_session: CurrentSession, category_id: UUID) -> WealthCategory:
    category = service.find_category(db, user_session.user.household_id, category_id)
    if category is None:
        raise _unprocessable("unknown wealth category")
    return category


@router.get("/lines")
def list_wealth_lines(user_session: CurrentSession, db: Db) -> list[WealthLineOut]:
    """The lines the user can see, closed ones included."""
    return [WealthLineOut.of(line) for line in service.visible_lines(db, user_session.user)]


@router.post("/lines", status_code=status.HTTP_201_CREATED)
def create_wealth_line(body: WealthLineIn, user_session: CurrentSession, db: Db) -> WealthLineOut:
    """The user owns the lines they create."""
    user = user_session.user
    category = _category_of(db, user_session, body.category_id)
    line = WealthLine(
        household_id=user.household_id,
        category_id=category.id,
        name=body.name,
        owner_id=user.id,
        visibility=body.visibility,
    )
    db.add(line)
    db.flush()
    db.refresh(line)
    return WealthLineOut.of(line)


@router.patch("/lines/{line_id}")
def update_wealth_line(
    line_id: UUID, body: WealthLinePatch, user_session: CurrentSession, db: Db
) -> WealthLineOut:
    """Anyone who sees a line edits it; only its owner changes who sees it."""
    line = _line(db, user_session, line_id)
    given = body.model_fields_set
    if body.visibility is not None and body.visibility != line.visibility:
        if line.owner_id != user_session.user.id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "only its owner changes who sees it")
        try:
            goals.check_line_visibility(db, line, body.visibility)
        except GoalError as exc:
            raise HTTPException(status.HTTP_409_CONFLICT, f"it funds a goal: {exc}") from None
        line.visibility = body.visibility
    if body.category_id is not None:
        line.category_id = _category_of(db, user_session, body.category_id).id
    if body.name is not None:
        line.name = body.name
    if "closed_from" in given:
        line.closed_from = _parse_month(body.closed_from).first_day() if body.closed_from else None
    db.flush()
    db.refresh(line)
    return WealthLineOut.of(line)


@router.delete("/lines/{line_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_wealth_line(line_id: UUID, user_session: CurrentSession, db: Db, now: Now) -> None:
    """With its values. Only its owner can; closing it keeps its history instead."""
    line = _line(db, user_session, line_id)
    if line.owner_id != user_session.user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "only its owner deletes it")
    audit.record(
        db,
        user_session.user,
        AuditAction.WEALTH_LINE_DELETED,
        now,
        private_to=line.owner_id if line.visibility is Visibility.PRIVATE else None,
        name=line.name,
        category=line.category.name,
    )
    db.delete(line)


class WealthValueIn(BaseModel):
    amount: Amount
    """Cents at most, positive: a debt is what is still owed."""


def _checked(amount: Decimal) -> Decimal:
    try:
        check_value(amount)
    except WealthValueError as exc:
        raise _unprocessable(str(exc)) from None
    return amount


def _set(db: Db, line: WealthLine, month: Month, amount: Decimal) -> None:
    try:
        service.set_value(db, line, month, _checked(amount))
    except service.ClosedMonthError:
        raise _unprocessable(f"{line.name} is closed in {month}") from None


@router.put("/lines/{line_id}/values/{month}", status_code=status.HTTP_204_NO_CONTENT)
def set_wealth_value(
    line_id: UUID, month: str, body: WealthValueIn, user_session: CurrentSession, db: Db
) -> None:
    """The line's value for this calendar month (F-WLT-3)."""
    line = _line(db, user_session, line_id)
    _set(db, line, _parse_month(month), body.amount)


@router.delete("/lines/{line_id}/values/{month}", status_code=status.HTTP_204_NO_CONTENT)
def remove_wealth_value(line_id: UUID, month: str, user_session: CurrentSession, db: Db) -> None:
    """The month carries the previous value forward again."""
    service.remove_value(db, _line(db, user_session, line_id), _parse_month(month))


class WealthUpdateLineOut(BaseModel):
    line_id: UUID
    name: str
    category_id: UUID
    category_name: str
    last_value: Decimal | None


class WealthUpdateValue(BaseModel):
    line_id: UUID
    amount: Amount


class WealthUpdateIn(BaseModel):
    month: MonthText
    values: list[WealthUpdateValue] = Field(max_length=500)


@router.get("/update")
def wealth_lines_to_update(
    user_session: CurrentSession,
    db: Db,
    now: Now,
    month: Annotated[str | None, Query(description="YYYY-MM; default: this month")] = None,
) -> list[WealthUpdateLineOut]:
    """ "Update this month": the open lines, with their last value pre-filled."""
    when = _parse_month(month) if month else Month.of(now.date())
    return [
        WealthUpdateLineOut(
            line_id=line.id,
            name=line.name,
            category_id=line.category_id,
            category_name=line.category.name,
            last_value=last,
        )
        for line, last in service.lines_to_update(db, user_session.user, when)
    ]


@router.post("/update", status_code=status.HTTP_204_NO_CONTENT)
def update_wealth_month(body: WealthUpdateIn, user_session: CurrentSession, db: Db) -> None:
    """Save several lines' values for one month at once: all or nothing."""
    month = _parse_month(body.month)
    visible = {line.id: line for line in service.visible_lines(db, user_session.user)}
    for value in body.values:
        line = visible.get(value.line_id)
        if line is None:
            raise NOT_FOUND  # nothing is saved: the request rolls back
        _set(db, line, month, value.amount)


class WealthCellOut(BaseModel):
    amount: Decimal
    carried: bool
    """No value entered this month: the previous one, carried forward."""


def _cell(cell: Cell | None) -> WealthCellOut | None:
    return (
        None if cell is None else WealthCellOut(amount=quantize(cell.amount), carried=cell.carried)
    )


class WealthMatrixLineOut(BaseModel):
    id: UUID
    name: str
    owner_id: UUID
    owner_name: str
    visibility: Visibility
    closed_from: str | None
    """YYYY-MM: from this month on the line holds nothing and takes no value."""
    cells: list[WealthCellOut | None]
    share: Decimal | None
    """Of gross assets in the last month."""


class WealthMatrixCategoryOut(BaseModel):
    id: UUID
    name: str
    kind: WealthKind
    colour: str
    subtotals: list[Decimal]
    share: Decimal | None
    """Of gross assets in the last month; null for debts."""
    lines: list[WealthMatrixLineOut]


class WealthMatrixOut(BaseModel):
    months: list[str]
    categories: list[WealthMatrixCategoryOut]
    gross: list[Decimal]
    debts: list[Decimal]
    net: list[Decimal]
    change: list[Decimal | None]
    """Net worth against the month before; null when that month held nothing."""
    change_ratio: list[Decimal | None]


def _window(start: str | None, end: str | None, today: date, since: Month | None) -> list[Month]:
    if (start is None) != (end is None):
        raise _unprocessable("give both start and end, or neither")
    if start is None or end is None:
        last = Month.of(today)
        first = last
        for _ in range(DEFAULT_MONTHS - 1):
            first = first.previous()
        if since is not None and since > first:
            first = min(since, last)
        return month_range(first, last)
    first, last = _parse_month(start), _parse_month(end)
    if last > Month.of(today):
        raise _unprocessable("the matrix ends this month at the latest: later months are unknown")
    months = month_range(first, last) if first <= last else []
    if not 1 <= len(months) <= MAX_MONTHS:
        raise _unprocessable(f"a matrix covers 1 to {MAX_MONTHS} months, from start to end")
    return months


@router.get("/matrix")
def wealth_matrix(
    user_session: CurrentSession,
    db: Db,
    now: Now,
    start: Annotated[str | None, Query(description="First month, YYYY-MM")] = None,
    end: Annotated[str | None, Query(description="Last month, YYYY-MM")] = None,
    scope: Scope = Scope.HOUSEHOLD,
) -> WealthMatrixOut:
    """The wealth matrix (F-WLT-5). Without a window: the last 12 months, from the wealth start
    at the earliest."""
    user = user_session.user
    months = _window(start, end, now.date(), wealth_start(db, user.household_id))
    m = service.matrix(db, user, months, scope)
    r = m.result
    by_category: dict[UUID, list[service.LineView]] = {c.id: [] for c in m.categories}
    for view in m.lines:
        by_category[view.input.category_id].append(view)
    return WealthMatrixOut(
        months=[str(month) for month in months],
        categories=[
            WealthMatrixCategoryOut(
                id=c.id,
                name=c.name,
                kind=c.kind,
                colour=c.colour,
                subtotals=[quantize(v) for v in r.categories[c.id]],
                share=_ratio(r.shares.get(c.id)),
                lines=[
                    WealthMatrixLineOut(
                        id=v.input.id,
                        name=v.name,
                        owner_id=v.input.owner_id,
                        owner_name=v.owner_name,
                        visibility=v.input.visibility,
                        closed_from=str(v.input.closed_from) if v.input.closed_from else None,
                        cells=[_cell(cell) for cell in r.lines[v.input.id]],
                        share=_ratio(r.line_shares.get(v.input.id)),
                    )
                    for v in sorted(by_category[c.id], key=lambda v: v.name.lower())
                ],
            )
            for c in m.categories
        ],
        gross=[quantize(v) for v in r.gross],
        debts=[quantize(v) for v in r.debts],
        net=[quantize(v) for v in r.net],
        change=[None if v is None else quantize(v) for v in r.change],
        change_ratio=[_ratio(v) for v in r.change_ratio],
    )
