from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from kwak_core.categories import CategoryKind, HierarchyError
from pydantic import BaseModel

from kwak_api.auth.routes import CurrentSession, Db
from kwak_api.models import Category
from kwak_api.services import categories as service

router = APIRouter(prefix="/api", tags=["categories"])

NOT_FOUND = HTTPException(status.HTTP_404_NOT_FOUND, "category not found")
DUPLICATE = HTTPException(status.HTTP_409_CONFLICT, "a sibling category already has this name")


class CategoryOut(BaseModel):
    id: UUID
    name: str
    kind: CategoryKind
    parent_id: UUID | None

    @classmethod
    def of(cls, category: Category) -> "CategoryOut":
        return cls(
            id=category.id, name=category.name, kind=category.kind, parent_id=category.parent_id
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
        )
    except (ValueError, HierarchyError) as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None
    except service.DuplicateCategoryError:
        raise DUPLICATE from None
    return CategoryOut.of(category)


@router.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(category_id: UUID, user_session: CurrentSession, db: Db) -> None:
    """Its transactions go back to "to categorise"."""
    category = service.find(db, user_session.user.household_id, category_id)
    if category is None:
        raise NOT_FOUND
    try:
        service.delete(db, category)
    except service.CategoryInUseError:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "move or delete its subcategories first"
        ) from None
