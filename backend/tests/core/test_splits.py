from decimal import Decimal
from uuid import uuid4

import pytest
from hypothesis import given
from hypothesis import strategies as st
from kwak_core.splits import Part, SplitError, resize, split

D = Decimal
FOOD, HOME, CARE = uuid4(), uuid4(), uuid4()


def test_the_last_part_takes_the_rest() -> None:
    parts = split(D("-84.30"), [Part(FOOD, D("-60.00")), Part(HOME, D("-15.50"))], CARE)
    assert parts == [
        Part(FOOD, D("-60.00")),
        Part(HOME, D("-15.50")),
        Part(CARE, D("-8.80")),
    ]


@pytest.mark.parametrize(
    ("given", "reason"),
    [
        ([], "two parts"),
        ([Part(FOOD, D("-84.30"))], "rest"),  # nothing left for the last part
        ([Part(FOOD, D("-90.00"))], "rest"),  # the rest would be an inflow
        ([Part(FOOD, D("0.00"))], "zero"),
        ([Part(FOOD, D("10.00"))], "sign"),
    ],
)
def test_parts_that_do_not_fit_are_refused(given: list[Part], reason: str) -> None:
    with pytest.raises(SplitError, match=reason):
        split(D("-84.30"), given, CARE)


def test_a_part_may_have_no_category_yet() -> None:
    parts = split(D("50.00"), [Part(None, D("20.00"))], FOOD)
    assert parts[0].category_id is None


def test_a_new_amount_moves_the_last_part() -> None:
    parts = [Part(FOOD, D("-60.00")), Part(CARE, D("-24.30"))]
    assert resize(parts, D("-90.00")) == [Part(FOOD, D("-60.00")), Part(CARE, D("-30.00"))]
    with pytest.raises(SplitError, match="rest"):
        resize(parts, D("-60.00"))


cents = st.integers(1, 10**7).map(lambda c: D(c) / 100)


@given(cents, st.lists(cents, min_size=1, max_size=6), st.booleans(), cents)
def test_parts_always_add_up_to_the_amount(
    total: Decimal, sizes: list[Decimal], outflow: bool, new_total: Decimal
) -> None:
    """Invariant §8.2."""
    sign = -1 if outflow else 1
    amount = sign * (total + sum(sizes, D(0)))
    parts = split(amount, [Part(FOOD, sign * s) for s in sizes], CARE)
    assert sum((p.amount for p in parts), D(0)) == amount
    assert all((p.amount < 0) == outflow and p.amount != 0 for p in parts)
    try:
        moved = resize(parts, sign * new_total)
    except SplitError:
        return
    assert sum((p.amount for p in moved), D(0)) == sign * new_total
    assert moved[:-1] == parts[:-1]
