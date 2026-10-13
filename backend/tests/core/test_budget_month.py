from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st
from kwak_core.budget import Month
from kwak_core.budget_month import (
    DEFAULT_SHIFT_DAY,
    Booked,
    budget_day,
    budget_month,
    check_manual_month,
    check_shift_day,
    months_moved,
    shift_day,
)

D = Decimal
SEP, OCT, NOV = Month(2026, 9), Month(2026, 10), Month(2026, 11)


def test_month_steps_back_across_a_year() -> None:
    assert Month(2026, 1).previous() == Month(2025, 12)
    assert OCT.previous() == SEP


def test_without_a_shift_a_transaction_counts_in_its_booking_month() -> None:
    assert budget_month(Booked(date(2026, 10, 20))) == OCT


@pytest.mark.parametrize(
    ("day", "month"),
    [(14, OCT), (15, NOV), (20, NOV), (28, NOV), (31, NOV)],
)
def test_from_the_shift_day_a_transaction_counts_for_the_next_month(day: int, month: Month) -> None:
    assert DEFAULT_SHIFT_DAY == 15
    assert budget_month(Booked(date(2026, 10, day)), shift_from=15) == month


def test_december_shifts_to_january() -> None:
    assert budget_month(Booked(date(2026, 12, 20)), shift_from=15) == Month(2027, 1)


def test_a_month_set_by_hand_wins_over_the_category() -> None:
    early = Booked(date(2026, 10, 18), manual=OCT)
    assert budget_month(early, shift_from=15) == OCT
    assert budget_month(Booked(date(2026, 10, 2), manual=SEP)) == SEP


def test_a_transfer_always_counts_in_its_booking_month() -> None:
    leg = Booked(date(2026, 10, 20), transfer=True, manual=NOV)
    assert budget_month(leg, shift_from=15) == OCT


def test_a_subcategory_follows_its_parent_unless_it_has_its_own_setting() -> None:
    assert shift_day(own=None, parent=20) == 20
    assert shift_day(own=None, parent=None) is None
    assert shift_day(own=25, parent=20) == 25
    assert shift_day(own=0, parent=20) is None  # 0: never shifted, whatever the parent


@pytest.mark.parametrize("day", [-1, 32])
def test_a_shift_day_is_a_day_of_the_month(day: int) -> None:
    with pytest.raises(ValueError, match="day"):
        check_shift_day(day)


def test_a_month_set_by_hand_is_at_most_one_month_away() -> None:
    check_manual_month(date(2026, 10, 20), SEP)
    check_manual_month(date(2026, 10, 20), NOV)
    with pytest.raises(ValueError, match="one month"):
        check_manual_month(date(2026, 10, 20), Month(2026, 12))


def test_a_shifted_transaction_sits_at_the_edge_of_its_budget_month_by_day() -> None:
    assert budget_day(date(2026, 10, 20), OCT) == date(2026, 10, 20)
    assert budget_day(date(2026, 10, 20), NOV) == date(2026, 11, 1)
    assert budget_day(date(2026, 10, 2), SEP) == date(2026, 9, 30)


def test_changing_the_shift_day_reports_the_months_it_touches() -> None:
    items = [
        Booked(date(2026, 9, 20)),  # Sep -> Oct
        Booked(date(2026, 10, 10)),  # stays in Oct
        Booked(date(2026, 10, 22), manual=OCT),  # set by hand: stays
        Booked(date(2026, 10, 25), transfer=True),  # transfer: stays
    ]
    moved, months = months_moved(items, before=None, after=15)
    assert moved == 1
    assert months == {SEP, OCT}


# Invariant §8.15.
days = st.dates(min_value=date(2020, 1, 1), max_value=date(2030, 12, 31))


@st.composite
def booked(draw: st.DrawFn) -> Booked:
    day = draw(days)
    own = Month.of(day)
    manual = draw(st.sampled_from([None, own.previous(), own, own.next()]))
    return Booked(day, manual=manual, transfer=draw(st.booleans()))


@given(
    st.lists(st.tuples(booked(), st.decimals(-5000, 5000, places=2)), max_size=40),
    st.one_of(st.none(), st.integers(1, 31)),
)
def test_every_transaction_counts_once_near_its_booking_month(
    items: list[tuple[Booked, Decimal]], shift_from: int | None
) -> None:
    by_budget: dict[Month, Decimal] = defaultdict(Decimal)
    by_booking: dict[Month, Decimal] = defaultdict(Decimal)
    for item, amount in items:
        own = Month.of(item.booked_on)
        month = budget_month(item, shift_from=shift_from)
        assert month in {own.previous(), own, own.next()}
        if item.transfer:
            assert month == own
        day = budget_day(item.booked_on, month)
        assert Month.of(day) == month
        assert abs(day - item.booked_on) <= timedelta(days=31)
        by_budget[month] += amount
        by_booking[own] += amount
    assert sum(by_budget.values(), D(0)) == sum(by_booking.values(), D(0))
