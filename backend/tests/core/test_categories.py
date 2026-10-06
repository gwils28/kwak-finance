from collections import Counter

import pytest
from kwak_core.categories import DEFAULT_CATEGORIES, CategoryKind, HierarchyError, check_hierarchy


def test_the_default_tree_has_two_levels_and_both_kinds() -> None:
    kinds = {parent.kind for parent in DEFAULT_CATEGORIES}
    assert kinds == {CategoryKind.EXPENSE, CategoryKind.INCOME}
    assert all(
        parent.children for parent in DEFAULT_CATEGORIES if parent.kind is CategoryKind.EXPENSE
    )


def test_default_names_are_unique_among_siblings() -> None:
    parents = Counter(p.name.lower() for p in DEFAULT_CATEGORIES)
    assert max(parents.values()) == 1
    for parent in DEFAULT_CATEGORIES:
        children = Counter(c.lower() for c in parent.children)
        assert not children or max(children.values()) == 1


def test_a_top_level_category_is_always_valid() -> None:
    check_hierarchy(parent=None, has_children=True)


def test_a_child_goes_under_a_top_level_category() -> None:
    check_hierarchy(
        parent=(None, CategoryKind.EXPENSE), has_children=False, kind=CategoryKind.EXPENSE
    )


@pytest.mark.parametrize(
    ("parent", "has_children", "kind", "message"),
    [
        (("some-parent", CategoryKind.EXPENSE), False, CategoryKind.EXPENSE, "two levels"),
        ((None, CategoryKind.EXPENSE), True, CategoryKind.EXPENSE, "two levels"),
        ((None, CategoryKind.INCOME), False, CategoryKind.EXPENSE, "same kind"),
    ],
)
def test_invalid_hierarchies_are_rejected(
    parent: tuple[str | None, CategoryKind], has_children: bool, kind: CategoryKind, message: str
) -> None:
    with pytest.raises(HierarchyError, match=message):
        check_hierarchy(parent=parent, has_children=has_children, kind=kind)
