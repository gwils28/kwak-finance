"""The spending since v1.0 (§4.2 to 4.6): categories, lines (income included), fixed expenses.

Spending belongs to the household: every member sees and edits every line (§3).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from kwak_core import fixed as core_fixed
from kwak_core.budget import Month
from kwak_core.categories import DEFAULT_SPENDING_CATEGORIES, CategoryKind
from kwak_core.labels import Use
from kwak_core.spending import LineKindError, check_line_kinds
from kwak_core.splits import Part, SplitError, split
from kwak_core.users import Language
from sqlalchemy import Select, exists, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from kwak_api.models import (
    FixedExpense,
    FixedSkip,
    SpendingCategory,
    SpendingLine,
    SpendingLinePart,
    User,
)


class DuplicateCategoryError(Exception):
    """Another category has this name."""


class CategoryInUseError(Exception):
    """It still holds lines, parts or fixed expenses: say where to move them."""


class LineError(ValueError):
    """The line does not fit its categories."""


# Categories (F-CAT-1, 4, 6)


def seed_categories(db: Session, household_id: UUID, language: Language = Language.EN) -> None:
    db.add_all(
        SpendingCategory(
            household_id=household_id,
            name=default.name(language),
            kind=default.kind,
            one_off=default.one_off,
            position=position,
        )
        for position, default in enumerate(DEFAULT_SPENDING_CATEGORIES)
    )
    db.flush()


def categories(db: Session, household_id: UUID) -> list[SpendingCategory]:
    return list(
        db.scalars(
            select(SpendingCategory)
            .where(SpendingCategory.household_id == household_id)
            .order_by(SpendingCategory.position, SpendingCategory.name)
        )
    )


def find_category(db: Session, household_id: UUID, category_id: UUID) -> SpendingCategory | None:
    category = db.get(SpendingCategory, category_id)
    return category if category is not None and category.household_id == household_id else None


def flush_unique(db: Session) -> None:
    try:
        with db.begin_nested():
            db.flush()
    except IntegrityError as exc:
        if "uq_spending_category_household_name" in str(exc.orig):
            raise DuplicateCategoryError from None
        raise


def create_category(
    db: Session, household_id: UUID, name: str, kind: CategoryKind
) -> SpendingCategory:
    last = db.scalar(
        select(func.max(SpendingCategory.position)).where(
            SpendingCategory.household_id == household_id
        )
    )
    category = SpendingCategory(
        household_id=household_id,
        name=" ".join(name.split()),
        kind=kind,
        position=(last or 0) + 1,
    )
    db.add(category)
    flush_unique(db)
    return category


def _in_use(db: Session, category: SpendingCategory) -> bool:
    return any(
        db.scalar(select(exists().where(column == category.id)))
        for column in (
            SpendingLine.category_id,
            SpendingLinePart.category_id,
            FixedExpense.category_id,
        )
    )


def delete_category(
    db: Session, category: SpendingCategory, move_to: SpendingCategory | None
) -> None:
    """Its lines, parts and fixed expenses go to `move_to`, needed when it holds any."""
    if move_to is None:
        if _in_use(db, category):
            raise CategoryInUseError
    else:
        for model in (SpendingLine, SpendingLinePart, FixedExpense):
            db.execute(
                update(model).where(model.category_id == category.id).values(category_id=move_to.id)
            )
    db.delete(category)
    db.flush()


def restore_categories(db: Session, household_id: UUID, language: Language) -> int:
    """Add back the default categories missing by name; how many were added."""
    have = {c.name.casefold() for c in categories(db, household_id)}
    added = 0
    for default in DEFAULT_SPENDING_CATEGORIES:
        if default.name(language).casefold() not in have:
            category = create_category(db, household_id, default.name(language), default.kind)
            category.one_off = default.one_off
            added += 1
    db.flush()
    return added


# Lines (F-LIN)


@dataclass(frozen=True)
class LineData:
    day: date
    label: str
    amount: Decimal
    category_id: UUID | None
    given: Sequence[Part] = ()
    """A split's parts but the last, which takes the rest in `category_id`."""
    fixed_expense_id: UUID | None = None


def _check_line(data: LineData, kinds: dict[UUID, CategoryKind]) -> tuple[UUID | None, list[Part]]:
    """The line's own category, or its parts when split."""
    if data.category_id is None or data.category_id not in kinds:
        raise LineError("a line needs a category of the household")
    if any(p.category_id not in kinds for p in data.given):
        raise LineError("every part needs a category of the household")
    parts: list[Part] = []
    if data.given:
        try:
            parts = split(data.amount, data.given, data.category_id)
        except SplitError as exc:
            raise LineError(str(exc)) from None
    used = {kinds[c] for p in parts if (c := p.category_id)} or {kinds[data.category_id]}
    try:
        check_line_kinds(data.amount, used)
    except LineKindError as exc:
        raise LineError(str(exc)) from None
    return (None, parts) if parts else (data.category_id, [])


def _kinds(db: Session, household_id: UUID) -> dict[UUID, CategoryKind]:
    return {c.id: c.kind for c in categories(db, household_id)}


def _fill(db: Session, line: SpendingLine, data: LineData) -> SpendingLine:
    category_id, parts = _check_line(data, _kinds(db, line.household_id))
    if data.fixed_expense_id is not None:
        item = db.get(FixedExpense, data.fixed_expense_id)
        if item is None or item.household_id != line.household_id:
            raise LineError("no such fixed expense")
    line.day, line.label, line.amount = data.day, data.label, data.amount
    line.category_id, line.fixed_expense_id = category_id, data.fixed_expense_id
    line.parts = [
        SpendingLinePart(position=i, category_id=p.category_id, amount=p.amount)
        for i, p in enumerate(parts)
    ]
    db.add(line)
    db.flush()
    return line


def create_line(db: Session, user: User, data: LineData, now: datetime) -> SpendingLine:
    """`now` is when it was entered (F-ENT-4)."""
    line = SpendingLine(household_id=user.household_id, entered_by=user, created_at=now)
    return _fill(db, line, data)


def replace_line(db: Session, line: SpendingLine, data: LineData) -> SpendingLine:
    return _fill(db, line, data)


def find_line(db: Session, household_id: UUID, line_id: UUID) -> SpendingLine | None:
    line = db.get(SpendingLine, line_id)
    return line if line is not None and line.household_id == household_id else None


def _lines(household_id: UUID) -> Select[SpendingLine]:
    return (
        select(SpendingLine)
        .where(SpendingLine.household_id == household_id)
        .options(selectinload(SpendingLine.parts), selectinload(SpendingLine.entered_by))
    )


def lines_of_month(db: Session, household_id: UUID, month: Month) -> list[SpendingLine]:
    """By date, then in the order they were entered."""
    return list(
        db.scalars(
            _lines(household_id)
            .where(
                SpendingLine.day >= month.first_day(), SpendingLine.day < month.next().first_day()
            )
            .order_by(SpendingLine.day, SpendingLine.created_at, SpendingLine.id)
        )
    )


def last_entry(db: Session, household_id: UUID) -> SpendingLine | None:
    """The line entered last (F-ENT-4)."""
    return db.scalars(
        _lines(household_id).order_by(SpendingLine.created_at.desc(), SpendingLine.id.desc())
    ).first()


def label_uses(db: Session, household_id: UUID) -> list[Use]:
    """Every line with a category of its own, for the label memory (F-ENT-3)."""
    rows = db.execute(
        select(
            SpendingLine.label,
            SpendingLine.category_id,
            SpendingLine.day,
            SpendingLine.created_at,
        ).where(SpendingLine.household_id == household_id, SpendingLine.category_id.is_not(None))
    )
    return [Use(label, category, day, at) for label, category, day, at in rows if category]


# Fixed expenses (F-FIX)


def fixed_expenses(db: Session, household_id: UUID) -> list[FixedExpense]:
    return list(
        db.scalars(
            select(FixedExpense)
            .where(FixedExpense.household_id == household_id)
            .order_by(FixedExpense.day, FixedExpense.label)
        )
    )


def find_fixed(db: Session, household_id: UUID, fixed_id: UUID) -> FixedExpense | None:
    item = db.get(FixedExpense, fixed_id)
    return item if item is not None and item.household_id == household_id else None


def core_item(item: FixedExpense) -> core_fixed.FixedExpense:
    return core_fixed.FixedExpense(
        item.id,
        item.label,
        item.category_id,
        item.amount,
        item.frequency,
        item.day,
        Month.of(item.first_month),
        Month.of(item.last_month) if item.last_month else None,
        item.paused,
    )


def set_skip(db: Session, item: FixedExpense, month: Month, skipped: bool) -> None:
    row = db.scalar(
        select(FixedSkip).where(
            FixedSkip.fixed_expense_id == item.id, FixedSkip.month == month.first_day()
        )
    )
    if skipped and row is None:
        db.add(FixedSkip(fixed_expense_id=item.id, month=month.first_day()))
    elif not skipped and row is not None:
        db.delete(row)
    db.flush()


def occurrences(
    db: Session, household_id: UUID, month: Month
) -> list[tuple[FixedExpense, core_fixed.Occurrence]]:
    items = fixed_expenses(db, household_id)
    skipped = set(
        db.scalars(
            select(FixedSkip.fixed_expense_id).where(
                FixedSkip.fixed_expense_id.in_([i.id for i in items]),
                FixedSkip.month == month.first_day(),
            )
        )
    )
    lines = [
        core_fixed.LineRef(ln.id, ln.label, ln.category_id, ln.day, ln.fixed_expense_id)
        for ln in lines_of_month(db, household_id, month)
    ]
    by_id = {i.id: i for i in items}
    found = core_fixed.occurrences([core_item(i) for i in items], month, lines, skipped)
    return [(by_id[o.item_id], o) for o in found]
