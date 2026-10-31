from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from hypothesis import given
from hypothesis import strategies as st
from kwak_core.budget import Month, build_matrix
from kwak_core.progress import (
    DEFAULT_WARN_AT,
    ProgressStatus,
    SavingsStatus,
    check_warn_at,
    month_pace,
    month_progress,
    one_off,
    progress_status,
    savings_progress,
    savings_status,
)

D = Decimal
FOOD, GROCERIES, BAKERY, HOUSING, RENT, LEISURE = (uuid4() for _ in range(6))
CATEGORIES = [
    (FOOD, None, "Food"),
    (GROCERIES, FOOD, "Groceries"),
    (BAKERY, FOOD, "Bakery"),
    (HOUSING, None, "Housing"),
    (RENT, HOUSING, "Rent"),
    (LEISURE, None, "Leisure"),
]
OCT = Month(2026, 10)
LIVRET, PEA, CRYPTO = (uuid4() for _ in range(3))
SAVINGS = [(LIVRET, None, "Livret A"), (PEA, None, "PEA"), (CRYPTO, None, "Crypto")]


@pytest.mark.parametrize(
    ("spent", "target", "status"),
    [
        ("0", "100", ProgressStatus.ON_TRACK),
        ("79.99", "100", ProgressStatus.ON_TRACK),
        ("80", "100", ProgressStatus.WATCH),
        ("100", "100", ProgressStatus.WATCH),
        ("100.01", "100", ProgressStatus.OVER),
        ("-20", "100", ProgressStatus.ON_TRACK),  # refunds above the spending
        ("0", "0", ProgressStatus.ON_TRACK),
        ("1", "0", ProgressStatus.OVER),
    ],
)
def test_the_status_follows_the_share_used(spent: str, target: str, status: ProgressStatus) -> None:
    assert D("0.80") == DEFAULT_WARN_AT
    assert progress_status(D(spent), D(target), DEFAULT_WARN_AT) is status


def test_the_warning_threshold_is_a_setting() -> None:
    assert progress_status(D("60"), D("100"), D("0.50")) is ProgressStatus.WATCH
    assert progress_status(D("99"), D("100"), D("1")) is ProgressStatus.ON_TRACK


@pytest.mark.parametrize(
    ("spent", "status"),
    [
        ("0", ProgressStatus.ON_TRACK),
        ("100", ProgressStatus.ON_TRACK),
        ("100.01", ProgressStatus.OVER),
    ],
)
def test_a_one_off_category_has_no_warning_threshold(spent: str, status: ProgressStatus) -> None:
    assert progress_status(D(spent), D("100"), DEFAULT_WARN_AT, one_off=True) is status


@pytest.mark.parametrize("value", ["0.49", "1.01", "0"])
def test_the_warning_threshold_is_between_50_and_100_percent(value: str) -> None:
    with pytest.raises(ValueError, match="threshold"):
        check_warn_at(D(value))


def test_the_pace_is_the_share_of_the_current_month_elapsed() -> None:
    assert month_pace(OCT, date(2026, 10, 1)) == D(1) / 31
    assert month_pace(OCT, date(2026, 10, 31)) == D(1)
    assert month_pace(Month(2026, 2), date(2026, 2, 14)) == D("0.5")


def test_there_is_no_pace_for_another_month() -> None:
    assert month_pace(OCT, date(2026, 11, 3)) is None
    assert month_pace(OCT, date(2026, 9, 30)) is None


def test_a_subcategory_is_one_off_like_its_parent_unless_it_says_otherwise() -> None:
    assert one_off(own=None, parent=True) is True
    assert one_off(own=False, parent=True) is False
    assert one_off(own=True, parent=None) is True
    assert one_off(own=None, parent=None) is False


def test_the_month_so_far_lists_the_categories_with_a_target_by_share_used() -> None:
    matrix = build_matrix(
        CATEGORIES,
        {FOOD: [(OCT, D("400"))], RENT: [(OCT, D("900"))]},
        {(GROCERIES, OCT): D("300"), (BAKERY, OCT): D("40"), (RENT, OCT): D("900")},
        [OCT],
    )
    lines = month_progress(
        matrix, today=date(2026, 10, 10), settings={HOUSING: True}, warn_at=DEFAULT_WARN_AT
    )

    assert [line.name for line in lines] == ["Rent", "Food"]  # Leisure has no target
    rent, food = lines
    assert (rent.spent, rent.target, rent.remaining) == (D("900"), D("900"), D("0"))
    assert rent.status is ProgressStatus.ON_TRACK  # one-off: paid as planned, nothing to watch
    assert rent.pace is None  # one-off, through its parent
    # A parent's target covers its children.
    assert (food.spent, food.remaining, food.share) == (D("340"), D("60"), D("0.85"))
    assert food.status is ProgressStatus.WATCH
    assert food.pace == D(10) / 31


def test_an_overrun_shows_as_a_negative_remainder() -> None:
    matrix = build_matrix(
        CATEGORIES, {LEISURE: [(OCT, D("100"))]}, {(LEISURE, OCT): D("130")}, [OCT]
    )
    (leisure,) = month_progress(matrix, today=date(2026, 10, 10), settings={}, warn_at=D("0.8"))
    assert leisure.remaining == D("-30")
    assert leisure.status is ProgressStatus.OVER


def test_a_parent_whose_target_comes_from_its_children_is_not_listed_twice() -> None:
    matrix = build_matrix(
        CATEGORIES,
        {GROCERIES: [(OCT, D("300"))], BAKERY: [(OCT, D("50"))]},
        {(GROCERIES, OCT): D("150"), (BAKERY, OCT): D("50")},
        [OCT],
    )
    lines = month_progress(matrix, today=date(2026, 10, 10), settings={}, warn_at=DEFAULT_WARN_AT)
    assert [line.name for line in lines] == ["Bakery", "Groceries"]


def test_a_past_month_has_no_pace() -> None:
    matrix = build_matrix(CATEGORIES, {LEISURE: [(OCT, D("100"))]}, {}, [OCT])
    (leisure,) = month_progress(
        matrix, today=date(2026, 11, 2), settings={}, warn_at=DEFAULT_WARN_AT
    )
    assert leisure.pace is None


# Invariant §8.10: the month so far never disagrees with the matrix.
amounts = st.decimals(-200, 2000, places=2)


@given(
    st.dictionaries(st.sampled_from([c[0] for c in CATEGORIES]), amounts, max_size=6),
    st.dictionaries(st.sampled_from([c[0] for c in CATEGORIES]), st.decimals(0, 2000, places=2)),
    st.decimals(D("0.5"), D("1"), places=2),
)
def test_each_line_is_its_matrix_cell_ranked_by_share_used(
    spending: dict[object, Decimal], targets: dict[object, Decimal], warn_at: Decimal
) -> None:
    matrix = build_matrix(
        CATEGORIES,
        {cid: [(OCT, amount)] for cid, amount in targets.items()},
        {(cid, OCT): amount for cid, amount in spending.items()},
        [OCT],
    )
    lines = month_progress(matrix, today=date(2026, 10, 15), settings={}, warn_at=warn_at)
    cells = {row.category_id: row.cells[0] for row in matrix.rows}
    for line in lines:
        cell = cells[line.category_id]
        assert (line.spent, line.target) == (cell.spent, cell.target)
        assert line.remaining == line.target - line.spent
        assert line.status is progress_status(line.spent, line.target, warn_at)
    keys = [line.rank for line in lines]
    assert keys == sorted(keys, reverse=True)


# The month's savings objectives (F-BUD-2, F-BUD-9)


@pytest.mark.parametrize(
    ("saved", "objective", "status"),
    [
        ("0", "100", SavingsStatus.IN_PROGRESS),
        ("99.99", "100", SavingsStatus.IN_PROGRESS),
        ("100", "100", SavingsStatus.REACHED),
        ("150", "100", SavingsStatus.REACHED),
        ("-20", "100", SavingsStatus.IN_PROGRESS),  # more taken back than put aside
        ("0", "0", SavingsStatus.REACHED),
        ("-1", "0", SavingsStatus.IN_PROGRESS),
    ],
)
def test_an_objective_is_reached_once_saved(
    saved: str, objective: str, status: SavingsStatus
) -> None:
    assert savings_status(D(saved), D(objective)) is status


def test_the_savings_lines_list_the_objectives_furthest_from_reached_first() -> None:
    matrix = build_matrix(
        CATEGORIES,
        {LIVRET: [(OCT, D("200"))], PEA: [(OCT, D("500"))], LEISURE: [(OCT, D("100"))]},
        {(LIVRET, OCT): D("250"), (PEA, OCT): D("100"), (CRYPTO, OCT): D("50")},
        [OCT],
        savings=SAVINGS,
    )
    lines = savings_progress(matrix)

    assert [line.name for line in lines] == ["PEA", "Livret A"]  # Crypto has no objective
    pea, livret = lines
    assert (pea.saved, pea.objective, pea.remaining, pea.share) == (
        D("100"),
        D("500"),
        D("400"),
        D("0.2"),
    )
    assert pea.status is SavingsStatus.IN_PROGRESS
    assert (livret.remaining, livret.share) == (D("-50"), D("1.25"))  # 50 beyond
    assert livret.status is SavingsStatus.REACHED


# Invariant §8.10 for the savings: each line is its matrix cell.
@given(
    st.dictionaries(st.sampled_from([c[0] for c in SAVINGS]), amounts, max_size=3),
    st.dictionaries(st.sampled_from([c[0] for c in SAVINGS]), st.decimals(0, 2000, places=2)),
)
def test_each_savings_line_is_its_matrix_cell(
    saved: dict[object, Decimal], objectives: dict[object, Decimal]
) -> None:
    matrix = build_matrix(
        [],
        {cid: [(OCT, amount)] for cid, amount in objectives.items()},
        {(cid, OCT): amount for cid, amount in saved.items()},
        [OCT],
        savings=SAVINGS,
    )
    lines = savings_progress(matrix)
    cells = {row.category_id: row.cells[0] for row in matrix.savings}
    assert {line.category_id for line in lines} == set(objectives)
    for line in lines:
        cell = cells[line.category_id]
        assert (line.saved, line.objective) == (cell.spent, cell.target)
        assert line.remaining == line.objective - line.saved
        assert line.status is savings_status(line.saved, line.objective)
    keys = [line.rank for line in lines]
    assert keys == sorted(keys)
