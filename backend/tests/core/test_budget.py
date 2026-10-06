from decimal import Decimal
from uuid import uuid4

import pytest
from hypothesis import given
from hypothesis import strategies as st
from kwak_core.budget import (
    BudgetStatus,
    Month,
    budget_status,
    build_matrix,
    month_range,
    target_for,
)

D = Decimal
FOOD, GROCERIES, BAKERY, HOUSING = uuid4(), uuid4(), uuid4(), uuid4()
CATEGORIES = [
    (FOOD, None, "Food"),
    (GROCERIES, FOOD, "Groceries"),
    (BAKERY, FOOD, "Bakery"),
    (HOUSING, None, "Housing"),
]
JAN, FEB, MAR = Month(2026, 1), Month(2026, 2), Month(2026, 3)


@pytest.mark.parametrize(
    ("spent", "target", "status"),
    [
        ("94.99", "100", BudgetStatus.UNDER),
        ("95.00", "100", BudgetStatus.ON),
        ("100", "100", BudgetStatus.ON),
        ("105.00", "100", BudgetStatus.ON),
        ("105.01", "100", BudgetStatus.OVER),
        ("0", "0", BudgetStatus.ON),
        ("1", "0", BudgetStatus.OVER),
        ("50", None, BudgetStatus.NONE),
    ],
)
def test_status_uses_a_5_percent_band(spent: str, target: str | None, status: BudgetStatus) -> None:
    assert budget_status(D(spent), None if target is None else D(target)) is status


def test_the_band_is_a_setting() -> None:
    assert budget_status(D("108"), D("100"), band=D("0.10")) is BudgetStatus.ON


def test_month_range_is_inclusive_and_crosses_years() -> None:
    assert month_range(Month(2025, 11), Month(2026, 2)) == [
        Month(2025, 11),
        Month(2025, 12),
        Month(2026, 1),
        Month(2026, 2),
    ]


def test_a_target_applies_from_its_month_until_changed() -> None:
    history = [(JAN, D("400")), (MAR, D("450"))]
    assert target_for(history, Month(2025, 12)) is None
    assert target_for(history, JAN) == D("400")
    assert target_for(history, FEB) == D("400")
    assert target_for(history, MAR) == D("450")
    assert target_for([(JAN, D("400")), (FEB, None)], MAR) is None  # removed


def _matrix(
    spending: dict[tuple[object, Month], Decimal],
    targets: dict[object, list[tuple[Month, Decimal | None]]],
):  # type: ignore[no-untyped-def]
    return build_matrix(CATEGORIES, targets, spending, [JAN, FEB, MAR])


def test_a_cell_shows_spending_gap_in_euros_and_percent_and_status() -> None:
    matrix = _matrix({(GROCERIES, JAN): D("440")}, {GROCERIES: [(JAN, D("400"))]})
    cell = next(r for r in matrix.rows if r.category_id == GROCERIES).cells[0]
    assert (cell.spent, cell.target, cell.gap, cell.gap_ratio) == (
        D("440"),
        D("400"),
        D("40"),
        D("0.1"),
    )
    assert cell.status is BudgetStatus.OVER


def test_a_parent_adds_its_children_and_uses_their_targets_unless_it_has_one() -> None:
    spending = {(GROCERIES, JAN): D("300"), (BAKERY, JAN): D("50"), (FOOD, JAN): D("10")}
    children_only = _matrix(spending, {GROCERIES: [(JAN, D("300"))], BAKERY: [(JAN, D("60"))]})
    food = next(r for r in children_only.rows if r.category_id == FOOD)
    assert (food.cells[0].spent, food.cells[0].target) == (D("360"), D("360"))
    own = _matrix(spending, {FOOD: [(JAN, D("500"))], GROCERIES: [(JAN, D("300"))]})
    assert next(r for r in own.rows if r.category_id == FOOD).cells[0].target == D("500")


def test_rows_come_parent_first_then_children() -> None:
    matrix = _matrix({}, {})
    assert [(r.name, r.level) for r in matrix.rows] == [
        ("Food", 0),
        ("Bakery", 1),
        ("Groceries", 1),
        ("Housing", 0),
    ]


def test_uncategorised_spending_has_its_own_row_and_counts_in_the_total() -> None:
    matrix = _matrix({(None, FEB): D("25"), (HOUSING, FEB): D("700")}, {})
    assert matrix.uncategorised.cells[1].spent == D("25")
    assert matrix.total.cells[1].spent == D("725")


amounts = st.integers(min_value=-500_00, max_value=5_000_00).map(lambda c: Decimal(c) / 100)
spending_strategy = st.dictionaries(
    st.tuples(
        st.sampled_from([FOOD, GROCERIES, BAKERY, HOUSING, None]), st.sampled_from([JAN, FEB, MAR])
    ),
    amounts,
    max_size=15,
)


@given(spending_strategy)
def test_the_total_row_is_every_top_level_row_plus_uncategorised(spending: dict) -> None:  # type: ignore[type-arg]
    matrix = _matrix(spending, {})
    for i, month in enumerate([JAN, FEB, MAR]):
        top = sum((r.cells[i].spent for r in matrix.rows if r.level == 0), Decimal(0))
        assert matrix.total.cells[i].spent == top + matrix.uncategorised.cells[i].spent
        assert matrix.total.cells[i].spent == sum(
            (v for (_, m), v in spending.items() if m == month), Decimal(0)
        )


def test_the_total_target_is_the_sum_of_top_level_targets() -> None:
    matrix = _matrix({}, {GROCERIES: [(JAN, D("400"))], HOUSING: [(JAN, D("800"))]})
    assert matrix.total.target == D("1200")
    assert _matrix({}, {}).total.target is None


def test_a_row_says_when_its_target_is_its_childrens_sum() -> None:
    children = _matrix({}, {GROCERIES: [(JAN, D("300"))]})
    food = next(r for r in children.rows if r.category_id == FOOD)
    assert (food.target, food.target_from_children) == (D("300"), True)
    own = _matrix({}, {FOOD: [(JAN, D("500"))]})
    assert next(r for r in own.rows if r.category_id == FOOD).target_from_children is False
