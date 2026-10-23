from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from hypothesis import given
from hypothesis import strategies as st
from kwak_core.budget import Month
from kwak_core.goal_analysis import (
    Dismissal,
    GoalFacts,
    LineRisk,
    Notice,
    Rule,
    Severity,
    Zone,
    behind_notices,
    data_notices,
    forward_efforts,
    hidden,
    history,
    loss_one_in_ten,
    no_gain_notices,
    overcommitted_notices,
    precaution_notices,
    reference_month,
    select,
    stale_lines,
    unfunded_notices,
    weighted,
    weights,
    zone,
)
from kwak_core.goals import GoalStatus, Line, Tier, add_months, track
from kwak_core.money import quantize

D = Decimal
OCT = Month(2026, 10)
SEP = Month(2026, 9)
JAN = Month(2026, 1)
A, B, C = uuid4(), uuid4(), uuid4()


def _facts(
    target: str,
    values: list[str],
    *,
    deadline: Month | None,
    start: Month = JAN,
    precaution: bool = False,
    held: dict[UUID, Decimal] | None = None,
    shares: dict[UUID, int] | None = None,
    volatility: str = "0",
    goal: UUID | None = None,
) -> GoalFacts:
    vals = [D(v) for v in values]
    return GoalFacts(
        id=goal or uuid4(),
        target=D(target),
        start=start,
        deadline=deadline,
        history=history(D(target), start, deadline, vals, precaution=precaution),
        held=held if held is not None else {A: vals[-1]},
        shares=shares if shares is not None else {A: 100},
        precaution=precaution,
        volatility=D(volatility),
    )


# F-ANA-1: the reference month


def test_the_reference_month_is_the_last_with_every_funding_line_entered() -> None:
    lines = {
        A: Line({Month(2026, 8): D(10), SEP: D(20), OCT: D(30)}),
        B: Line({Month(2026, 8): D(10), SEP: D(20)}),
    }
    assert reference_month(lines.values(), OCT, floor=Month(2026, 1)) == SEP


def test_the_current_month_is_the_reference_once_it_is_all_entered() -> None:
    lines = [Line({SEP: D(20), OCT: D(30)}), Line({OCT: D(1)})]
    assert reference_month(lines, OCT, floor=Month(2026, 1)) == OCT


def test_a_closed_line_or_one_not_yet_opened_is_not_waited_for() -> None:
    lines = [
        Line({Month(2026, 7): D(5)}, closed_from=Month(2026, 8)),
        Line({SEP: D(1), OCT: D(2)}),
        Line({Month(2026, 8): D(3), SEP: D(4), OCT: D(5)}),
    ]
    assert reference_month(lines, OCT, floor=Month(2026, 1)) == OCT


def test_no_reference_month_when_nothing_is_entered() -> None:
    assert reference_month([Line({})], OCT, floor=Month(2026, 1)) is None


def test_stale_lines_lack_a_value_for_the_last_complete_month() -> None:
    lines = {
        A: Line({SEP: D(1)}),
        B: Line({Month(2026, 8): D(1)}),
        C: Line({}),
        uuid4(): Line({OCT: D(1)}),
    }
    assert stale_lines(lines, OCT) == [B, C]


# F-ANA-2: required effort against capacity


def test_bands_are_constant_until_the_month_before_the_deadline() -> None:
    fwd = forward_efforts(OCT, {A: (D(100), 3), B: (D(50), 1)}, capacity=D(120), horizon=12)
    assert fwd.months[:4] == [OCT, Month(2026, 11), Month(2026, 12), Month(2027, 1)]
    assert fwd.totals[:4] == [D(150), D(100), D(100), D(0)]
    assert fwd.over == 1
    assert fwd.peak == D(30)


def test_a_goal_due_this_month_takes_one_month() -> None:
    fwd = forward_efforts(OCT, {A: (D(300), 0)}, capacity=D(0), horizon=12)
    assert fwd.totals[:2] == [D(300), D(0)]


def test_the_horizon_is_12_to_60_months() -> None:
    with pytest.raises(ValueError, match="horizon"):
        forward_efforts(OCT, {}, capacity=D(0), horizon=6)


@given(
    st.dictionaries(
        st.uuids(),
        st.tuples(st.decimals(0, 5000, places=2), st.integers(0, 80)),
        max_size=6,
    )
)
def test_the_stack_never_rises(bands: dict[UUID, tuple[Decimal, int]]) -> None:
    """Invariant §8.31."""
    fwd = forward_efforts(OCT, bands, capacity=D(0), horizon=60)
    assert all(a >= b for a, b in zip(fwd.totals, fwd.totals[1:], strict=False))


@given(st.decimals(1, 100_000, places=2), st.integers(2, 120))
def test_paying_the_required_effort_keeps_it(remaining: Decimal, months: int) -> None:
    """Invariant §8.31, to the cent: what is left over what is left of the time."""
    deadline = add_months(OCT, months)
    first = track(remaining, OCT, deadline, [D(0)], this_month=OCT).required
    assert first is not None
    nxt = track(remaining, OCT, deadline, [D(0), first], this_month=OCT.next()).required
    assert nxt is not None
    assert abs(nxt - first) <= D("0.01")


# F-ANA-4: horizon and risk


def test_weights_follow_the_envelopes_then_the_shares() -> None:
    assert weights({A: D(300), B: D(100)}, {A: 50, B: 50}) == {A: D("0.75"), B: D("0.25")}
    assert weights({A: D(0), B: D(0)}, {A: 20, B: 60}) == {A: D("0.25"), B: D("0.75")}
    assert weights({}, {}) == {}


@given(
    st.dictionaries(st.uuids(), st.decimals(0, 10_000, places=2), min_size=1, max_size=5),
    st.data(),
)
def test_weighted_volatility_lies_between_its_lines(
    held: dict[UUID, Decimal], data: st.DataObject
) -> None:
    """Invariant §8.33."""
    shares = {k: data.draw(st.integers(1, 100)) for k in held}
    vols = {k: data.draw(st.decimals(0, 1, places=2)) for k in held}
    w = weights(held, shares)
    assert all(v > 0 for v in w.values())
    assert abs(sum(w.values(), D(0)) - 1) < D("1e-20")
    sigma = weighted(w, vols)
    assert min(vols.values()) - D("1e-20") <= sigma <= max(vols.values()) + D("1e-20")


def test_the_loss_in_one_outcome_in_ten_matches_the_lognormal() -> None:
    assert loss_one_in_ten(D("0.07"), D("0.16"), 12).quantize(D("0.001")) == D("-0.125")
    assert loss_one_in_ten(D("0.03"), D("0.06"), 24).quantize(D("0.001")) == D("-0.049")
    assert loss_one_in_ten(D("0.017"), D(0), 12).quantize(D("0.001")) == D("0.017")


@pytest.mark.parametrize(
    ("months", "sigma", "volatile", "real", "expected"),
    [
        (12, "0.16", "1", "0.05", Zone.RED_SHORT),
        (24, "0.05", "1", "0", Zone.NONE),
        (48, "0.16", "0.5", "0.05", Zone.NONE),
        (48, "0.16", "0.7", "0.05", Zone.AMBER_GLIDE),
        (120, "0", "0", "-0.003", Zone.RED_ERODING),
        (90, "0", "0", "-0.003", Zone.NONE),
    ],
)
def test_zones(months: int, sigma: str, volatile: str, real: str, expected: Zone) -> None:
    assert zone(months, D(sigma), D(volatile), D(real)) is expected


# F-ANA-6: status by month


def test_history_gives_each_months_status() -> None:
    h = history(D(1200), OCT.previous().previous(), Month(2027, 8), [D(0), D(0), D(300)])
    assert [t.status for t in h] == [GoalStatus.ON, GoalStatus.BEHIND, GoalStatus.AHEAD]


# F-ANA-8: points to look at


def test_stale_data_and_short_capacity_come_first() -> None:
    notices = data_notices([A, B], capacity_months=2)
    assert [(n.rule, n.lines, n.severity) for n in notices] == [
        (Rule.DATA, (A, B), Severity.WARNING),
        (Rule.DATA, (), Severity.WARNING),
    ]
    assert data_notices([], capacity_months=3) == []


def test_no_precaution_is_a_warning() -> None:
    goal = _facts("1000", ["0"], deadline=Month(2027, 6), start=OCT)
    (notice,) = precaution_notices([goal], {A: LineRisk()}, monthly_fixed=D(1000))
    assert (notice.rule, notice.severity) == (Rule.PRECAUTION_NONE, Severity.WARNING)


@pytest.mark.parametrize(
    ("target", "severity"), [("2500", Severity.WARNING), ("4000", Severity.INFO), ("6000", None)]
)
def test_a_precaution_below_months_of_fixed_expenses(target: str, severity: Severity) -> None:
    goal = _facts(target, ["0"], deadline=None, start=OCT, precaution=True, held={})
    notices = precaution_notices([goal], {}, monthly_fixed=D(1000))
    assert [(n.rule, n.severity) for n in notices] == (
        [(Rule.PRECAUTION_LOW, severity)] if severity else []
    )
    if severity is Severity.WARNING:
        assert notices[0].amount == D(500)


def test_a_precaution_on_a_volatile_or_current_account_line() -> None:
    goal = _facts(
        "6000",
        ["6000"],
        deadline=None,
        start=OCT,
        precaution=True,
        held={A: D(1000), B: D(2000), C: D(3000)},
        shares={A: 10, B: 10, C: 10},
    )
    risks = {
        A: LineRisk(volatility=D("0.16"), ret=D("0.07")),
        B: LineRisk(current=True),
        C: LineRisk(ret=D("0.017")),
    }
    notices = precaution_notices([goal], risks, monthly_fixed=D(1000))
    assert [(n.rule, n.severity, n.amount) for n in notices] == [
        (Rule.PRECAUTION_RISKY, Severity.WARNING, D(1000)),
        (Rule.PRECAUTION_CURRENT, Severity.INFO, D(2000)),
    ]


def test_an_unfunded_goal_never_progresses() -> None:
    goal = _facts("800", ["0"], deadline=Month(2027, 6), start=OCT, held={}, shares={})
    (notice,) = unfunded_notices([goal])
    assert (notice.rule, notice.goal, notice.severity) == (Rule.UNFUNDED, goal.id, Severity.WARNING)


def _due(remaining: str, months: int, goal: UUID | None = None) -> GoalFacts:
    return _facts(remaining, ["0"], deadline=add_months(OCT, months), start=OCT, goal=goal)


def test_over_committed_postpones_the_farthest_goal_first() -> None:
    near, far = _due("1200", 12), _due("6000", 30)  # 100 + 200 a month
    (notice,) = overcommitted_notices(
        [near, far],
        capacity=D(250),
        capacity_months=6,
        allocations={},
        months_to_fill=None,
        this_month=OCT,
    )
    assert (notice.rule, notice.severity, notice.amount) == (
        Rule.OVERCOMMITTED,
        Severity.WARNING,
        D(50),
    )
    first, *others = notice.postponements
    assert (first.goal, first.months) == (far.id, 10)  # 6000 / 150 = 40 months
    assert first.deadline == add_months(OCT, 40)
    assert first.tier is Tier.MEDIUM
    assert first.lower_by == D(1500)
    assert [(p.goal, p.months) for p in others] == [(near.id, 12)]  # 1200 / 50 = 24


def test_over_committed_by_little_is_not_shown() -> None:
    goals = [_due("1200", 12)]
    assert (
        overcommitted_notices(
            goals,
            capacity=D(90),
            capacity_months=6,
            allocations={},
            months_to_fill=None,
            this_month=OCT,
        )
        == []
    )


def test_over_committed_only_while_the_precaution_fills_is_information() -> None:
    goal = _due("2400", 24)  # 100 a month, 45 from the plan while the precaution takes 105
    fund = _facts("5000", ["4580"], deadline=None, start=OCT, precaution=True)
    (notice,) = overcommitted_notices(
        [goal, fund],
        capacity=D(150),
        capacity_months=6,
        allocations={goal.id: D(45), fund.id: D(105)},
        months_to_fill=4,
        this_month=OCT,
    )
    assert notice.amount == D(55)  # 100 + 105 - 150; then (2400 - 4 * 45) / 20 = 111 fits
    assert notice.severity is Severity.INFO
    assert notice.figures["months_to_fill"] == 4


def test_over_committed_with_no_postponement_that_fits() -> None:
    goals = [_due("1200", 12), _due("1200", 12)]
    (notice,) = overcommitted_notices(
        goals,
        capacity=D(50),
        capacity_months=6,
        allocations={},
        months_to_fill=None,
        this_month=OCT,
    )
    assert notice.postponements == ()
    assert notice.amount == D(150)


@given(
    st.lists(
        st.tuples(st.decimals(100, 50_000, places=2), st.integers(1, 120)), min_size=1, max_size=5
    ),
    st.decimals(0, 3000, places=2),
    st.decimals(0, 1000, places=2),
)
def test_a_postponement_fits_exactly(
    goals: list[tuple[Decimal, int]], cap: Decimal, filling: Decimal
) -> None:
    """Invariant §8.32: next to what the precaution receives while it fills."""
    facts = [_due(str(r), n) for r, n in goals]
    fund = _facts("90000", ["0"], deadline=None, start=OCT, precaution=True)
    notices = overcommitted_notices(
        [*facts, fund],
        capacity=cap,
        capacity_months=6,
        allocations={fund.id: filling},
        months_to_fill=None,
        this_month=OCT,
    )
    required = {f.id: f.now.required or D(0) for f in facts}
    excess = sum(required.values(), D(0)) + filling - cap

    def fits(goal: GoalFacts, months: int) -> bool:
        return quantize(goal.now.remaining / months) <= required[goal.id] - excess

    def fewest(goal: GoalFacts) -> int | None:
        n = goal.now.months_left or 0
        return next((m for m in range(n + 1, n + 61) if fits(goal, m)), None)

    if not notices:
        assert excess <= max(D(20), D("0.05") * cap)
        return
    (notice,) = notices
    expected = [
        (f.id, m - (f.now.months_left or 0))
        for f in sorted(facts, key=lambda f: f.deadline or OCT, reverse=True)
        if (m := fewest(f)) is not None
    ]
    assert [(p.goal, p.months) for p in notice.postponements] == expected
    for p in notice.postponements:
        goal = next(f for f in facts if f.id == p.goal)
        n = goal.now.months_left or 0
        lowered = quantize((goal.now.remaining - p.lower_by) / max(1, n))
        assert lowered <= required[goal.id] - excess


def test_behind_for_three_months() -> None:
    start = add_months(OCT, -5)
    goal = _facts(
        "1200",
        ["0", "100", "100", "100", "100", "100"],
        deadline=add_months(start, 12),
        start=start,
    )
    (notice,) = behind_notices([goal])
    assert (notice.rule, notice.goal) == (Rule.BEHIND, goal.id)
    assert notice.severity is Severity.WARNING  # deadline 7 months away
    assert notice.amount == D(400)


def test_behind_is_not_shown_for_a_small_gap() -> None:
    start = add_months(OCT, -5)
    goal = _facts(
        "120000",
        ["0", "10000", "20000", "28000", "37500", "47000"],
        deadline=add_months(start, 12),
        start=start,
    )
    assert [t.status for t in goal.history[-3:]] == [GoalStatus.BEHIND] * 3
    assert behind_notices([goal]) == []


def test_behind_clears_after_two_months_not_behind() -> None:
    start = add_months(OCT, -7)
    behind = ["0", "100", "100", "100", "100", "100"]
    still = _facts("1200", [*behind, "700"], deadline=add_months(start, 12), start=start)
    cleared = _facts("1200", [*behind, "700", "800"], deadline=add_months(start, 12), start=start)
    (notice,) = behind_notices([still])
    assert notice.rule is Rule.BEHIND
    assert notice.amount == D(0)  # ahead this month, shown until a second month
    assert notice.figures["extra"] == D(0)
    assert behind_notices([cleared]) == []


def test_behind_on_volatile_lines_mentions_the_market() -> None:
    start = add_months(OCT, -5)
    goal = _facts(
        "3000",
        ["0", "100", "100", "100", "100", "100"],
        deadline=add_months(start, 30),
        start=start,
        volatility="0.16",
    )
    (notice,) = behind_notices([goal])
    assert notice.severity is Severity.INFO
    assert notice.figures["market"] is True


def test_no_gain_in_six_months() -> None:
    start = add_months(OCT, -6)
    flat = _facts(
        "1000",
        ["100", "100", "90", "90", "80", "80", "80"],
        deadline=add_months(OCT, 24),
        start=start,
    )
    moving = _facts(
        "1000",
        ["100", "90", "80", "70", "60", "50", "51"],
        deadline=add_months(OCT, 24),
        start=start,
    )
    young = _facts("1000", ["100"] * 6, deadline=add_months(OCT, 24), start=add_months(OCT, -5))
    notices = no_gain_notices([flat, moving, young])
    assert [(n.goal, n.severity) for n in notices] == [(flat.id, Severity.INFO)]


def test_a_locked_pleasure_goal_gains_nothing_and_is_left_alone() -> None:
    start = add_months(OCT, -6)
    values = [D(0)] * 7
    goal = GoalFacts(
        id=A,
        target=D(400),
        start=start,
        deadline=None,
        history=history(D(400), start, None, values, locked=[True] * 7),
        held={},
        shares={B: 100},
        pleasure=True,
    )
    assert goal.now.status is GoalStatus.LOCKED
    assert no_gain_notices([goal]) == []


@given(
    st.lists(st.decimals(0, 5000, places=2), min_size=1, max_size=14),
    st.integers(0, 30),
    st.decimals(1, 6000, places=2),
)
def test_history_is_the_tracking_of_each_month(
    values: list[Decimal], months: int, target: Decimal
) -> None:
    """Invariant §8.30: a month's status, gain and effort are F-GOAL-4 and 5's at that month."""
    start = add_months(OCT, 1 - len(values))
    deadline = add_months(OCT, months)
    h = history(target, start, deadline, values)
    for k, tracked in enumerate(h):
        month = add_months(start, k)
        assert tracked == track(target, start, deadline, values[: k + 1], this_month=month)


# Ordering, one per goal, dismissal (invariant §8.36)


def _n(
    rule: Rule,
    severity: Severity,
    goal: UUID | None = None,
    amount: str = "100",
    deadline: Month | None = None,
) -> Notice:
    return Notice(rule, severity, goal=goal, amount=D(amount), deadline=deadline)


def test_points_are_ordered_one_per_goal_three_shown() -> None:
    notices = [
        _n(Rule.NO_GAIN, Severity.INFO, A),
        _n(Rule.BEHIND, Severity.WARNING, A),
        _n(Rule.UNFUNDED, Severity.WARNING, B),
        _n(Rule.PRECAUTION_CURRENT, Severity.INFO, C),
        _n(Rule.PRECAUTION_NONE, Severity.WARNING),
    ]
    sel = select(notices, {}, OCT)
    assert [(n.rule, n.goal) for n in sel.shown] == [
        (Rule.PRECAUTION_NONE, None),
        (Rule.UNFUNDED, B),
        (Rule.BEHIND, A),
    ]
    assert [n.rule for n in sel.more] == [Rule.PRECAUTION_CURRENT]


def test_nearest_deadline_first_within_a_rule() -> None:
    late = _n(Rule.BEHIND, Severity.WARNING, A, deadline=Month(2027, 9))
    soon = _n(Rule.BEHIND, Severity.WARNING, B, deadline=Month(2027, 1))
    assert select([late, soon], {}, OCT).shown == [soon, late]


def test_stale_data_silences_behind_and_no_gain() -> None:
    notices = [
        _n(Rule.DATA, Severity.WARNING),
        _n(Rule.BEHIND, Severity.WARNING, A),
        _n(Rule.NO_GAIN, Severity.INFO, B),
        _n(Rule.UNFUNDED, Severity.WARNING, C),
    ]
    assert [n.rule for n in select(notices, {}, OCT).shown] == [Rule.DATA, Rule.UNFUNDED]


def test_a_dismissed_point_lets_the_next_of_its_goal_show() -> None:
    behind = _n(Rule.BEHIND, Severity.WARNING, A)
    idle = _n(Rule.NO_GAIN, Severity.INFO, A)
    gone = {behind.key: Dismissal(severity=Severity.WARNING, amount=D(100))}
    assert select([behind, idle], gone, OCT).shown == [idle]


def test_a_snoozed_point_comes_back_the_next_reference_month() -> None:
    notice = _n(Rule.BEHIND, Severity.WARNING, A)
    snoozed = Dismissal(until=Month(2026, 11))
    assert hidden(notice, snoozed, OCT)
    assert not hidden(notice, snoozed, Month(2026, 11))


@given(
    st.sampled_from(list(Severity)),
    st.sampled_from(list(Severity)),
    st.decimals(1, 10_000, places=2),
    st.decimals(0, 20_000, places=2),
)
def test_a_dismissed_point_comes_back_exactly_when_it_worsens(
    was: Severity, now: Severity, then: Decimal, amount: Decimal
) -> None:
    order = [Severity.GOOD, Severity.INFO, Severity.WARNING]
    notice = _n(Rule.BEHIND, now, A, amount=str(amount))
    worse = order.index(now) > order.index(was) or amount > then * D("1.25")
    assert hidden(notice, Dismissal(severity=was, amount=then), OCT) is not worse


@pytest.mark.parametrize("rule", [Rule.DATA, Rule.PRECAUTION_NONE])
def test_some_points_are_never_hidden(rule: Rule) -> None:
    notice = _n(rule, Severity.WARNING)
    assert not hidden(notice, Dismissal(until=Month(2027, 1)), OCT)
    assert not hidden(notice, Dismissal(severity=Severity.WARNING, amount=D(100)), OCT)
