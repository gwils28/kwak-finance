from decimal import Decimal

import pytest
from kwak_core.budget import Month
from kwak_core.reports import previous_period, relative_change, report_period

D = Decimal


@pytest.mark.parametrize(
    ("start", "end", "expected"),
    [
        ("2026-01", "2026-12", ("2025-01", "2025-12")),  # a year: the year before
        ("2026-04", "2026-06", ("2026-01", "2026-03")),  # a quarter: the quarter before
        ("2026-01", "2026-01", ("2025-12", "2025-12")),  # a month: the month before
        ("2025-11", "2026-02", ("2025-07", "2025-10")),  # any length, across a year
    ],
)
def test_the_previous_period_has_the_same_length_and_ends_just_before(
    start: str, end: str, expected: tuple[str, str]
) -> None:
    first, last = previous_period(Month.parse(start), Month.parse(end))
    assert (str(first), str(last)) == expected


@pytest.mark.parametrize(
    ("start", "end", "expected"),
    [
        # A running year stops at the current month, against the same months the year before.
        ("2026-01", "2026-12", ("2026-01", "2026-10", "2025-01", "2025-10", True)),
        ("2026-10", "2026-12", ("2026-10", "2026-10", "2026-07", "2026-07", True)),
        # A period over already: the period just before, of the same length.
        ("2025-01", "2025-12", ("2025-01", "2025-12", "2024-01", "2024-12", False)),
        ("2025-11", "2026-10", ("2025-11", "2026-10", "2024-11", "2025-10", False)),
    ],
)
def test_a_running_period_stops_at_the_current_month(
    start: str, end: str, expected: tuple[str, str, str, str, bool]
) -> None:
    p = report_period(Month.parse(start), Month.parse(end), current=Month(2026, 10))
    got = (str(p.start), str(p.end), str(p.previous_start), str(p.previous_end), p.to_date)
    assert got == expected


@pytest.mark.parametrize(("start", "end"), [("2026-04", "2026-03"), ("2026-11", "2026-12")])
def test_a_period_ending_before_it_starts_or_not_started_is_refused(start: str, end: str) -> None:
    with pytest.raises(ValueError, match="the period"):
        report_period(Month.parse(start), Month.parse(end), current=Month(2026, 10))


@pytest.mark.parametrize(
    ("current", "reference", "expected"),
    [
        ("120", "100", D("0.2")),
        ("80", "100", D("-0.2")),
        ("200", "-500", D("1.4")),  # from -500 to +200: better, not worse
        ("-600", "-500", D("-0.2")),
        ("50", "0", None),
    ],
)
def test_a_change_keeps_its_direction_from_a_negative_reference(
    current: str, reference: str, expected: Decimal | None
) -> None:
    assert relative_change(D(current), D(reference)) == expected


def test_a_period_starts_no_earlier_than_the_first_line() -> None:
    p = report_period(
        Month(2026, 1), Month(2026, 12), current=Month(2026, 11), since=Month(2026, 10)
    )
    assert (str(p.start), str(p.end), p.to_date) == ("2026-10", "2026-11", True)
    # Before the start, so counted as empty: the report says there is nothing to compare.
    assert p.previous_end < Month(2026, 10)


def test_a_period_over_before_the_first_line_is_refused() -> None:
    with pytest.raises(ValueError, match="before the first month with a line"):
        report_period(
            Month(2025, 1), Month(2025, 12), current=Month(2026, 11), since=Month(2026, 10)
        )


def test_a_previous_period_reaching_before_the_first_line_is_not_compared() -> None:
    p = report_period(Month(2026, 5), Month(2026, 7), current=Month(2026, 10), since=Month(2026, 4))
    assert (str(p.previous_start), str(p.previous_end)) == ("2026-02", "2026-04")
    assert p.compared is False  # only April counts: no fair comparison
    full = report_period(
        Month(2026, 7), Month(2026, 9), current=Month(2026, 10), since=Month(2026, 4)
    )
    assert full.compared is True
