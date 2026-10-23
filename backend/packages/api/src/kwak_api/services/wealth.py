"""The monthly wealth matrix (F-WLT): categories, lines entered by hand and their values."""

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from kwak_core.budget import Month
from kwak_core.ids import uuid7
from kwak_core.users import Language
from kwak_core.visibility import Scope, can_view
from kwak_core.wealth import (
    DEFAULT_WEALTH_CATEGORIES,
    CategoryInput,
    LineInput,
    WealthMatrix,
    in_scope,
    to_update,
    wealth_matrix,
)
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from kwak_api.models import User, WealthCategory, WealthLine, WealthValue


class CategoryInUseError(Exception):
    """The category still holds lines."""


class DuplicateCategoryError(Exception):
    """Another category has this name (any case)."""


def seed_defaults(db: Session, household_id: UUID, language: Language = Language.EN) -> None:
    db.add_all(
        WealthCategory(
            household_id=household_id,
            name=default.names.name(language),
            kind=default.kind,
            colour=default.colour,
            preset=default.colour,
            position=position,
        )
        for position, default in enumerate(DEFAULT_WEALTH_CATEGORIES)
    )
    db.flush()


def categories(db: Session, household_id: UUID) -> list[WealthCategory]:
    return list(
        db.scalars(
            select(WealthCategory)
            .where(WealthCategory.household_id == household_id)
            .order_by(WealthCategory.position, WealthCategory.name)
        )
    )


def find_category(db: Session, household_id: UUID, category_id: UUID) -> WealthCategory | None:
    category = db.get(WealthCategory, category_id)
    return category if category and category.household_id == household_id else None


def _flush_unique(db: Session) -> None:
    try:
        with db.begin_nested():
            db.flush()
    except IntegrityError:
        raise DuplicateCategoryError from None


def create_category(db: Session, household_id: UUID, **fields: object) -> WealthCategory:
    last = db.scalar(
        select(func.max(WealthCategory.position)).where(WealthCategory.household_id == household_id)
    )
    category = WealthCategory(
        household_id=household_id, position=0 if last is None else last + 1, **fields
    )
    db.add(category)
    _flush_unique(db)
    return category


def move_category(db: Session, category: WealthCategory, position: int) -> None:
    """Put the category at `position` (0: the top), the others keeping their order."""
    others = [c for c in categories(db, category.household_id) if c.id != category.id]
    position = max(0, min(position, len(others)))
    for index, c in enumerate([*others[:position], category, *others[position:]]):
        c.position = index
    db.flush()


def rename_category(db: Session, category: WealthCategory, name: str) -> None:
    category.name = name
    _flush_unique(db)


def delete_category(db: Session, category: WealthCategory) -> None:
    held = db.scalar(select(func.count()).where(WealthLine.category_id == category.id))
    if held:
        raise CategoryInUseError
    db.delete(category)
    db.flush()


def visible_lines(db: Session, viewer: User) -> list[WealthLine]:
    lines = db.scalars(
        select(WealthLine)
        .where(WealthLine.household_id == viewer.household_id)
        .options(joinedload(WealthLine.owner), joinedload(WealthLine.category))
        .order_by(func.lower(WealthLine.name))
    )
    return [
        line
        for line in lines
        if can_view(owner_id=line.owner_id, visibility=line.visibility, viewer_id=viewer.id)
    ]


def find_line(db: Session, viewer: User, line_id: UUID) -> WealthLine | None:
    line = db.get(WealthLine, line_id)
    if line is None or line.household_id != viewer.household_id:
        return None
    visible = can_view(owner_id=line.owner_id, visibility=line.visibility, viewer_id=viewer.id)
    return line if visible else None


class ClosedMonthError(Exception):
    """The line is closed in that month."""


def set_value(db: Session, line: WealthLine, month: Month, amount: Decimal) -> None:
    if line.closed_from is not None and month >= Month.of(line.closed_from):
        raise ClosedMonthError
    # One statement: two saves of the same month at once cannot both insert.
    db.execute(
        insert(WealthValue)
        .values(id=uuid7(), line_id=line.id, month=month.first_day(), amount=amount)
        .on_conflict_do_update(
            index_elements=[WealthValue.line_id, WealthValue.month], set_={"amount": amount}
        )
    )


def remove_value(db: Session, line: WealthLine, month: Month) -> None:
    value = db.scalar(
        select(WealthValue).where(
            WealthValue.line_id == line.id, WealthValue.month == month.first_day()
        )
    )
    if value is not None:
        db.delete(value)
        db.flush()


def _values(db: Session, lines: Sequence[WealthLine]) -> dict[UUID, dict[Month, Decimal]]:
    out: dict[UUID, dict[Month, Decimal]] = defaultdict(dict)
    for line_id, month, amount in db.execute(
        select(WealthValue.line_id, WealthValue.month, WealthValue.amount).where(
            WealthValue.line_id.in_([line.id for line in lines])
        )
    ):
        out[line_id][Month.of(month)] = amount
    return out


@dataclass
class LineView:
    input: LineInput
    name: str
    owner_name: str


@dataclass
class Matrix:
    categories: list[WealthCategory]
    lines: list[LineView]
    result: WealthMatrix


def _line_views(db: Session, viewer: User) -> list[LineView]:
    lines = visible_lines(db, viewer)
    values = _values(db, lines)
    return [
        LineView(
            LineInput(
                line.id,
                line.category_id,
                values.get(line.id, {}),
                line.owner_id,
                line.visibility,
                closed_from=Month.of(line.closed_from) if line.closed_from else None,
            ),
            line.name,
            line.owner.display_name,
        )
        for line in lines
    ]


def matrix(db: Session, viewer: User, months: list[Month], scope: Scope) -> Matrix:
    rows = categories(db, viewer.household_id)
    views = _line_views(db, viewer)
    kept = {line.id for line in in_scope([v.input for v in views], scope, viewer.id)}
    scoped = [v for v in views if v.input.id in kept]
    result = wealth_matrix(
        [CategoryInput(c.id, c.kind) for c in rows], [v.input for v in scoped], months
    )
    return Matrix(rows, scoped, result)


def lines_to_update(
    db: Session, viewer: User, month: Month
) -> list[tuple[WealthLine, Decimal | None]]:
    """The open lines the viewer sees, with their last value (F-WLT-3)."""
    manual = visible_lines(db, viewer)
    values = _values(db, manual)
    by_id = {line.id: line for line in manual}
    inputs = [
        LineInput(
            line.id,
            line.category_id,
            values.get(line.id, {}),
            line.owner_id,
            line.visibility,
            closed_from=Month.of(line.closed_from) if line.closed_from else None,
        )
        for line in manual
    ]
    order = {c.id: c.position for c in categories(db, viewer.household_id)}
    listed = to_update(
        sorted(inputs, key=lambda i: (order.get(i.category_id, 0), by_id[i.id].name)), month
    )
    return [(by_id[line.id], last) for line, last in listed]
