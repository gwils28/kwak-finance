from datetime import date, timedelta
from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st
from kwak_core.balances import balance_on

OPENED = date(2026, 1, 1)
cents = st.integers(min_value=-(10**8), max_value=10**8).map(lambda c: Decimal(c) / 100)
movements = st.lists(
    st.tuples(st.integers(0, 60).map(lambda d: OPENED + timedelta(days=d)), cents), max_size=40
)


def test_the_balance_starts_from_the_opening_balance() -> None:
    assert balance_on(Decimal("100.00"), [], on=OPENED) == Decimal("100.00")


def test_the_balance_counts_movements_up_to_and_including_the_day() -> None:
    moves = [(date(2026, 1, 5), Decimal("-30.00")), (date(2026, 1, 6), Decimal("10.00"))]
    assert balance_on(Decimal("100.00"), moves, on=date(2026, 1, 5)) == Decimal("70.00")
    assert balance_on(Decimal("100.00"), moves, on=date(2026, 1, 6)) == Decimal("80.00")


@given(cents, movements, st.integers(0, 60))
def test_balance_is_opening_plus_movements_to_date(
    opening: Decimal, moves: list[tuple[date, Decimal]], day: int
) -> None:
    """Invariant §8.1."""
    on = OPENED + timedelta(days=day)
    expected = opening + sum((amount for when, amount in moves if when <= on), Decimal(0))
    assert balance_on(opening, moves, on=on) == expected


@given(cents, movements, movements)
def test_order_of_movements_does_not_matter(
    opening: Decimal, a: list[tuple[date, Decimal]], b: list[tuple[date, Decimal]]
) -> None:
    on = OPENED + timedelta(days=60)
    assert balance_on(opening, a + b, on=on) == balance_on(opening, b + a, on=on)
