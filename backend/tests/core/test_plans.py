from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from hypothesis import given
from hypothesis import strategies as st
from kwak_core.budget import BudgetStatus, Month, build_matrix
from kwak_core.plans import (
    Period,
    PeriodKind,
    Plan,
    Review,
    ReviewRow,
    check_no_overlap,
    close_early,
    compare,
    cumulative,
    editable,
    elapsed_share,
    envelopes,
    new_plan,
    replacement,
    review_plan,
    target_history,
)

D = Decimal
FOOD, GROCERIES, BAKERY, HOUSING = uuid4(), uuid4(), uuid4(), uuid4()
CATEGORIES = [
    (FOOD, None, "Food"),
    (GROCERIES, FOOD, "Groceries"),
    (BAKERY, FOOD, "Bakery"),
    (HOUSING, None, "Housing"),
]
Q1 = Period(PeriodKind.QUARTER, 2027, 1)
JAN, FEB, MAR, APR = Month(2027, 1), Month(2027, 2), Month(2027, 3), Month(2027, 4)


def q1_plan(**targets: str) -> Plan:
    ids = {"food": FOOD, "groceries": GROCERIES, "bakery": BAKERY, "housing": HOUSING}
    return Plan.covering(Q1, {ids[k]: D(v) for k, v in targets.items()})


def row(review: Review, cid: UUID | None) -> ReviewRow:
    return next(r for r in review.rows if r.category_id == cid)


# Periods


@pytest.mark.parametrize(
    ("kind", "index", "start", "end", "label"),
    [
        (PeriodKind.YEAR, 1, Month(2027, 1), Month(2027, 12), "2027"),
        (PeriodKind.SEMESTER, 2, Month(2027, 7), Month(2027, 12), "2027-S2"),
        (PeriodKind.QUARTER, 3, Month(2027, 7), Month(2027, 9), "2027-Q3"),
    ],
)
def test_periods_follow_the_calendar(
    kind: PeriodKind, index: int, start: Month, end: Month, label: str
) -> None:
    period = Period(kind, 2027, index)
    assert (period.start, period.end, str(period)) == (start, end, label)
    assert Period.parse(label) == period
    assert Period.containing(kind, Month(2027, end.month)) == period


@pytest.mark.parametrize(
    "bad",
    [
        (PeriodKind.QUARTER, 5),
        (PeriodKind.SEMESTER, 0),
        (PeriodKind.YEAR, 2),
    ],
)
def test_a_period_index_must_exist(bad: tuple[PeriodKind, int]) -> None:
    with pytest.raises(ValueError, match="no such period"):
        Period(bad[0], 2027, bad[1])


@pytest.mark.parametrize("text", ["2027-Q5", "2027-X1", "27", ""])
def test_unreadable_periods_are_refused(text: str) -> None:
    with pytest.raises(ValueError, match="period"):
        Period.parse(text)


# Plans


def test_a_plan_covers_its_period_and_refuses_negative_targets() -> None:
    plan = q1_plan(groceries="400")
    assert (plan.start, plan.end, plan.months) == (JAN, MAR, [JAN, FEB, MAR])
    assert not plan.closed_early
    with pytest.raises(ValueError, match="a target cannot be negative"):
        q1_plan(groceries="-1")
    with pytest.raises(ValueError, match="whole number of cents"):
        q1_plan(groceries="1.001")


def test_a_plan_stays_inside_its_period() -> None:
    with pytest.raises(ValueError, match="a plan lies within its period"):
        Plan(Q1, {}, start=MAR, end=APR)
    with pytest.raises(ValueError, match="a plan lies within its period"):
        Plan(Q1, {}, start=FEB, end=JAN)


def test_plans_cannot_overlap() -> None:
    year = Plan.covering(Period(PeriodKind.YEAR, 2027, 1), {})
    q2 = Plan.covering(Period(PeriodKind.QUARTER, 2027, 2), {})
    check_no_overlap([q1_plan(), q2])
    with pytest.raises(ValueError, match="budget plans overlap: 2027 and 2027-Q1"):
        check_no_overlap([q1_plan(), year])


def test_a_new_plan_takes_the_latest_plan_targets() -> None:
    previous = Plan.covering(Q1, {GROCERIES: D("400")}, expected_income=D("3000"))
    plan = new_plan(Period(PeriodKind.SEMESTER, 2027, 2), previous)
    assert plan.targets == {GROCERIES: D("400")}
    assert plan.expected_income == D("3000")
    assert new_plan(Q1, None).targets == {}


def test_a_plan_is_editable_until_the_end_of_its_first_month() -> None:
    plan = q1_plan()
    assert editable(plan, date(2026, 12, 15))
    assert editable(plan, date(2027, 1, 31))
    assert not editable(plan, date(2027, 2, 1))


def test_closing_early_keeps_the_months_covered_and_a_replacement_covers_the_rest() -> None:
    plan = Plan.covering(Q1, {GROCERIES: D("400")}, expected_income=D("3000"))
    closed = close_early(plan, FEB, reason="job loss")
    assert (closed.start, closed.end, closed.closed_early) == (JAN, FEB, True)
    assert closed.close_reason == "job loss"
    rest = replacement(closed)
    assert (rest.start, rest.end, rest.closed_early) == (MAR, MAR, False)
    assert rest.targets == {GROCERIES: D("400")}
    assert rest.expected_income == D("3000")
    check_no_overlap([closed, rest])


@pytest.mark.parametrize("last", [Month(2026, 12), MAR, APR])
def test_a_plan_closes_early_on_one_of_its_months_but_the_last(last: Month) -> None:
    with pytest.raises(ValueError, match="a plan closes early before its last month"):
        close_early(q1_plan(), last)


def test_only_a_plan_closed_early_gets_a_replacement() -> None:
    with pytest.raises(ValueError, match="only a plan closed early is replaced"):
        replacement(q1_plan())


def test_envelopes_multiply_the_monthly_target_and_parents_sum_their_children() -> None:
    plan = q1_plan(groceries="400", bakery="30", housing="900")
    assert envelopes(plan, CATEGORIES) == {
        FOOD: D("1290"),
        GROCERIES: D("1200"),
        BAKERY: D("90"),
        HOUSING: D("2700"),
    }
    own = q1_plan(food="500", groceries="400")
    assert envelopes(own, CATEGORIES)[FOOD] == D("1500")
    assert BAKERY not in envelopes(own, CATEGORIES)


# The matrix follows the plans


def test_the_matrix_targets_come_from_the_plans_and_stop_between_them() -> None:
    q1 = q1_plan(groceries="400", housing="900")
    q3 = Plan.covering(Period(PeriodKind.QUARTER, 2027, 3), {GROCERIES: D("450")})
    history = target_history([q3, q1])
    months = [JAN, MAR, APR, Month(2027, 7)]
    matrix = build_matrix(CATEGORIES, history, {}, months)
    groceries = next(r for r in matrix.rows if r.category_id == GROCERIES)
    housing = next(r for r in matrix.rows if r.category_id == HOUSING)
    assert [c.target for c in groceries.cells] == [D("400"), D("400"), None, D("450")]
    assert [c.target for c in housing.cells] == [D("900"), D("900"), None, None]


# Review


def test_elapsed_share_counts_completed_months_and_the_days_of_the_current_one() -> None:
    plan = q1_plan()
    assert elapsed_share(plan, date(2026, 12, 31)) == 0
    assert elapsed_share(plan, date(2027, 2, 14)) == (1 + D(14) / 28) / 3
    assert elapsed_share(plan, date(2027, 3, 31)) == 1
    assert elapsed_share(plan, date(2027, 6, 1)) == 1


def test_a_finished_plan_is_judged_on_its_envelope() -> None:
    plan = q1_plan(groceries="400")
    spending = {(GROCERIES, JAN): D("450"), (GROCERIES, FEB): D("350"), (GROCERIES, MAR): D("380")}
    review = review_plan(plan, CATEGORIES, spending, {}, today=date(2027, 4, 2))
    groceries = row(review, GROCERIES)
    assert review.finished
    assert (groceries.envelope, groceries.spent, groceries.gap) == (D("1200"), D("1180"), D("-20"))
    assert groceries.status is BudgetStatus.ON
    assert (groceries.months_over, groceries.months_on, groceries.months_under) == (1, 1, 1)
    assert groceries.projection == D("1180")
    assert not groceries.drifting


def test_during_a_plan_spending_is_judged_on_the_pace_and_projected() -> None:
    plan = q1_plan(groceries="400", housing="900")
    spending = {(GROCERIES, JAN): D("500"), (GROCERIES, FEB): D("250"), (HOUSING, JAN): D("900")}
    review = review_plan(plan, CATEGORIES, spending, {}, today=date(2027, 2, 14))
    groceries, housing = row(review, GROCERIES), row(review, HOUSING)
    # 1.5 months out of 3: pace 600, projection 750 / 0.5 = 1500 > 1200.
    assert not review.finished
    assert (groceries.pace, groceries.projection) == (D("600.00"), D("1500.00"))
    assert groceries.status is BudgetStatus.OVER
    assert groceries.drifting
    assert groceries.drift == D("300.00")
    # February is not over yet: only January counts in the months over / on / under.
    assert (groceries.months_over, groceries.months_on, groceries.months_under) == (1, 0, 0)
    assert housing.status is BudgetStatus.UNDER
    assert [r.category_id for r in review.drifting_rows] == [FOOD, GROCERIES]
    # The gap the status is judged on: 750 spent against a pace of 600.
    assert groceries.pace_gap_ratio == D("0.25")


def test_once_over_the_gap_to_the_pace_is_the_gap_to_the_envelope() -> None:
    plan = q1_plan(groceries="400")
    spending = {(GROCERIES, JAN): D("1180")}
    groceries = row(review_plan(plan, CATEGORIES, spending, {}, today=date(2027, 4, 2)), GROCERIES)
    assert groceries.pace_gap_ratio == groceries.gap_ratio
    assert (
        row(review_plan(plan, CATEGORIES, {}, {}, date(2026, 12, 1)), GROCERIES).pace_gap_ratio
        is None
    )


def test_the_review_totals_income_savings_and_the_planned_savings() -> None:
    plan = Plan.covering(Q1, {GROCERIES: D("400")}, expected_income=D("2000"))
    spending = {(GROCERIES, m): D("400") for m in (JAN, FEB, MAR)} | {(None, FEB): D("60")}
    income = {JAN: D("2000"), FEB: D("2100"), MAR: D("1900"), APR: D("9999")}
    review = review_plan(plan, CATEGORIES, spending, income, today=date(2027, 4, 1))
    assert review.total.spent == D("1260")
    assert review.total.envelope == D("1200")
    assert review.uncategorised == D("60")
    assert review.provisional
    assert review.income == D("6000")
    assert review.savings == D("4740")
    assert review.savings_rate == D("0.79")
    assert review.planned_savings == D("4800")


def test_a_plan_closed_early_is_reviewed_over_its_own_months() -> None:
    plan = close_early(q1_plan(groceries="400"), JAN, reason="raise")
    spending = {(GROCERIES, JAN): D("390"), (GROCERIES, FEB): D("999")}
    review = review_plan(plan, CATEGORIES, spending, {}, today=date(2027, 2, 10))
    groceries = row(review, GROCERIES)
    assert review.finished
    assert (groceries.envelope, groceries.spent) == (D("400"), D("390"))
    assert not review.provisional


# Steering charts


def test_the_cumulative_chart_stops_spending_at_today_and_ends_on_the_envelope() -> None:
    plan = q1_plan(groceries="300")
    daily = {date(2027, 1, 1): D("10"), date(2027, 1, 31): D("5"), date(2027, 2, 2): D("7")}
    points = cumulative(plan, daily, D("900"), today=date(2027, 2, 2))
    assert (points[0].day, points[-1].day) == (date(2027, 1, 1), date(2027, 3, 31))
    by_day = {p.day: p for p in points}
    assert by_day[date(2027, 1, 31)].spent == D("15")
    assert by_day[date(2027, 1, 31)].envelope == D("300.00")
    assert by_day[date(2027, 2, 2)].spent == D("22")
    assert by_day[date(2027, 2, 3)].spent is None
    assert points[-1].envelope == D("900.00")


def test_plans_of_different_lengths_compare_on_monthly_averages() -> None:
    year_2026 = Plan.covering(Period(PeriodKind.YEAR, 2026, 1), {GROCERIES: D("350")})
    spending_2026 = {(GROCERIES, Month(2026, m)): D("360") for m in range(1, 13)}
    before = review_plan(year_2026, CATEGORIES, spending_2026, {}, today=date(2027, 4, 1))
    spending_q1 = {(GROCERIES, m): D("396") for m in (JAN, FEB, MAR)}
    after = review_plan(q1_plan(groceries="400"), CATEGORIES, spending_q1, {}, date(2027, 4, 1))
    groceries = next(r for r in compare(before, after) if r.category_id == GROCERIES)
    assert (groceries.target_a, groceries.target_b) == (D("350"), D("400"))
    assert (groceries.average_a, groceries.average_b) == (D("360.00"), D("396.00"))
    assert groceries.change == D("36.00")
    assert groceries.change_ratio == D("0.1")


# Invariants (docs/SPECIFICATIONS.md §8)

periods = st.builds(
    lambda kind, year, i: Period(kind, year, min(i, {"year": 1, "semester": 2}.get(kind, 4))),
    st.sampled_from(PeriodKind),
    st.integers(2026, 2028),
    st.integers(1, 4),
)
amounts = st.integers(0, 100_000).map(lambda cents: D(cents) / 100)


@given(st.lists(periods, max_size=6))
def test_invariant_8_accepted_plans_never_share_a_month(chosen: list[Period]) -> None:
    plans = [Plan.covering(p, {}) for p in chosen]
    try:
        check_no_overlap(plans)
    except ValueError:
        return
    months = [m for p in plans for m in p.months]
    assert len(months) == len(set(months))
    for plan in plans:
        assert plan.period.start <= plan.start <= plan.end <= plan.period.end


@given(periods, st.integers(0, 10))
def test_invariant_8_closing_early_and_replacing_tiles_the_period(period: Period, cut: int) -> None:
    plan = Plan.covering(period, {GROCERIES: D("1")})
    if cut >= len(plan.months) - 1:
        return
    closed = close_early(plan, plan.months[cut])
    rest = replacement(closed)
    check_no_overlap([closed, rest])
    assert closed.months + rest.months == period.months


@given(periods, amounts, amounts, st.booleans())
def test_invariant_9_envelope_is_target_times_months(
    period: Period, groceries: Decimal, bakery: Decimal, own_food: bool
) -> None:
    targets = {GROCERIES: groceries, BAKERY: bakery} | ({FOOD: groceries} if own_food else {})
    plan = Plan.covering(period, targets)
    result = envelopes(plan, CATEGORIES)
    n = len(period.months)
    assert result[GROCERIES] == groceries * n
    assert result[FOOD] == (groceries * n if own_food else (groceries + bakery) * n)


@given(
    st.dictionaries(
        st.tuples(
            st.sampled_from([FOOD, GROCERIES, BAKERY, HOUSING, None]),
            st.sampled_from([JAN, FEB, MAR, APR]),
        ),
        amounts,
    ),
    st.integers(0, 120),
)
def test_invariant_10_the_review_agrees_with_the_matrix(
    spending: dict[tuple[UUID | None, Month], Decimal], offset: int
) -> None:
    plan = q1_plan(groceries="400", housing="900")
    today = date(2027, 1, 1) + timedelta(days=offset)
    review = review_plan(plan, CATEGORIES, spending, {}, today)
    matrix = build_matrix(CATEGORIES, target_history([plan]), spending, plan.months)
    for matrix_row in matrix.rows:
        assert row(review, matrix_row.category_id).spent == sum(
            (c.spent for c in matrix_row.cells), D(0)
        )
    assert review.total.spent == sum((c.spent for c in matrix.total.cells), D(0))
