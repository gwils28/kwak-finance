from decimal import Decimal
from uuid import uuid4

import pytest
from hypothesis import given
from hypothesis import strategies as st
from kwak_core.accounts import Visibility
from kwak_core.budget import Month
from kwak_core.goals import (
    Funding,
    GoalError,
    GoalStatus,
    PyramidGoal,
    Tier,
    capacity,
    check_funding_line,
    check_goal,
    check_line_shares,
    check_precaution_slot,
    effort_plan,
    fixed_expenses,
    goal_values,
    horizon_flagged,
    precaution_proposal,
    pyramid,
    track,
)
from kwak_core.recurring import Frequency
from kwak_core.wealth import WealthKind

D = Decimal
ME, OTHER = uuid4(), uuid4()
OCT = Month(2026, 10)


def _months(start: Month, n: int) -> list[Month]:
    out = [start]
    while len(out) < n:
        out.append(out[-1].next())
    return out


# F-GOAL-1: a goal's fields


def test_medium_and_long_term_goals_need_a_deadline() -> None:
    check_goal(Tier.PRECAUTION, D("5000"), deadline=None, start=OCT, this_month=OCT)
    for tier in (Tier.MEDIUM, Tier.LONG):
        with pytest.raises(GoalError, match="deadline"):
            check_goal(tier, D("5000"), deadline=None, start=OCT, this_month=OCT)


@pytest.mark.parametrize("target", [D("0"), D("-1"), D("10.001")])
def test_a_target_is_positive_in_cents(target: Decimal) -> None:
    with pytest.raises(GoalError, match="target"):
        check_goal(Tier.MEDIUM, target, deadline=Month(2027, 8), start=OCT, this_month=OCT)


def test_a_deadline_is_never_past_and_a_start_never_to_come() -> None:
    with pytest.raises(GoalError, match="deadline"):
        check_goal(Tier.MEDIUM, D("100"), deadline=Month(2026, 9), start=OCT, this_month=OCT)
    with pytest.raises(GoalError, match="start"):
        check_goal(Tier.MEDIUM, D("100"), deadline=Month(2027, 8), start=OCT.next(), this_month=OCT)
    # an earlier start counts progress already made
    check_goal(Tier.MEDIUM, D("100"), deadline=Month(2027, 8), start=Month(2026, 1), this_month=OCT)


def test_a_deadline_outside_the_tiers_horizon_is_flagged_not_refused() -> None:
    assert not horizon_flagged(Tier.MEDIUM, Month(2028, 10), this_month=OCT)  # 2 years
    assert horizon_flagged(Tier.MEDIUM, Month(2027, 3), this_month=OCT)  # under a year
    assert horizon_flagged(Tier.MEDIUM, Month(2032, 10), this_month=OCT)  # beyond 5 years
    assert not horizon_flagged(Tier.LONG, Month(2032, 10), this_month=OCT)
    assert horizon_flagged(Tier.LONG, Month(2029, 10), this_month=OCT)
    assert not horizon_flagged(Tier.PRECAUTION, None, this_month=OCT)
    assert horizon_flagged(Tier.PRECAUTION, Month(2028, 10), this_month=OCT)


def test_one_open_precaution_per_member_and_one_joint() -> None:
    check_precaution_slot([], ME, Visibility.PRIVATE)
    taken = [(ME, Visibility.SHARED), (OTHER, Visibility.JOINT)]
    with pytest.raises(GoalError, match="precaution"):
        check_precaution_slot(taken, ME, Visibility.PRIVATE)
    with pytest.raises(GoalError, match="precaution"):
        check_precaution_slot(taken, ME, Visibility.JOINT)
    check_precaution_slot(taken, OTHER, Visibility.SHARED)


# F-GOAL-2: the precaution's proposal


def test_fixed_expenses_are_the_monthly_equivalent_of_recurring_outflows() -> None:
    items = [
        (Frequency.MONTHLY, D("-900")),  # rent
        (Frequency.WEEKLY, D("-12")),  # 12 x 52 / 12 = 52
        (Frequency.QUARTERLY, D("-90")),  # 30
        (Frequency.YEARLY, D("-600")),  # 50
        (Frequency.MONTHLY, D("2500")),  # a salary is no expense
    ]
    assert fixed_expenses(items) == D("1032.00")


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


def test_a_goals_value_is_its_lines_values_times_their_shares() -> None:
    sep = Month(2026, 9)
    livret = {Month(2026, 8): D("1000"), OCT: D("1200")}
    pea = {sep: D("333.33")}
    values = goal_values(
        [Funding(livret, 100), Funding(pea, 50, closed_from=Month(2026, 11))],
        _months(Month(2026, 7), 5),
    )
    # nothing before the first value, carried forward, a share rounded down, nothing once closed
    assert values == [D("0"), D("1000"), D("1166.66"), D("1366.66"), D("1200")]


# F-GOAL-4 and 5: tracking, status and estimates

JAPAN_START = Month(2026, 3)
JAPAN_VALUES = [D(v) for v in (800, 1100, 1450, 1800, 2100, 2450, 2780, 3100)]


def test_tracking_gives_the_months_with_value_gain_expected_and_gap() -> None:
    t = track(Tier.MEDIUM, D("6000"), JAPAN_START, Month(2027, 8), JAPAN_VALUES, this_month=OCT)
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
    t = track(Tier.MEDIUM, D("6000"), JAPAN_START, Month(2027, 8), JAPAN_VALUES, this_month=OCT)
    assert t.progress == D("3100") / D("6000")
    assert (t.remaining, t.months_left, t.required) == (D("2900"), 10, D("290.00"))
    assert t.actual == D("333.33")  # (3100 - 1100) / 6
    assert t.estimated == Month(2027, 7)  # 2900 / 333.33 = 8.7, rounded up to 9 months
    assert (t.months_early, t.extra) == (1, None)
    assert t.status is GoalStatus.AHEAD  # 3100 is 5.4 % above 2941.18


def test_a_late_goal_says_the_extra_effort_that_keeps_the_date() -> None:
    values = [D(v) for v in (300, 420, 560, 690, 800, 900)]
    t = track(Tier.MEDIUM, D("2500"), Month(2026, 5), Month(2027, 6), values, this_month=OCT)
    assert t.status is GoalStatus.BEHIND
    assert (t.required, t.actual) == (D("200.00"), D("120.00"))
    assert (t.estimated, t.months_early, t.extra) == (Month(2027, 12), -6, D("80.00"))


def test_ahead_reached_and_fill_first() -> None:
    values = [D("0"), D("2000")]
    ahead = track(Tier.LONG, D("10000"), Month(2026, 9), Month(2031, 9), values, this_month=OCT)
    assert ahead.status is GoalStatus.AHEAD
    reached = track(Tier.MEDIUM, D("2000"), Month(2026, 9), Month(2027, 9), values, this_month=OCT)
    assert (reached.status, reached.remaining, reached.estimated) == (GoalStatus.REACHED, 0, OCT)
    prec = track(Tier.PRECAUTION, D("5000"), Month(2026, 9), None, values, this_month=OCT)
    assert prec.status is GoalStatus.FILL_FIRST
    assert (prec.months_left, prec.required, prec.months[-1].expected) == (None, None, None)


def test_without_history_or_progress_there_is_no_estimated_date() -> None:
    young = track(Tier.MEDIUM, D("1000"), OCT, Month(2027, 10), [D("100")], this_month=OCT)
    assert (young.actual, young.estimated, young.never) == (None, None, False)
    stuck = track(
        Tier.MEDIUM,
        D("1000"),
        Month(2026, 9),
        Month(2027, 10),
        [D("200"), D("150")],
        this_month=OCT,
    )
    assert (stuck.actual, stuck.estimated, stuck.never) == (D("-50.00"), None, True)


def test_a_goal_at_its_deadline_month_needs_what_is_left() -> None:
    t = track(Tier.MEDIUM, D("1000"), Month(2026, 9), OCT, [D("0"), D("400")], this_month=OCT)
    assert (t.months_left, t.required) == (0, D("600.00"))


def test_values_must_cover_the_months_from_the_start() -> None:
    with pytest.raises(ValueError, match="month"):
        track(Tier.MEDIUM, D("1000"), Month(2026, 9), Month(2027, 9), [D("1")], this_month=OCT)


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
    st.lists(st.dictionaries(st.sampled_from(MONTHS), amounts, max_size=6), min_size=1, max_size=4),
    st.lists(st.lists(st.integers(1, 100), min_size=1, max_size=4), min_size=1, max_size=4),
    st.data(),
)
def test_goals_never_hold_more_than_their_lines_are_worth(
    lines: list[dict[Month, Decimal]], goals_lines: list[list[int]], data: st.DataObject
) -> None:
    # Each goal funds itself from some lines; shares are drawn so no line exceeds 100 %.
    left = [100] * len(lines)
    goals: list[list[Funding]] = []
    for wanted in goals_lines:
        fundings = []
        for share in wanted:
            i = data.draw(st.integers(0, len(lines) - 1))
            take = min(share, left[i])
            if take:
                left[i] -= take
                fundings.append(Funding(lines[i], take))
        goals.append(fundings)
    worth = goal_values([Funding(line, 100) for line in lines], MONTHS)
    held = [goal_values(f, MONTHS) for f in goals]
    for k in range(len(MONTHS)):
        assert sum(h[k] for h in held) <= worth[k]


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
