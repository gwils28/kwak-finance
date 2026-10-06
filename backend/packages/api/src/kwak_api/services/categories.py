"""Household categories: a two-level tree seeded with defaults (F-CAT-1)."""

from uuid import UUID

from kwak_core.categories import DEFAULT_CATEGORIES, CategoryKind, check_hierarchy
from sqlalchemy import exists, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from kwak_api.models import Category, Transaction


class DuplicateCategoryError(Exception):
    """A sibling already has this name."""


class CategoryInUseError(Exception):
    """The category still has subcategories."""


def seed_defaults(db: Session, household_id: UUID) -> None:
    for default in DEFAULT_CATEGORIES:
        parent = Category(household_id=household_id, name=default.name, kind=default.kind)
        db.add(parent)
        db.flush()
        db.add_all(
            Category(household_id=household_id, parent_id=parent.id, name=child, kind=default.kind)
            for child in default.children
        )
    db.flush()


def tree(db: Session, household_id: UUID) -> list[Category]:
    """Every category, each parent followed by its children, alphabetically."""
    categories = list(db.scalars(select(Category).where(Category.household_id == household_id)))
    by_name = sorted(categories, key=lambda c: c.name.lower())
    ordered = []
    for parent in (c for c in by_name if c.parent_id is None):
        ordered.append(parent)
        ordered.extend(c for c in by_name if c.parent_id == parent.id)
    return ordered


def find(db: Session, household_id: UUID, category_id: UUID) -> Category | None:
    category = db.get(Category, category_id)
    return category if category and category.household_id == household_id else None


def _has_children(db: Session, category: Category) -> bool:
    return bool(db.scalar(select(exists().where(Category.parent_id == category.id))))


def _flush_unique(db: Session) -> None:
    try:
        with db.begin_nested():
            db.flush()
    except IntegrityError as exc:
        if "uq_category_household_parent_name" in str(exc.orig):
            raise DuplicateCategoryError from None
        raise


def _clean(name: str) -> str:
    name = " ".join(name.split())
    if not name:
        raise ValueError("a category name is required")
    return name


def create(
    db: Session, household_id: UUID, *, name: str, kind: CategoryKind, parent: Category | None
) -> Category:
    if parent is not None:
        check_hierarchy(parent=(parent.parent_id, parent.kind), has_children=False)
        kind = parent.kind
    category = Category(
        household_id=household_id,
        parent_id=parent.id if parent else None,
        name=_clean(name),
        kind=kind,
    )
    db.add(category)
    _flush_unique(db)
    return category


def update_category(
    db: Session, category: Category, *, name: str | None, parent: Category | None, move: bool
) -> None:
    """Rename and/or move (`move` with `parent` None puts it at the top level)."""
    if name is not None:
        category.name = _clean(name)
    if move:
        if parent is not None:
            if parent.id == category.id:
                raise ValueError("a category cannot be its own parent")
            check_hierarchy(
                parent=(parent.parent_id, parent.kind),
                has_children=_has_children(db, category),
                kind=category.kind,
            )
        category.parent_id = parent.id if parent else None
    _flush_unique(db)


def delete(db: Session, category: Category) -> None:
    if _has_children(db, category):
        raise CategoryInUseError
    db.execute(
        update(Transaction).where(Transaction.category_id == category.id).values(category_id=None)
    )
    db.delete(category)
    db.flush()
