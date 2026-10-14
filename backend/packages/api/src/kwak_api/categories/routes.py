from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from kwak_core.audit import AuditAction
from kwak_core.categories import CategoryKind, HierarchyError
from kwak_core.users import Language
from pydantic import BaseModel, Field

from kwak_api.auth.routes import CurrentSession, Db, Now
from kwak_api.household.routes import OwnerSession
from kwak_api.models import Category
from kwak_api.services import audit
from kwak_api.services import categories as service
from kwak_api.services.budget import core_plan

router = APIRouter(prefix="/api", tags=["categories"])

NOT_FOUND = HTTPException(status.HTTP_404_NOT_FOUND, "category not found")
DUPLICATE = HTTPException(status.HTTP_409_CONFLICT, "a sibling category already has this name")


class CategoryOut(BaseModel):
    id: UUID
    name: str
    kind: CategoryKind
    parent_id: UUID | None
    shift_day: int | None
    """From this day of the month, its transactions count for the next month (F-CAT-5). null:
    no setting of its own (a subcategory follows its parent's); 0: never shifted."""
    one_off: bool | None
    """Paid once in the month, so never judged against the month's pace (F-CAT-6). null: no
    setting of its own (a subcategory follows its parent's)."""

    @classmethod
    def of(cls, category: Category) -> "CategoryOut":
        return cls(
            id=category.id,
            name=category.name,
            kind=category.kind,
            parent_id=category.parent_id,
            shift_day=category.shift_day,
            one_off=category.one_off,
        )


class CategoryIn(BaseModel):
    name: str
    kind: CategoryKind = CategoryKind.EXPENSE
    """Ignored for a subcategory: it takes its parent's kind."""
    parent_id: UUID | None = None


class CategoryPatch(BaseModel):
    """`parent_id: null` moves the category to the top level; leave it out to keep its place."""

    name: str | None = None
    parent_id: UUID | None = None
    shift_day: int | None = None
    """0-31; null removes the category's own setting. Leave it out to keep it."""
    one_off: bool | None = None
    """Expense categories only; null removes the category's own setting. Leave it out to keep
    it."""


class ShiftPreviewOut(BaseModel):
    """What setting a category's shift day would change (F-CAT-5)."""

    moved: int
    """Transactions that would change budget month."""
    months: list[str]
    """YYYY-MM: every month that gains or loses one."""
    locked_plans: list[str]
    """Periods of the plans past their first month whose review would change."""


def _parent(db: Db, household_id: UUID, parent_id: UUID | None) -> Category | None:
    if parent_id is None:
        return None
    parent = service.find(db, household_id, parent_id)
    if parent is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "unknown parent category")
    return parent


@router.get("/categories")
def list_categories(user_session: CurrentSession, db: Db) -> list[CategoryOut]:
    """Parents first, each followed by its subcategories."""
    return [CategoryOut.of(c) for c in service.tree(db, user_session.user.household_id)]


@router.post("/categories", status_code=status.HTTP_201_CREATED)
def create_category(body: CategoryIn, user_session: CurrentSession, db: Db) -> CategoryOut:
    household_id = user_session.user.household_id
    try:
        category = service.create(
            db,
            household_id,
            name=body.name,
            kind=body.kind,
            parent=_parent(db, household_id, body.parent_id),
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None
    except service.DuplicateCategoryError:
        raise DUPLICATE from None
    return CategoryOut.of(category)


@router.patch("/categories/{category_id}")
def update_category(
    category_id: UUID, body: CategoryPatch, user_session: CurrentSession, db: Db
) -> CategoryOut:
    household_id = user_session.user.household_id
    category = service.find(db, household_id, category_id)
    if category is None:
        raise NOT_FOUND
    move = "parent_id" in body.model_fields_set
    try:
        service.update_category(
            db,
            category,
            name=body.name,
            parent=_parent(db, household_id, body.parent_id) if move else None,
            move=move,
            shift=(body.shift_day,) if "shift_day" in body.model_fields_set else None,
            one_off=(body.one_off,) if "one_off" in body.model_fields_set else None,
        )
    except (ValueError, HierarchyError) as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None
    except service.DuplicateCategoryError:
        raise DUPLICATE from None
    return CategoryOut.of(category)


@router.get("/categories/{category_id}/shift-preview")
def preview_shift(
    category_id: UUID,
    user_session: CurrentSession,
    db: Db,
    now: Now,
    day: Annotated[int | None, Query(ge=0, le=31, description="Leave out to remove it")] = None,
) -> ShiftPreviewOut:
    """What setting the category's shift day to `day` would change, without changing it."""
    category = service.find(db, user_session.user.household_id, category_id)
    if category is None:
        raise NOT_FOUND
    preview = service.shift_preview(db, user_session.user, category, day, now.date())
    return ShiftPreviewOut(
        moved=preview.moved,
        months=[str(m) for m in preview.months],
        locked_plans=[str(core_plan(p).period) for p in preview.locked_plans],
    )


@router.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(category_id: UUID, user_session: CurrentSession, db: Db, now: Now) -> None:
    """Its transactions go back to "to categorise"."""
    category = service.find(db, user_session.user.household_id, category_id)
    if category is None:
        raise NOT_FOUND
    name = category.name
    try:
        service.delete(db, category)
    except service.CategoryInUseError:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "move or delete its subcategories first"
        ) from None
    audit.record(db, user_session.user, AuditAction.CATEGORY_DELETED, now, name=name)


class RenameOut(BaseModel):
    from_: str = Field(alias="from", serialization_alias="from")
    to: str


class RestoreOut(BaseModel):
    """What restoring the default categories does (GET) or did (POST)."""

    language: Language
    """The language of the default names: the requesting user's."""
    created: list[str]
    renamed: list[RenameOut]
    merged: list[RenameOut]
    """Duplicates of a default, merged with their transactions, rules and plan targets."""
    moved: list[str]
    """Default subcategories moved back under their default parent."""
    deleted: list[str]
    """Categories that are not defaults."""
    transactions_to_categorise: int
    rules_deleted: int
    plan_targets_deleted: int
    locked_plans_affected: int
    """Plans past their first month that lose a target: their review changes."""

    @classmethod
    def of(cls, summary: service.RestoreSummary) -> "RestoreOut":
        return cls(
            language=summary.language,
            created=summary.created,
            renamed=[RenameOut(**{"from": a, "to": b}) for a, b in summary.renamed],
            merged=[RenameOut(**{"from": a, "to": b}) for a, b in summary.merged],
            moved=summary.moved,
            deleted=summary.deleted,
            transactions_to_categorise=summary.transactions_to_categorise,
            rules_deleted=summary.rules_deleted,
            plan_targets_deleted=summary.plan_targets_deleted,
            locked_plans_affected=summary.locked_plans_affected,
        )


def _restore(user_session: OwnerSession, db: Db, now: Now, *, apply: bool) -> RestoreOut:
    user = user_session.user
    summary = service.restore_defaults(
        db, user.household_id, user.language or Language.EN, now.date(), apply=apply
    )
    if apply:
        audit.record(
            db,
            user,
            AuditAction.CATEGORIES_RESTORED,
            now,
            created=len(summary.created),
            merged=len(summary.merged),
            deleted=len(summary.deleted),
        )
    return RestoreOut.of(summary)


@router.get("/categories/restore")
def preview_restore(user_session: OwnerSession, db: Db, now: Now) -> RestoreOut:
    """What restoring the default categories would do, without changing anything."""
    return _restore(user_session, db, now, apply=False)


@router.post("/categories/restore")
def restore_defaults(user_session: OwnerSession, db: Db, now: Now) -> RestoreOut:
    """Restore the default categories, named in the owner's language (owner only).

    Defaults found are kept (renamed, moved back) with their transactions, rules and plan
    targets; duplicates merge into them; missing ones are created; every other category is
    deleted: its transactions go back to "to categorise", its rules and plan targets go.
    """
    return _restore(user_session, db, now, apply=True)
