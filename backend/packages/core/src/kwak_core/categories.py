"""Two-level category tree (F-CAT-1)."""

import enum
from collections.abc import Sequence
from dataclasses import dataclass, field
from uuid import UUID

from kwak_core.users import Language


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
class Names:
    """A default category's name in each interface language."""

    en: str
    fr: str

    def name(self, language: Language) -> str:
        return self.fr if language is Language.FR else self.en

    def matches(self, name: str) -> bool:
        return name.lower() in {self.en.lower(), self.fr.lower()}


@dataclass(frozen=True)
class DefaultCategory:
    names: Names
    kind: CategoryKind
    children: tuple[Names, ...] = field(default=())

    def name(self, language: Language) -> str:
        return self.names.name(language)


_E, _I, N = CategoryKind.EXPENSE, CategoryKind.INCOME, Names

# Seeded for every new household; everything can be renamed, moved or deleted.
DEFAULT_CATEGORIES: tuple[DefaultCategory, ...] = (
    DefaultCategory(
        N("Housing", "Logement"),
        _E,
        (
            N("Rent or mortgage", "Loyer ou crédit"),
            N("Utilities", "Énergie et eau"),
            N("Home insurance", "Assurance habitation"),
            N("Repairs", "Travaux et réparations"),
        ),
    ),
    DefaultCategory(
        N("Food", "Alimentation"),
        _E,
        (
            N("Groceries", "Courses"),
            N("Restaurants", "Restaurants"),
            N("Bakery and coffee", "Boulangerie et café"),
        ),
    ),
    DefaultCategory(
        N("Transport", "Transport"),
        _E,
        (
            N("Fuel", "Carburant"),
            N("Public transport", "Transports en commun"),
            N("Car", "Voiture"),
            N("Parking and tolls", "Parking et péages"),
        ),
    ),
    DefaultCategory(
        N("Health", "Santé"),
        _E,
        (N("Pharmacy", "Pharmacie"), N("Doctors", "Médecins"), N("Health insurance", "Mutuelle")),
    ),
    DefaultCategory(
        N("Subscriptions", "Abonnements"),
        _E,
        (
            N("Phone and internet", "Téléphone et internet"),
            N("Streaming", "Streaming"),
            N("Other subscriptions", "Autres abonnements"),
        ),
    ),
    DefaultCategory(
        N("Shopping", "Achats"),
        _E,
        (
            N("Clothing", "Vêtements"),
            N("Electronics", "Électronique"),
            N("Home and garden", "Maison et jardin"),
        ),
    ),
    DefaultCategory(
        N("Leisure", "Loisirs"),
        _E,
        (N("Sports", "Sport"), N("Culture", "Culture"), N("Holidays", "Vacances")),
    ),
    DefaultCategory(
        N("Personal", "Personnel"),
        _E,
        (N("Hair and care", "Coiffure et soins"), N("Gifts", "Cadeaux"), N("Donations", "Dons")),
    ),
    DefaultCategory(
        N("Education", "Éducation"), _E, (N("Courses", "Formations"), N("Books", "Livres"))
    ),
    DefaultCategory(
        N("Finance", "Finances"),
        _E,
        (
            N("Bank fees", "Frais bancaires"),
            N("Taxes", "Impôts"),
            N("Cash withdrawals", "Retraits d'espèces"),
        ),
    ),
    DefaultCategory(
        N("Income", "Revenus"),
        _I,
        (
            N("Salary", "Salaire"),
            N("Refunds", "Remboursements"),
            N("Interest", "Intérêts"),
            N("Other income", "Autres revenus"),
        ),
    ),
)


@dataclass(frozen=True)
class Existing:
    """A household category, as the restore sees it."""

    id: UUID
    parent: UUID | None
    name: str
    kind: CategoryKind


@dataclass(frozen=True)
class NewCategory:
    key: str
    """The English default name, so subcategories can point at a parent created alongside."""
    name: str
    kind: CategoryKind
    parent: UUID | str | None
    """An existing category, the key of a new one, or None for a top-level category."""


@dataclass
class RestorePlan:
    """How to bring a household's categories back to the defaults, keeping what can be kept.

    The service applies it in this order: create the missing top-level categories, merge,
    rename, move, create the missing subcategories, then delete (subcategories first).
    """

    creates: list[NewCategory] = field(default_factory=list)
    merges: dict[UUID, UUID] = field(default_factory=dict)
    """Duplicate -> the category it merges into (transactions, rules and plan targets move)."""
    renames: dict[UUID, str] = field(default_factory=dict)
    moves: dict[UUID, UUID | str] = field(default_factory=dict)
    deletes: list[UUID] = field(default_factory=list)
    """Categories that are not defaults: subcategories first."""


def _pick(candidates: list[Existing], wanted: str) -> Existing:
    """The category to keep among those matching one default: best if already named so."""
    return (
        next((c for c in candidates if c.name == wanted), None)
        or next((c for c in candidates if c.name.lower() == wanted.lower()), None)
        or candidates[0]
    )


def plan_restore(existing: Sequence[Existing], language: Language) -> RestorePlan:
    """Match the categories with the defaults, by name in any language and by kind.

    A default found once is kept (renamed into `language`, moved back under its parent); found
    several times, the copies merge into one; missing, it is created. Every other category is
    deleted. A subcategory that has children of its own is never taken for a default one.
    """
    plan = RestorePlan()
    claimed: set[UUID] = set()
    parent_of_default: dict[UUID, int] = {}
    targets: list[UUID | str] = []

    def keep(candidates: list[Existing], names: Names) -> Existing:
        kept = _pick(candidates, names.name(language))
        for other in candidates:
            if other is not kept:
                plan.merges[other.id] = kept.id
        if kept.name != names.name(language):
            plan.renames[kept.id] = names.name(language)
        claimed.update(c.id for c in candidates)
        return kept

    for i, default in enumerate(DEFAULT_CATEGORIES):
        found = [
            c
            for c in existing
            if c.parent is None and c.kind is default.kind and default.names.matches(c.name)
        ]
        if found:
            targets.append(keep(found, default.names).id)
            parent_of_default.update((c.id, i) for c in found)
        else:
            key = default.names.en
            plan.creates.append(NewCategory(key, default.name(language), default.kind, None))
            targets.append(key)

    with_children = {c.parent for c in existing if c.parent is not None}
    assigned: dict[tuple[int, int], list[Existing]] = {}
    for c in existing:
        if c.id in claimed or c.id in with_children:
            continue
        options = [
            (i, j)
            for i, default in enumerate(DEFAULT_CATEGORIES)
            if default.kind is c.kind
            for j, child in enumerate(default.children)
            if child.matches(c.name)
        ]
        if not options:
            continue
        # "Courses" is Groceries under Food and lessons under Education: the parent decides,
        # then the name in the wanted language.
        home = parent_of_default.get(c.parent) if c.parent else None
        options.sort(
            key=lambda o: (
                o[0] != home,
                DEFAULT_CATEGORIES[o[0]].children[o[1]].name(language).lower() != c.name.lower(),
            )
        )
        assigned.setdefault(options[0], []).append(c)

    for i, default in enumerate(DEFAULT_CATEGORIES):
        for j, child in enumerate(default.children):
            found = assigned.get((i, j), [])
            if found:
                kept = keep(found, child)
                if kept.parent != targets[i]:
                    plan.moves[kept.id] = targets[i]
            else:
                key = f"{default.names.en}/{child.en}"
                plan.creates.append(
                    NewCategory(key, child.name(language), default.kind, targets[i])
                )

    rest = [c for c in existing if c.id not in claimed]
    plan.deletes = [c.id for c in rest if c.parent is not None] + [
        c.id for c in rest if c.parent is None
    ]
    return plan
