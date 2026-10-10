"""Household categories: a two-level tree seeded with defaults (F-CAT-1)."""

from dataclasses import dataclass, field
from datetime import date
from uuid import UUID

from kwak_core.categories import (
    DEFAULT_CATEGORIES,
    CategoryKind,
    Existing,
    RestorePlan,
    check_hierarchy,
    plan_restore,
)
from kwak_core.users import Language
from sqlalchemy import delete as delete_rows
from sqlalchemy import exists, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from kwak_api.models import (
    BudgetPlan,
    BudgetPlanTarget,
    CategorizationRule,
    Category,
    Transaction,
)
from kwak_api.services.budget import is_editable


class DuplicateCategoryError(Exception):
    """A sibling already has this name."""


class CategoryInUseError(Exception):
    """The category still has subcategories."""


def seed_defaults(db: Session, household_id: UUID, language: Language = Language.EN) -> None:
    for default in DEFAULT_CATEGORIES:
        parent = Category(household_id=household_id, name=default.name(language), kind=default.kind)
        db.add(parent)
        db.flush()
        db.add_all(
            Category(
                household_id=household_id,
                parent_id=parent.id,
                name=child.name(language),
                kind=default.kind,
            )
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


@dataclass
class RestoreSummary:
    """What restoring the default categories does (preview) or did."""

    language: Language
    created: list[str] = field(default_factory=list)
    renamed: list[tuple[str, str]] = field(default_factory=list)
    merged: list[tuple[str, str]] = field(default_factory=list)
    """(duplicate, the category it merges into, under its final name)."""
    moved: list[str] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)
    transactions_to_categorise: int = 0
    rules_deleted: int = 0
    plan_targets_deleted: int = 0
    locked_plans_affected: int = 0
    """Plans past their first month that lose a target, so their review changes."""


def _count(
    db: Session, model: type[Transaction] | type[CategorizationRule], ids: list[UUID]
) -> int:
    return db.scalar(select(func.count()).select_from(model).where(model.category_id.in_(ids))) or 0


def restore_defaults(
    db: Session, household_id: UUID, language: Language, today: date, *, apply: bool
) -> RestoreSummary:
    """Bring the categories back to the defaults (kwak_core.categories.plan_restore).

    Kept defaults keep their transactions, rules and plan targets; duplicates merge into
    them. Deleting a category sends its transactions back to "to categorise" and deletes its
    rules and plan targets. With `apply=False`, only says what would happen.
    """
    categories = {
        c.id: c for c in db.scalars(select(Category).where(Category.household_id == household_id))
    }
    plan = plan_restore(
        [Existing(c.id, c.parent_id, c.name, c.kind) for c in categories.values()], language
    )
    final = {cid: plan.renames.get(cid, c.name) for cid, c in categories.items()}
    summary = RestoreSummary(
        language,
        created=[c.name for c in plan.creates],
        renamed=[(categories[cid].name, name) for cid, name in plan.renames.items()],
        merged=[(categories[gone].name, final[kept]) for gone, kept in plan.merges.items()],
        moved=[final[cid] for cid in plan.moves],
        deleted=[categories[cid].name for cid in plan.deletes],
        transactions_to_categorise=_count(db, Transaction, plan.deletes),
        rules_deleted=_count(db, CategorizationRule, plan.deletes),
    )
    # Plan targets lost: those of deleted categories, and a duplicate's where the kept
    # category already has one in the same plan.
    targets = list(
        db.scalars(
            select(BudgetPlanTarget).where(
                BudgetPlanTarget.category_id.in_(
                    [*plan.deletes, *plan.merges, *plan.merges.values()]
                )
            )
        )
    )
    held = {(t.plan_id, t.category_id) for t in targets}
    lost = [
        t
        for t in targets
        if t.category_id in plan.deletes
        or (t.category_id in plan.merges and (t.plan_id, plan.merges[t.category_id]) in held)
    ]
    summary.plan_targets_deleted = len(lost)
    plans = {t.plan_id for t in lost}
    summary.locked_plans_affected = sum(
        1
        for p in db.scalars(select(BudgetPlan).where(BudgetPlan.id.in_(plans)))
        if not is_editable(p, today)
    )
    if apply:
        _apply(db, household_id, plan, categories, lost)
    return summary


def _apply(
    db: Session,
    household_id: UUID,
    plan: RestorePlan,
    categories: dict[UUID, Category],
    lost: list[BudgetPlanTarget],
) -> None:
    """In an order that never breaks the sibling-name index nor the parent links."""
    created: dict[str, UUID] = {}

    def resolve(parent: UUID | str | None) -> UUID | None:
        return created[parent] if isinstance(parent, str) else parent

    for new in [c for c in plan.creates if c.parent is None]:
        row = Category(household_id=household_id, name=new.name, kind=new.kind)
        db.add(row)
        db.flush()
        created[new.key] = row.id
    for target in lost:
        db.delete(target)
    db.flush()
    for gone, kept in plan.merges.items():
        db.execute(
            update(Transaction).where(Transaction.category_id == gone).values(category_id=kept)
        )
        db.execute(
            update(CategorizationRule)
            .where(CategorizationRule.category_id == gone)
            .values(category_id=kept)
        )
        db.execute(
            update(BudgetPlanTarget)
            .where(BudgetPlanTarget.category_id == gone)
            .values(category_id=kept)
        )
    # Merged subcategories go now, so a kept one can take their name; merged top-level ones
    # once their children have moved.
    merged_children = [cid for cid in plan.merges if categories[cid].parent_id is not None]
    _delete(db, merged_children)
    for cid, name in plan.renames.items():
        categories[cid].name = name
        db.flush()
    for cid, parent in plan.moves.items():
        categories[cid].parent_id = resolve(parent)
        db.flush()
    db.add_all(
        Category(household_id=household_id, parent_id=resolve(c.parent), name=c.name, kind=c.kind)
        for c in plan.creates
        if c.parent is not None
    )
    db.flush()
    _delete(db, plan.deletes)
    _delete(db, [cid for cid in plan.merges if cid not in merged_children])
    db.expire_all()


def _delete(db: Session, ids: list[UUID]) -> None:
    """Their transactions go back to categorise; their rules and plan targets go (cascade)."""
    for cid in ids:
        db.execute(
            update(Transaction).where(Transaction.category_id == cid).values(category_id=None)
        )
        db.execute(delete_rows(Category).where(Category.id == cid))
    db.flush()
