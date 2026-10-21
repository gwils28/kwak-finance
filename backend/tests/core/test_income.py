from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st
from kwak_core.budget import Month
from kwak_core.income import Income, check_income, income_of

D = Decimal
SEP, OCT, NOV, DEC = Month(2026, 9), Month(2026, 10), Month(2026, 11), Month(2026, 12)


def test_an_entered_month_is_not_carried() -> None:
    assert income_of(OCT, {OCT: D("4200.00")}) == Income(D("4200.00"), carried=False)


def test_a_month_without_income_takes_the_previous_one_carried() -> None:
    entered = {SEP: D("4000.00"), OCT: D("4200.00")}
    assert income_of(DEC, entered) == Income(D("4200.00"), carried=True)


def test_before_the_first_income_a_month_has_none() -> None:
    assert income_of(SEP, {OCT: D("4200.00")}) is None


def test_zero_is_an_income_entered() -> None:
    assert income_of(NOV, {OCT: D("4200.00"), NOV: D(0)}) == Income(D(0), carried=False)


@pytest.mark.parametrize("amount", [D("-1.00"), D("10.001")])
def test_an_income_is_zero_or_more_in_cents(amount: Decimal) -> None:
    with pytest.raises(ValueError, match=r"zero or more|cents"):
        check_income(amount)


months = st.builds(Month, st.integers(2025, 2027), st.integers(1, 12))
amounts = st.decimals(min_value=0, max_value=20000, places=2)


@given(st.dictionaries(months, amounts, max_size=6), months)
def test_invariant_5_the_last_income_entered_up_to_the_month(
    entered: dict[Month, Decimal], month: Month
) -> None:
    earlier = [m for m in entered if m <= month]
    got = income_of(month, entered)
    if not earlier:
        assert got is None
    else:
        assert got == Income(entered[max(earlier)], carried=month not in entered)
