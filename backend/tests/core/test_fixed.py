from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from hypothesis import given
from hypothesis import strategies as st
from kwak_core.budget import Month
from kwak_core.fixed import (
    FixedExpense,
    FixedFrequency,
    FixedStatus,
    LineRef,
    due_date,
    is_due,
    monthly_equivalent,
    occurrences,
    projected_rest,
)

D = Decimal
HOUSING, KIDS, SAVINGS = uuid4(), uuid4(), uuid4()
OCT, JANUARY = Month(2026, 10), Month(2026, 1)


def fixed(
    label: str = "Loyer",
    category: UUID = HOUSING,
    amount: str = "-950.00",
    frequency: FixedFrequency = FixedFrequency.MONTHLY,
    day: int = 1,
    first: Month = JANUARY,
    last: Month | None = None,
    paused: bool = False,
) -> FixedExpense:
    return FixedExpense(uuid4(), label, category, D(amount), frequency, day, first, last, paused)


def line(label: str, category: UUID, day: int, item: UUID | None = None) -> LineRef:
    return LineRef(uuid4(), label, category, date(2026, 10, day), item)


@pytest.mark.parametrize(
    ("frequency", "first", "month", "due"),
    [
        (FixedFrequency.MONTHLY, Month(2026, 1), OCT, True),
        (FixedFrequency.MONTHLY, Month(2026, 11), OCT, False),
        (FixedFrequency.QUARTERLY, Month(2026, 1), OCT, True),
        (FixedFrequency.QUARTERLY, Month(2026, 2), OCT, False),
        (FixedFrequency.QUARTERLY, Month(2025, 10), OCT, True),
        (FixedFrequency.YEARLY, Month(2024, 10), OCT, True),
        (FixedFrequency.YEARLY, Month(2026, 9), OCT, False),
    ],
)
def test_due_every_period_from_the_first_month(
    frequency: FixedFrequency, first: Month, month: Month, due: bool
) -> None:
    assert is_due(fixed(frequency=frequency, first=first), month) is due


def test_not_due_after_the_last_month_nor_while_paused() -> None:
    assert not is_due(fixed(last=Month(2026, 9)), OCT)
    assert is_due(fixed(last=OCT), OCT)
    assert not is_due(fixed(paused=True), OCT)


def test_the_last_day_stands_in_for_a_missing_one() -> None:
    assert due_date(fixed(day=31), Month(2026, 2)) == date(2026, 2, 28)
    assert due_date(fixed(day=31), OCT) == date(2026, 10, 31)


def test_monthly_equivalent() -> None:
    assert monthly_equivalent(D("-90.00"), FixedFrequency.MONTHLY) == D("-90.00")
    assert monthly_equivalent(D("-90.00"), FixedFrequency.QUARTERLY) == D("-30.00")
    assert monthly_equivalent(D("-120.00"), FixedFrequency.YEARLY) == D("-10.00")


def test_occurrences_to_confirm_confirmed_or_skipped() -> None:
    rent, nanny, netflix = fixed(), fixed("Crèche", KIDS, "-420.00", day=5), fixed("Netflix")
    created = line("Loyer (oct.)", HOUSING, 2, rent.id)  # label changed when confirming
    occ = occurrences([rent, nanny, netflix], OCT, [created], skipped={netflix.id})
    assert [(o.item_id, o.status, o.line_id) for o in occ] == [
        (rent.id, FixedStatus.CONFIRMED, created.id),
        (netflix.id, FixedStatus.SKIPPED, None),
        (nanny.id, FixedStatus.TO_CONFIRM, None),
    ]
    assert occ[2].due == date(2026, 10, 5)


def test_a_line_typed_by_hand_with_the_same_label_and_category_confirms() -> None:
    nanny = fixed("Crèche", KIDS, "-420.00", day=5)
    typed = line("  creche ", KIDS, 6)
    other_category = line("Crèche", HOUSING, 5)
    (occ,) = occurrences([nanny], OCT, [other_category, typed], skipped=set())
    assert (occ.status, occ.line_id) == (FixedStatus.CONFIRMED, typed.id)


def test_a_line_created_from_another_item_is_not_taken_by_hand_matching() -> None:
    a, b = fixed("Assurance", HOUSING, "-30.00", day=3), fixed("Assurance", HOUSING, "-30.00")
    from_a = line("Assurance", HOUSING, 3, a.id)
    occ = {o.item_id: o for o in occurrences([a, b], OCT, [from_a], skipped=set())}
    assert occ[a.id].line_id == from_a.id
    assert occ[b.id].status is FixedStatus.TO_CONFIRM


def test_the_closest_hand_line_confirms() -> None:
    gym = fixed("Salle", HOUSING, "-30.00", day=10)
    far, near = line("Salle", HOUSING, 25), line("Salle", HOUSING, 11)
    (occ,) = occurrences([gym], OCT, [far, near], skipped=set())
    assert occ.line_id == near.id


def test_projected_rest_takes_off_what_is_still_to_confirm() -> None:
    rent, nanny = fixed(), fixed("Crèche", KIDS, "-420.00", day=5)
    occ = occurrences([rent, nanny], OCT, [line("Loyer", HOUSING, 1)], skipped=set())
    assert projected_rest(D("1500.00"), occ) == D("1080.00")


labels = st.sampled_from(["Loyer", "Crèche", "Assurance"])
categories = st.sampled_from([HOUSING, KIDS])


@given(
    st.lists(st.tuples(labels, categories, st.integers(1, 28)), max_size=5),
    st.lists(st.tuples(labels, categories, st.integers(1, 28), st.booleans()), max_size=6),
    st.sets(st.integers(0, 4)),
)
def test_invariant_16_one_to_one_and_projection(
    items_spec: list[tuple[str, UUID, int]],
    lines_spec: list[tuple[str, UUID, int, bool]],
    skipped_at: set[int],
) -> None:
    items = [fixed(lb, cat, "-10.00", day=d) for lb, cat, d in items_spec]
    lines = [
        line(lb, cat, d, items[0].id if from_first and items else None)
        for lb, cat, d, from_first in lines_spec
    ]
    skipped = {items[i].id for i in skipped_at if i < len(items)}
    occ = occurrences(items, OCT, lines, skipped=skipped)
    taken = [o.line_id for o in occ if o.line_id is not None]
    assert len(taken) == len(set(taken))
    assert len(occ) == len({o.item_id for o in occ}) == len(items)
    open_ = [o for o in occ if o.status is FixedStatus.TO_CONFIRM]
    assert projected_rest(D(0), occ) == sum((o.amount for o in open_), D(0))
