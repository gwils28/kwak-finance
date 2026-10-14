from datetime import date

from hypothesis import given
from hypothesis import strategies as st
from kwak_core.analysis import counted_day, counted_months, first_counted
from kwak_core.budget import Month, month_range

OCT = Month(2026, 10)


def test_without_a_start_every_month_counts() -> None:
    months = month_range(Month(2025, 1), Month(2026, 12))
    assert counted_months(months, None) == months
    assert first_counted(Month(2025, 1), None) == Month(2025, 1)
    assert counted_day(date(2025, 1, 5), None) == date(2025, 1, 5)


def test_months_before_the_start_do_not_count() -> None:
    months = month_range(Month(2026, 8), Month(2026, 12))
    assert counted_months(months, OCT) == month_range(OCT, Month(2026, 12))
    assert counted_months(month_range(Month(2026, 1), Month(2026, 3)), OCT) == []
    assert first_counted(Month(2026, 1), OCT) == OCT
    assert first_counted(Month(2026, 11), OCT) == Month(2026, 11)


def test_detection_looks_back_no_further_than_the_start() -> None:
    assert counted_day(date(2026, 4, 17), OCT) == date(2026, 10, 1)
    assert counted_day(date(2026, 10, 20), OCT) == date(2026, 10, 20)


months = st.builds(Month, st.integers(2000, 2030), st.integers(1, 12))


@given(months, months, st.one_of(st.none(), months))
def test_counted_months_are_the_months_from_the_start(
    a: Month, b: Month, since: Month | None
) -> None:
    period = month_range(min(a, b), max(a, b))
    counted = counted_months(period, since)
    assert counted == period[len(period) - len(counted) :]  # a suffix
    assert all(since is None or m >= since for m in counted)
    assert first_counted(a, since) >= a
    assert since is None or first_counted(a, since) >= since
