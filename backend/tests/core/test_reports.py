from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from hypothesis import given
from hypothesis import strategies as st
from kwak_core.budget import Month
from kwak_core.categories import CategoryKind
from kwak_core.kpis import Flow, MonthFigures, month_figures
from kwak_core.reports import (
    LineKey,
    ReportRow,
    Section,
    by_category,
    previous_period,
    relative_change,
    report_period,
    report_rows,
    total_figures,
)

D = Decimal
FOOD, GROCERIES, HOUSING, SALARY, BONUS, PEA = (uuid4() for _ in range(6))
KINDS = {
    FOOD: CategoryKind.EXPENSE,
    GROCERIES: CategoryKind.EXPENSE,
    HOUSING: CategoryKind.EXPENSE,
    SALARY: CategoryKind.INCOME,
    BONUS: CategoryKind.INCOME,
    PEA: CategoryKind.SAVINGS,
}
PARENTS = {GROCERIES: FOOD, BONUS: SALARY}


def test_each_category_counts_in_its_section_in_its_natural_direction() -> None:
    flows = [
        Flow(GROCERIES, D("-300")),
        Flow(GROCERIES, D("20")),  # a refund lowers spending
        Flow(SALARY, D("2500")),
        Flow(PEA, D("-500")),
        Flow(None, D("-40")),  # to categorise: an outflow is spending...
        Flow(None, D("15")),  # ...and an inflow is income
    ]
    assert by_category(flows, KINDS) == {
        (Section.SPENDING, GROCERIES): D("280"),
        (Section.INCOME, SALARY): D("2500"),
        (Section.SAVINGS, PEA): D("500"),
        (Section.SPENDING, None): D("40"),
        (Section.INCOME, None): D("15"),
    }


def test_subcategories_roll_up_into_their_top_level_category() -> None:
    current: dict[LineKey, Decimal] = {
        (Section.SPENDING, FOOD): D("50"),  # spent in the parent itself
        (Section.SPENDING, GROCERIES): D("300"),
        (Section.SPENDING, HOUSING): D("900"),
        (Section.INCOME, SALARY): D("2500"),
    }
    previous: dict[LineKey, Decimal] = {
        (Section.SPENDING, GROCERIES): D("200"),
        (Section.INCOME, BONUS): D("100"),
    }

    rows = report_rows(current, previous, PARENTS)

    assert rows == [
        ReportRow(
            Section.INCOME,
            SALARY,
            D("2500"),
            D("100"),
            (ReportRow(Section.INCOME, BONUS, D("0"), D("100")),),
        ),
        ReportRow(Section.SPENDING, HOUSING, D("900"), D("0")),
        ReportRow(
            Section.SPENDING,
            FOOD,
            D("350"),
            D("200"),
            (ReportRow(Section.SPENDING, GROCERIES, D("300"), D("200")),),
        ),
    ]


def test_to_categorise_comes_last_in_its_section() -> None:
    current = {(Section.SPENDING, None): D("5000"), (Section.SPENDING, HOUSING): D("900")}
    rows = report_rows(current, {}, PARENTS)
    assert [r.category_id for r in rows] == [HOUSING, None]


def test_a_category_with_nothing_in_either_period_is_left_out() -> None:
    rows = report_rows({(Section.SPENDING, HOUSING): D("0")}, {}, PARENTS)
    assert rows == []


def test_the_totals_of_a_period_add_up_its_months() -> None:
    months = [
        MonthFigures(D("100"), D("2000"), D("50"), D("10"), D("300")),
        MonthFigures(D("200"), D("2100"), D("0"), D("20"), D("-100")),
    ]
    assert total_figures(months) == MonthFigures(D("300"), D("4100"), D("50"), D("30"), D("200"))
    assert total_figures([]) == MonthFigures(D("0"), D("0"))


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


amounts = st.integers(min_value=-1_000_00, max_value=1_000_00).map(lambda c: Decimal(c) / 100)
month_flows = st.lists(
    st.tuples(st.sampled_from([FOOD, GROCERIES, HOUSING, SALARY, BONUS, PEA, None]), amounts),
    max_size=30,
)


@given(st.lists(month_flows, min_size=1, max_size=6))
def test_a_report_never_disagrees_with_the_home_page(
    months: list[list[tuple[UUID | None, Decimal]]],
) -> None:
    """Invariant §8.18: the period's figures are the sums of its months' KPIs, and in each
    section the category lines add up to the section's total."""
    flows = [[Flow(c, a) for c, a in month] for month in months]
    totals = total_figures(month_figures(f, KINDS) for f in flows)
    lines = by_category([f for month in flows for f in month], KINDS)
    rows = report_rows(lines, {}, PARENTS)

    def section(s: Section) -> Decimal:
        return sum((r.amount for r in rows if r.section is s), D(0))

    assert section(Section.SPENDING) == totals.spent
    assert section(Section.INCOME) == totals.income
    assert section(Section.SAVINGS) == totals.saved
    for row in rows:
        assert (
            sum((c.amount for c in row.children), D(0))
            + lines.get((row.section, row.category_id), D(0))
            == row.amount
        )


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
