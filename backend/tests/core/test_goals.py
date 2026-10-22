from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest
from hypothesis import given
from hypothesis import strategies as st
from kwak_core.budget import Month
from kwak_core.fixed import FixedFrequency as Frequency
from kwak_core.goals import (
    Envelope,
    FundedGoal,
    GoalError,
    GoalStatus,
    Line,
    PyramidGoal,
    Tier,
    archives_itself,
    capacity,
    check_funding_line,
    check_goal,
    check_line_shares,
    check_precaution_slot,
    effort_plan,
    envelopes,
    fixed_expenses,
    line_worth,
    precaution_proposal,
    pyramid,
    tier_of,
    track,
)
from kwak_core.visibility import Visibility
from kwak_core.wealth import WealthKind, line_cell

D = Decimal
ME, OTHER = uuid4(), uuid4()
OCT = Month(2026, 10)


def _months(start: Month, n: int) -> list[Month]:
    out = [start]
    while len(out) < n:
        out.append(out[-1].next())
    return out


# F-GOAL-1: a goal's fields


def test_only_a_permanent_goal_goes_without_a_deadline() -> None:
    check_goal(D("5000"), permanent=True, deadline=None, start=OCT, this_month=OCT)
    check_goal(D("5000"), precaution=True, permanent=True, deadline=None, start=OCT, this_month=OCT)
    with pytest.raises(GoalError, match="deadline"):
        check_goal(D("5000"), deadline=None, start=OCT, this_month=OCT)


def test_the_precaution_is_permanent() -> None:
    with pytest.raises(GoalError, match="permanent"):
        check_goal(D("5000"), precaution=True, deadline=None, start=OCT, this_month=OCT)


def test_a_goal_archives_itself_once_reached_unless_permanent() -> None:
    values = [D("0"), D("2000")]
    reached = track(D("2000"), Month(2026, 9), Month(2027, 9), values, this_month=OCT)
    behind = track(D("9000"), Month(2026, 9), Month(2027, 9), values, this_month=OCT)
    assert archives_itself(reached, permanent=False)
    assert not archives_itself(reached, permanent=True)
    assert not archives_itself(behind, permanent=False)


@pytest.mark.parametrize("target", [D("0"), D("-1"), D("10.001")])
def test_a_target_is_positive_in_cents(target: Decimal) -> None:
    with pytest.raises(GoalError, match="target"):
        check_goal(target, deadline=Month(2027, 8), start=OCT, this_month=OCT)


def test_a_deadline_is_never_past_and_a_start_never_to_come() -> None:
    with pytest.raises(GoalError, match="deadline"):
        check_goal(D("100"), deadline=Month(2026, 9), start=OCT, this_month=OCT)
    with pytest.raises(GoalError, match="start"):
        check_goal(D("100"), deadline=Month(2027, 8), start=OCT.next(), this_month=OCT)
    # an earlier start counts progress already made
    check_goal(D("100"), deadline=Month(2027, 8), start=Month(2026, 1), this_month=OCT)


def test_the_tier_follows_the_deadline_and_moves_down_as_it_nears() -> None:
    # short: up to a year; medium: over a year, up to five; long: beyond five
    assert tier_of(Month(2027, 10), this_month=OCT) is Tier.SHORT  # 12 months
    assert tier_of(Month(2027, 11), this_month=OCT) is Tier.MEDIUM
    assert tier_of(Month(2031, 10), this_month=OCT) is Tier.MEDIUM  # 60 months
    assert tier_of(Month(2031, 11), this_month=OCT) is Tier.LONG
    # a year later, the same deadline has come down a tier
    assert tier_of(Month(2031, 11), this_month=Month(2027, 10)) is Tier.MEDIUM
    assert tier_of(Month(2026, 9), this_month=OCT) is Tier.SHORT  # overdue


def test_the_precaution_is_the_pyramids_foundation() -> None:
    assert list(Tier) == [Tier.PRECAUTION, Tier.SHORT, Tier.MEDIUM, Tier.LONG]
    assert tier_of(None, this_month=OCT, precaution=True) is Tier.PRECAUTION
    assert tier_of(Month(2029, 1), this_month=OCT, precaution=True) is Tier.PRECAUTION
    # a permanent goal without a deadline is in the short term
    assert tier_of(None, this_month=OCT) is Tier.SHORT


def test_one_open_precaution_per_member_and_one_joint() -> None:
    check_precaution_slot([], ME, Visibility.PRIVATE)
    taken = [(ME, Visibility.SHARED), (OTHER, Visibility.JOINT)]
    with pytest.raises(GoalError, match="precaution"):
        check_precaution_slot(taken, ME, Visibility.PRIVATE)
    with pytest.raises(GoalError, match="precaution"):
        check_precaution_slot(taken, ME, Visibility.JOINT)
    check_precaution_slot(taken, OTHER, Visibility.SHARED)


# F-GOAL-2: the precaution's proposal


def test_fixed_expenses_are_the_monthly_equivalent_of_their_outflows() -> None:
    items = [
        (Frequency.MONTHLY, D("-900")),  # rent
        (Frequency.QUARTERLY, D("-90")),  # 30
        (Frequency.YEARLY, D("-600")),  # 50
        (Frequency.MONTHLY, D("2500")),  # a salary is no expense
    ]
    assert fixed_expenses(items) == D("980.00")


def test_the_proposal_is_a_number_of_months_of_fixed_expenses() -> None:
    assert precaution_proposal(D("1032.00"), 6) == D("6192.00")
    for months in (0, 13):
        with pytest.raises(GoalError, match="months"):
            precaution_proposal(D("1032.00"), months)


# F-GOAL-3: funding


def test_a_goal_uses_its_owners_lines_and_joint_ones_never_a_debt() -> None:
    def ok(goal_visibility: Visibility, line_owner: object, line_visibility: Visibility) -> bool:
        try:
            check_funding_line(
                goal_owner_id=ME,
                goal_visibility=goal_visibility,
                line_owner_id=line_owner,  # type: ignore[arg-type]
                line_visibility=line_visibility,
                line_kind=WealthKind.ASSET,
            )
        except GoalError:
            return False
        return True

    assert ok(Visibility.PRIVATE, ME, Visibility.PRIVATE)
    assert not ok(Visibility.SHARED, ME, Visibility.PRIVATE)
    assert ok(Visibility.SHARED, ME, Visibility.SHARED)
    assert ok(Visibility.PRIVATE, OTHER, Visibility.JOINT)
    assert not ok(Visibility.SHARED, OTHER, Visibility.SHARED)
    assert ok(Visibility.JOINT, OTHER, Visibility.JOINT)
    assert not ok(Visibility.JOINT, ME, Visibility.SHARED)
    with pytest.raises(GoalError, match="debt"):
        check_funding_line(
            goal_owner_id=ME,
            goal_visibility=Visibility.PRIVATE,
            line_owner_id=ME,
            line_visibility=Visibility.PRIVATE,
            line_kind=WealthKind.DEBT,
        )


def test_a_lines_shares_sum_to_100_percent_at_most() -> None:
    check_line_shares([100])
    check_line_shares([30, 70])
    for shares in ([60, 41], [0], [101]):
        with pytest.raises(GoalError, match="share"):
            check_line_shares(shares)


LDDS, PEA = uuid4(), uuid4()
JUL, MAY = Month(2026, 7), Month(2027, 5)


def _funded(
    target: str,
    *envelopes: Envelope,
    start: Month = JUL,
    deadline: Month | None = MAY,
    precaution: bool = False,
    closed_from: Month | None = None,
    adjustments: dict[tuple[UUID, Month], Decimal] | None = None,
) -> FundedGoal:
    return FundedGoal(
        uuid4(), D(target), start, envelopes, deadline, precaution, closed_from, adjustments or {}
    )


def _series(*amounts: int, start: Month = JUL) -> dict[Month, Decimal]:
    return {m: D(a) for m, a in zip(_months(start, len(amounts)), amounts, strict=True)}


def test_a_withdrawal_comes_out_of_the_free_part_first() -> None:
    # 8500 on the LDDS, a 2500 trip: 250 set aside, 1000 taken for something else, then nearly all
    trip = _funded("2500", Envelope(LDDS, 100))
    held = envelopes(
        {LDDS: Line(_series(8500, 8750, 7750, 200))}, [trip], _months(Month(2026, 7), 4)
    )
    assert held.value(trip.id) == [D("0"), D("250"), D("250"), D("200")]
    assert held.free(LDDS) == [D("8500"), D("8500"), D("7500"), D("0")]


def test_an_opening_amount_is_taken_from_the_free_part() -> None:
    first = _funded("9000", Envelope(LDDS, 50, D("6000")))
    second = _funded("9000", Envelope(LDDS, 50, D("6000")))
    held = envelopes({LDDS: Line(_series(8500))}, [first, second], [Month(2026, 7)])
    assert (held.value(first.id), held.value(second.id)) == ([D("6000")], [D("2500")])


def test_a_rise_is_shared_out_never_beyond_a_target() -> None:
    big = _funded("5000", Envelope(LDDS, 60))
    small = _funded("300", Envelope(LDDS, 40))
    held = envelopes({LDDS: Line(_series(0, 1000, 2000))}, [big, small], _months(Month(2026, 7), 3))
    assert held.value(big.id) == [D("0"), D("600"), D("1200")]
    # 400 then nothing more: the rest stays free
    assert held.value(small.id) == [D("0"), D("300"), D("300")]
    assert held.free(LDDS) == [D("0"), D("100"), D("500")]


def test_a_rise_on_one_line_never_takes_a_goal_beyond_its_target() -> None:
    trip = _funded("1000", Envelope(LDDS, 100, D("800")), Envelope(PEA, 100))
    lines = {LDDS: Line(_series(800, 800)), PEA: Line(_series(0, 500))}
    held = envelopes(lines, [trip], _months(Month(2026, 7), 2))
    assert held.value(trip.id) == [D("800"), D("1000")]


def test_a_line_worth_less_than_its_goals_cuts_the_farthest_deadline_first() -> None:
    fund = _funded("400", Envelope(LDDS, 40, D("400")), deadline=None, precaution=True)
    trip = _funded("300", Envelope(LDDS, 30, D("300")), deadline=Month(2027, 3))
    house = _funded("300", Envelope(LDDS, 30, D("300")), deadline=Month(2032, 1))
    held = envelopes(
        {LDDS: Line(_series(1000, 500, 100))}, [fund, trip, house], _months(Month(2026, 7), 3)
    )
    assert held.value(house.id) == [D("300"), D("0"), D("0")]
    assert held.value(trip.id) == [D("300"), D("100"), D("0")]
    assert held.value(fund.id) == [D("400"), D("400"), D("100")]


def test_an_adjusted_envelope_holds_the_amount_set_then_goes_on() -> None:
    # 2000 parked on the LDDS in August, not for the trip: brought back to 200
    aug = Month(2026, 8)
    trip = _funded("2500", Envelope(LDDS, 100), adjustments={(LDDS, aug): D("200")})
    held = envelopes({LDDS: Line(_series(8500, 10500, 10750))}, [trip], _months(JUL, 3))
    assert held.value(trip.id) == [D("0"), D("200"), D("450")]
    assert held.free(LDDS) == [D("8500"), D("10300"), D("10300")]


def test_an_adjustment_never_takes_more_than_the_line_allows_or_the_target() -> None:
    fund = _funded("9000", Envelope(LDDS, 50, D("800")), deadline=None, precaution=True)
    trip = _funded("600", Envelope(LDDS, 50), adjustments={(LDDS, Month(2026, 8)): D("5000")})
    held = envelopes({LDDS: Line(_series(1000, 1000))}, [fund, trip], _months(JUL, 2))
    # the target caps it, then what the line holds beyond the other envelope
    assert held.value(trip.id) == [D("0"), D("200")]
    assert held.value(fund.id) == [D("800"), D("800")]


def test_a_closed_goal_or_line_frees_its_envelopes() -> None:
    sep, octo = Month(2026, 9), Month(2026, 10)
    done = _funded("2000", Envelope(LDDS, 50, D("1000")), closed_from=sep)
    other = _funded("9000", Envelope(LDDS, 50))
    held = envelopes(
        {LDDS: Line(_series(1000, 1000, 1400, 1400), closed_from=octo)},
        [done, other],
        _months(Month(2026, 7), 4),
    )
    assert held.value(done.id) == [D("1000"), D("1000"), D("0"), D("0")]
    # the freed 1000 stays free: only rises count
    assert held.value(other.id) == [D("0"), D("0"), D("200"), D("0")]


# F-GOAL-4 and 5: tracking, status and estimates

JAPAN_START = Month(2026, 3)
JAPAN_VALUES = [D(v) for v in (800, 1100, 1450, 1800, 2100, 2450, 2780, 3100)]


def test_tracking_gives_the_months_with_value_gain_expected_and_gap() -> None:
    t = track(D("6000"), JAPAN_START, Month(2027, 8), JAPAN_VALUES, this_month=OCT)
    first, last = t.months[0], t.months[-1]
    assert (first.month, first.value, first.gained, first.expected) == (
        JAPAN_START,
        D("800"),
        None,
        D("800.00"),
    )
    # 800 + 5200 x 7 / 17 = 2941.18
    assert (last.month, last.gained, last.expected, last.gap) == (
        OCT,
        D("320"),
        D("2941.18"),
        D("158.82"),
    )


def test_estimates_against_the_deadline() -> None:
    t = track(D("6000"), JAPAN_START, Month(2027, 8), JAPAN_VALUES, this_month=OCT)
    assert t.progress == D("3100") / D("6000")
    assert (t.remaining, t.months_left, t.required) == (D("2900"), 10, D("290.00"))
    assert t.actual == D("333.33")  # (3100 - 1100) / 6
    assert t.estimated == Month(2027, 7)  # 2900 / 333.33 = 8.7, rounded up to 9 months
    assert (t.months_early, t.extra) == (1, None)
    assert t.status is GoalStatus.AHEAD  # 3100 is 5.4 % above 2941.18


def test_a_late_goal_says_the_extra_effort_that_keeps_the_date() -> None:
    values = [D(v) for v in (300, 420, 560, 690, 800, 900)]
    t = track(D("2500"), Month(2026, 5), Month(2027, 6), values, this_month=OCT)
    assert t.status is GoalStatus.BEHIND
    assert (t.required, t.actual) == (D("200.00"), D("120.00"))
    assert (t.estimated, t.months_early, t.extra) == (Month(2027, 12), -6, D("80.00"))


def test_ahead_reached_and_fill_first() -> None:
    values = [D("0"), D("2000")]
    ahead = track(D("10000"), Month(2026, 9), Month(2031, 9), values, this_month=OCT)
    assert ahead.status is GoalStatus.AHEAD
    reached = track(D("2000"), Month(2026, 9), Month(2027, 9), values, this_month=OCT)
    assert (reached.status, reached.remaining, reached.estimated) == (GoalStatus.REACHED, 0, OCT)
    prec = track(D("5000"), Month(2026, 9), None, values, this_month=OCT, precaution=True)
    assert prec.status is GoalStatus.FILL_FIRST
    assert (prec.months_left, prec.required, prec.months[-1].expected) == (None, None, None)
    # another short-term goal is tracked against its deadline
    trip = track(D("3000"), Month(2026, 9), Month(2027, 3), values, this_month=OCT)
    assert trip.status is GoalStatus.AHEAD
    # a permanent goal without a deadline has no pace to keep
    works = track(D("5000"), Month(2026, 9), None, values, this_month=OCT)
    assert works.status is GoalStatus.OPEN


def test_without_history_or_progress_there_is_no_estimated_date() -> None:
    young = track(D("1000"), OCT, Month(2027, 10), [D("100")], this_month=OCT)
    assert (young.actual, young.estimated, young.never) == (None, None, False)
    stuck = track(D("1000"), Month(2026, 9), Month(2027, 10), [D("200"), D("150")], this_month=OCT)
    assert (stuck.actual, stuck.estimated, stuck.never) == (D("-50.00"), None, True)


def test_a_goal_at_its_deadline_month_needs_what_is_left() -> None:
    t = track(D("1000"), Month(2026, 9), OCT, [D("0"), D("400")], this_month=OCT)
    assert (t.months_left, t.required) == (0, D("600.00"))


def test_values_must_cover_the_months_from_the_start() -> None:
    with pytest.raises(ValueError, match="month"):
        track(D("1000"), Month(2026, 9), Month(2027, 9), [D("1")], this_month=OCT)


# F-GOAL-6: the month's effort plan


def test_capacity_is_the_average_net_cash_flow_never_below_zero() -> None:
    assert capacity([D("1000"), D("1700"), D("-200")]) == D("833.33")
    assert capacity([D("-500")]) == D("0")
    assert capacity([]) == D("0")
    assert capacity([D(v) for v in (9, 9, 1, 1, 1, 1, 1, 1)]) == D("1")  # the last 6 only


def test_the_precaution_takes_its_share_first_then_the_others_by_required_effort() -> None:
    prec, japan, home = uuid4(), uuid4(), uuid4()
    plan = effort_plan(
        D("1350"),
        D("0.7"),
        precaution={prec: D("2300")},
        others={japan: D("290"), home: D("484")},
    )
    assert plan.allocations[prec] == D("945.00")
    # 405 shared 290 : 484, rounded down
    assert (plan.allocations[japan], plan.allocations[home]) == (D("151.74"), D("253.25"))
    assert plan.months_to_fill == 3
    assert plan.shortfall == D("369.01")
    assert plan.unallocated == D("0.01")


def test_what_the_others_do_not_need_goes_to_the_precaution_then_is_unallocated() -> None:
    prec, japan = uuid4(), uuid4()
    plan = effort_plan(D("1000"), D("0.5"), precaution={prec: D("700")}, others={japan: D("100")})
    assert (plan.allocations[prec], plan.allocations[japan]) == (D("700"), D("100"))
    assert (plan.unallocated, plan.shortfall, plan.months_to_fill) == (D("200"), D("0"), 1)


def test_without_a_gap_the_precaution_takes_nothing() -> None:
    prec, japan = uuid4(), uuid4()
    plan = effort_plan(D("500"), D("0.7"), precaution={prec: D("0")}, others={japan: D("300")})
    assert (plan.allocations[prec], plan.allocations[japan]) == (D("0"), D("300"))
    assert (plan.months_to_fill, plan.unallocated) == (None, D("200"))


def test_the_precaution_share_is_between_50_and_100_percent() -> None:
    for share in (D("0.49"), D("1.01")):
        with pytest.raises(GoalError, match="share"):
            effort_plan(D("100"), share, precaution={}, others={})


# F-GOAL-7: the pyramid


def test_each_tier_is_filled_by_its_goals_values_over_their_targets() -> None:
    tiers = pyramid(
        [
            PyramidGoal(Tier.PRECAUTION, D("12400"), D("14700")),
            PyramidGoal(Tier.MEDIUM, D("3100"), D("6000")),
            PyramidGoal(Tier.MEDIUM, D("3000"), D("2500")),  # beyond its target: counts 2500
        ]
    )
    assert (tiers[Tier.MEDIUM].value, tiers[Tier.MEDIUM].target) == (D("6100"), D("8500"))
    assert tiers[Tier.MEDIUM].progress == D("5600") / D("8500")
    assert (tiers[Tier.LONG].target, tiers[Tier.LONG].progress) == (D("0"), None)


# §8 invariants 19 and 20

amounts = st.integers(0, 10_000_000).map(lambda c: D(c) / 100)
MONTHS = _months(Month(2026, 1), 6)


@given(
    st.lists(st.dictionaries(st.sampled_from(MONTHS), amounts, max_size=6), min_size=1, max_size=3),
    st.lists(
        st.tuples(
            st.sampled_from(MONTHS),
            amounts,
            st.lists(st.tuples(st.integers(0, 2), st.integers(1, 100), amounts), max_size=3),
            st.booleans(),
            st.sampled_from([None, Month(2027, 1), Month(2032, 1)]),
            st.lists(amounts, max_size=3),
        ),
        max_size=4,
    ),
)
def test_goals_never_hold_more_than_their_lines_and_a_covered_fall_changes_none(
    series: list[dict[Month, Decimal]], drawn: list[tuple[Any, ...]]
) -> None:
    line_ids = [uuid4() for _ in series]
    lines = {i: Line(v) for i, v in zip(line_ids, series, strict=True)}
    left = dict.fromkeys(line_ids, 100)
    goals = []
    for start, target, wanted, precaution, deadline, wanted_adjust in drawn:
        envs, used = [], set()
        for index, share, opening in wanted:
            line = line_ids[index % len(line_ids)]
            take = min(share, left[line])
            if take and line not in used:
                used.add(line)
                left[line] -= take
                envs.append(Envelope(line, take, opening))
        adjust = {
            (e.line, month): amount
            for e, month, amount in zip(envs, MONTHS[::2], wanted_adjust, strict=False)
        }
        goals.append(
            _funded(
                str(target + 1),
                *envs,
                start=start,
                deadline=deadline,
                precaution=precaution,
                adjustments=adjust,
            )
        )
    held = envelopes(lines, goals, MONTHS)
    for k, month in enumerate(MONTHS):
        for line in line_ids:
            cell = line_cell(lines[line].values, month)
            worth = max(D(0), cell.amount) if cell else D(0)
            amounts_on_line = [held.held(g.id, line)[k] for g in goals]
            assert all(a >= 0 for a in amounts_on_line)
            assert sum(amounts_on_line) <= worth
            assert held.free(line)[k] == worth - sum(amounts_on_line)
            if k and worth < line_worth(lines[line], MONTHS[k - 1]):
                before = [held.held(g.id, line)[k - 1] for g in goals if g.start < month]
                # a goal adjusted that month holds what was set; the others stay as they were
                kept = [g for g in goals if g.start < month and (line, month) not in g.adjustments]
                if worth >= sum(before):
                    assert [held.held(g.id, line)[k - 1] for g in kept] == [
                        held.held(g.id, line)[k] for g in kept
                    ]
        for g in goals:
            assert held.value(g.id)[k] <= g.target


@given(
    amounts,
    st.sampled_from([D("0.5"), D("0.7"), D("1")]),
    st.lists(amounts, max_size=3),
    st.lists(amounts, max_size=5),
)
def test_the_effort_plan_never_hands_out_more_than_the_capacity_or_the_needs(
    cap: Decimal, share: Decimal, gaps: list[Decimal], required: list[Decimal]
) -> None:
    precaution = {uuid4(): g for g in gaps}
    others = {uuid4(): r for r in required}
    plan = effort_plan(cap, share, precaution=precaution, others=others)
    assert sum(plan.allocations.values()) + plan.unallocated == cap
    assert plan.unallocated >= 0
    for goal_id, need in (precaution | others).items():
        assert 0 <= plan.allocations[goal_id] <= need
    to_prec = sum(plan.allocations[g] for g in precaution)
    # the precaution gets the least of its gap and its share before anyone else (to the cent)
    assert to_prec >= min(sum(gaps), cap * share) - D("0.01") * (len(gaps) + 1)
