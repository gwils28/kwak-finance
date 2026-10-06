"""Two-level category tree (F-CAT-1)."""

import enum
from dataclasses import dataclass, field


class CategoryKind(enum.StrEnum):
    EXPENSE = "expense"
    INCOME = "income"


class HierarchyError(ValueError):
    pass


def check_hierarchy(
    *,
    parent: tuple[object | None, CategoryKind] | None,
    has_children: bool,
    kind: CategoryKind | None = None,
) -> None:
    """Validate placing a category under `parent` (its own parent id and kind), or at the top.

    Categories have two levels: a parent cannot itself have a parent, and a category with
    children stays at the top. A child has its parent's kind.
    """
    if parent is None:
        return
    grandparent, parent_kind = parent
    if grandparent is not None or has_children:
        raise HierarchyError("categories have two levels: a subcategory cannot have children")
    if kind is not None and kind is not parent_kind:
        raise HierarchyError("a subcategory has the same kind as its parent")


@dataclass(frozen=True)
class DefaultCategory:
    name: str
    kind: CategoryKind
    children: tuple[str, ...] = field(default=())


_E, _I = CategoryKind.EXPENSE, CategoryKind.INCOME

# Seeded for every new household; everything can be renamed, moved or deleted.
DEFAULT_CATEGORIES: tuple[DefaultCategory, ...] = (
    DefaultCategory("Housing", _E, ("Rent or mortgage", "Utilities", "Home insurance", "Repairs")),
    DefaultCategory("Food", _E, ("Groceries", "Restaurants", "Bakery and coffee")),
    DefaultCategory("Transport", _E, ("Fuel", "Public transport", "Car", "Parking and tolls")),
    DefaultCategory("Health", _E, ("Pharmacy", "Doctors", "Health insurance")),
    DefaultCategory(
        "Subscriptions", _E, ("Phone and internet", "Streaming", "Other subscriptions")
    ),
    DefaultCategory("Shopping", _E, ("Clothing", "Electronics", "Home and garden")),
    DefaultCategory("Leisure", _E, ("Sports", "Culture", "Holidays")),
    DefaultCategory("Personal", _E, ("Hair and care", "Gifts", "Donations")),
    DefaultCategory("Education", _E, ("Courses", "Books")),
    DefaultCategory("Finance", _E, ("Bank fees", "Taxes", "Cash withdrawals")),
    DefaultCategory("Income", _I, ("Salary", "Refunds", "Interest", "Other income")),
)
