from uuid import UUID, uuid4

from hypothesis import given
from hypothesis import strategies as st
from kwak_core.categories import (
    DEFAULT_CATEGORIES,
    CategoryKind,
    Existing,
    RestorePlan,
    plan_restore,
)
from kwak_core.users import Language

E, INC = CategoryKind.EXPENSE, CategoryKind.INCOME


def cat(name: str, parent: Existing | None = None, kind: CategoryKind = E) -> Existing:
    return Existing(uuid4(), parent.id if parent else None, name, kind)


def defaults(language: Language) -> list[Existing]:
    """A household freshly seeded in `language`."""
    result = []
    for default in DEFAULT_CATEGORIES:
        parent = cat(default.name(language), kind=default.kind)
        result.append(parent)
        result += [cat(c.name(language), parent, default.kind) for c in default.children]
    return result


def by_name(categories: list[Existing], name: str) -> Existing:
    return next(c for c in categories if c.name == name)


def test_a_household_with_the_defaults_has_nothing_to_restore() -> None:
    plan = plan_restore(defaults(Language.EN), Language.EN)
    assert (plan.creates, plan.renames, plan.moves, plan.merges, plan.deletes) == (
        [],
        {},
        {},
        {},
        [],
    )


def test_the_categories_you_created_are_deleted_children_first() -> None:
    existing = defaults(Language.EN)
    mine = cat("Pets")
    vet = cat("Vet", mine)
    salary_bonus = cat("Bonus", by_name(existing, "Income"), INC)
    plan = plan_restore([*existing, mine, vet, salary_bonus], Language.EN)
    assert plan.deletes == [vet.id, salary_bonus.id, mine.id]


def test_missing_defaults_are_created() -> None:
    existing = [
        c
        for c in defaults(Language.EN)
        if c.name not in {"Groceries", "Leisure", "Sports", "Culture", "Holidays"}
    ]
    plan = plan_restore(existing, Language.EN)
    # Top-level categories first, so subcategories can point at them.
    assert [(c.name, c.parent) for c in plan.creates] == [
        ("Leisure", None),
        ("Groceries", by_name(existing, "Food").id),
        ("Sports", "Leisure"),
        ("Culture", "Leisure"),
        ("Holidays", "Leisure"),
    ]


def test_in_french_the_defaults_are_renamed_and_keep_their_transactions() -> None:
    existing = defaults(Language.EN)
    plan = plan_restore(existing, Language.FR)
    assert plan.renames[by_name(existing, "Groceries").id] == "Courses"
    assert plan.renames[by_name(existing, "Housing").id] == "Logement"
    assert plan.renames[by_name(existing, "Courses").id] == "Formations"  # Education's
    assert "Restaurants" not in plan.renames.values()  # same name in both languages
    assert (plan.creates, plan.deletes) == ([], [])


def test_courses_means_groceries_under_food_and_lessons_under_education() -> None:
    existing = defaults(Language.FR)
    plan = plan_restore(existing, Language.EN)
    food, education = by_name(existing, "Alimentation"), by_name(existing, "Éducation")
    groceries = next(c for c in existing if c.name == "Courses" and c.parent == food.id)
    assert plan.renames[groceries.id] == "Groceries"
    lessons = next(c for c in existing if c.name == "Formations" and c.parent == education.id)
    assert plan.renames[lessons.id] == "Courses"


def test_a_category_you_created_twice_is_merged_into_the_default() -> None:
    """A "courses" made by hand next to the seeded "Groceries": one category, nothing lost."""
    existing = defaults(Language.EN)
    mine = cat("courses", by_name(existing, "Food"))
    plan = plan_restore([*existing, mine], Language.FR)
    # The one already named as wanted is kept; the other merges into it.
    assert plan.merges == {by_name(existing, "Groceries").id: mine.id}  # gone -> kept
    assert plan.renames[mine.id] == "Courses"
    assert mine.id not in plan.deletes


def test_a_default_subcategory_moved_elsewhere_goes_back_to_its_parent() -> None:
    existing = defaults(Language.EN)
    mine = cat("Kitchen")
    groceries = by_name(existing, "Groceries")
    moved = Existing(groceries.id, mine.id, "Groceries", E)
    existing = [c for c in existing if c.id != groceries.id] + [mine, moved]
    plan = plan_restore(existing, Language.EN)
    assert plan.moves == {groceries.id: by_name(existing, "Food").id}
    assert plan.deletes == [mine.id]


def test_kinds_must_match() -> None:
    existing = [c for c in defaults(Language.EN) if c.name != "Salary"]
    wrong = cat("Salary", by_name(existing, "Food"))  # an expense named like the income default
    plan = plan_restore([*existing, wrong], Language.EN)
    assert wrong.id in plan.deletes
    assert ("Salary", by_name(existing, "Income").id) in [(c.name, c.parent) for c in plan.creates]


names = st.sampled_from(
    [
        "Food",
        "Alimentation",
        "Groceries",
        "Courses",
        "courses",
        "Formations",
        "Pets",
        "Vet",
        "Income",
        "Salary",
    ]
)


@given(
    st.lists(st.tuples(names, st.booleans(), st.integers(0, 5)), max_size=12),
    st.sampled_from(Language),
)
def test_restoring_twice_changes_nothing_the_second_time(
    rows: list[tuple[str, bool, int]], language: Language
) -> None:
    """Applying a restore, then planning another, finds nothing to do."""
    existing: list[Existing] = []
    for name, income, parent_index in rows:
        tops = [c for c in existing if c.parent is None]
        parent = tops[parent_index % len(tops)] if tops and parent_index else None
        kind = parent.kind if parent else (INC if income else E)
        siblings = {c.name.lower() for c in existing if c.parent == (parent.id if parent else None)}
        if name.lower() not in siblings:
            existing.append(cat(name, parent, kind))
    after = apply(existing, plan_restore(existing, language))
    second = plan_restore(after, language)
    assert (second.creates, second.renames, second.moves, second.merges, second.deletes) == (
        [],
        {},
        {},
        {},
        [],
    )
    # Sibling names stay unique, any case.
    keys = [(c.parent, c.name.lower()) for c in after]
    assert len(keys) == len(set(keys))


def apply(existing: list[Existing], plan: RestorePlan) -> list[Existing]:
    """What the service does with a plan, on plain data."""
    current = {c.id: c for c in existing}
    created: dict[str, UUID] = {}

    def resolve(parent: UUID | str | None) -> UUID | None:
        return created[parent] if isinstance(parent, str) else parent

    for new in [c for c in plan.creates if c.parent is None]:
        uid = uuid4()
        current[uid] = Existing(uid, None, new.name, new.kind)
        created[new.key] = uid
    for gone in plan.merges:
        del current[gone]
    for cid, name in plan.renames.items():
        c = current[cid]
        current[cid] = Existing(c.id, c.parent, name, c.kind)
    for cid, parent in plan.moves.items():
        c = current[cid]
        current[cid] = Existing(c.id, resolve(parent), c.name, c.kind)
    for new in [c for c in plan.creates if c.parent is not None]:
        uid = uuid4()
        current[uid] = Existing(uid, resolve(new.parent), new.name, new.kind)
    for cid in plan.deletes:
        del current[cid]
    return list(current.values())
