from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from hypothesis import given
from hypothesis import strategies as st
from kwak_core.budget import DEFAULT_BAND, Month
from kwak_core.goal_analysis import (
    DEFAULT_RISKS,
    Dismissal,
    GoalFacts,
    LineRisk,
    Notice,
    Rule,
    SankeyLine,
    Severity,
    Zone,
    _to_ahead,
    behind_notices,
    capstone_notices,
    ceiling_notices,
    costly_debt_notices,
    data_notices,
    debt_payment_notices,
    eroding_notices,
    forward_efforts,
    hidden,
    history,
    idle_notices,
    left_over_notices,
    losing_value_notices,
    loss_one_in_ten,
    no_gain_notices,
    not_indexed_notices,
    overcommitted_notices,
    placement,
    precaution_notices,
    reference_month,
    risk_of,
    select,
    short_risk_notices,
    stale_lines,
    unfunded_notices,
    weighted,
    weights,
    zone,
)
from kwak_core.goals import GoalStatus, Line, Tier, add_months, track
from kwak_core.money import quantize
from kwak_core.projection import Assumption
from kwak_core.wealth import DEFAULT_WEALTH_CATEGORIES, RegulatedType

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
        (12, "0", "0.5", "-0.1", Zone.RED_SHORT),  # on equipment: risky though not volatile
        (12, "0", "0.1", "0", Zone.NONE),
        (24, "0.05", "0", "0", Zone.NONE),  # 5 %: not above, so not volatile
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


def test_each_default_category_has_its_projection_defaults() -> None:
    """F-SIM-1's defaults, by the category's preset, until the household sets its own."""
    assert {c.colour for c in DEFAULT_WEALTH_CATEGORIES} - {"debts"} == set(DEFAULT_RISKS)
    assert DEFAULT_RISKS["stocks"] == LineRisk(ret=D("0.07"), volatility=D("0.16"))
    assert DEFAULT_RISKS["current"].current
    assert not DEFAULT_RISKS["savings"].risky
    assert all(DEFAULT_RISKS[k].illiquid for k in ("real-estate", "private-equity", "equipment"))
    assert DEFAULT_RISKS["equipment"].volatile  # it loses value
    assert risk_of(None) == risk_of("unknown") == LineRisk()


# F-ANA-8, second batch


STOCKS = LineRisk(ret=D("0.07"), volatility=D("0.16"))
LIVRET = LineRisk(ret=D("0.017"))
CURRENT = LineRisk(current=True)
EQUIPMENT = LineRisk(ret=D("-0.15"), illiquid=True)


def _held(value: str, months: int, held: dict[UUID, Decimal], target: str = "10000") -> GoalFacts:
    return _facts(
        target,
        [value],
        deadline=add_months(OCT, months),
        start=OCT,
        held=held,
        shares=dict.fromkeys(held, 50),
    )


def test_a_short_goal_on_volatile_lines_is_a_warning_with_its_loss() -> None:
    goal = _held("4000", 18, {A: D(3000), B: D(1000)})
    (notice,) = short_risk_notices([goal], {A: STOCKS, B: LIVRET})
    assert (notice.rule, notice.severity, notice.amount) == (
        Rule.SHORT_RISK,
        Severity.WARNING,
        D(3000),
    )
    loss = notice.figures["loss"]
    assert isinstance(loss, Decimal)
    assert D(300) < loss < D(700)  # one outcome in ten, in euros


@pytest.mark.parametrize(
    ("months", "risky", "severity"),
    [
        (18, "400", None),  # 10 % of the goal: not above
        (40, "2000", Severity.INFO),  # 50 % against the 44 % allowed 40 months out
        (40, "1000", None),
        (48, "3000", Severity.INFO),  # 75 % against 67 %
        (72, "4000", None),  # beyond five years: no glide path
    ],
)
def test_the_glide_path(months: int, risky: str, severity: Severity | None) -> None:
    goal = _held("4000", months, {A: D(risky), B: D(4000) - D(risky)})
    notices = short_risk_notices([goal], {A: STOCKS, B: LIVRET})
    assert [n.severity for n in notices] == ([severity] if severity else [])


def test_a_category_losing_value() -> None:
    goal = _held("4000", 30, {A: D(500), B: D(3500)})
    (notice,) = losing_value_notices([goal], {A: EQUIPMENT, B: LIVRET})
    assert (notice.rule, notice.severity, notice.amount) == (
        Rule.LOSING_VALUE,
        Severity.INFO,
        D(500),
    )
    assert (
        losing_value_notices(
            [_held("4000", 30, {A: D(300), B: D(3700)})], {A: EQUIPMENT, B: LIVRET}
        )
        == []
    )


def test_a_long_goal_on_livrets_erodes() -> None:
    goal = _held("10000", 120, {A: D(10000)}, target="30000")
    (notice,) = eroding_notices([goal], {A: LIVRET}, inflation=D("0.02"))
    assert (notice.rule, notice.severity) == (Rule.ERODING, Severity.INFO)
    assert notice.amount == D("290.26")  # 10,000 x (1 - (1.017 / 1.02)^10)
    assert eroding_notices([goal], {A: STOCKS}, inflation=D("0.02")) == []
    short = _held("10000", 90, {A: D(10000)}, target="30000")
    assert eroding_notices([short], {A: LIVRET}, inflation=D("0.02")) == []


def test_a_small_long_goal_is_left_alone() -> None:
    goal = _held("100", 120, {A: D(100)}, target="4000")
    assert eroding_notices([goal], {A: LIVRET}, inflation=D("0.02")) == []


def test_a_far_target_is_not_indexed() -> None:
    goal = _held("0", 120, {}, target="30000")
    (notice,) = not_indexed_notices([goal], inflation=D("0.02"))
    assert (notice.rule, notice.amount) == (Rule.NOT_INDEXED, D(30000))
    assert notice.figures["indexed"] == D("36569.83")  # 30,000 x 1.02^10
    assert not_indexed_notices([_held("0", 60, {}, target="30000")], inflation=D("0.02")) == []


def test_idle_money_on_current_accounts() -> None:
    start = add_months(OCT, -5)
    behind = _facts(
        "1200",
        ["0", "100", "100", "100", "100", "100"],
        deadline=add_months(start, 12),
        start=start,
    )
    fine = _due("1200", 12)
    kwargs = {"income": D(3000), "spending": D(2000), "history_months": 6, "monthly_fixed": D(900)}
    (notice,) = idle_notices([behind, fine], current_free=D(6000), **kwargs)
    assert (notice.rule, notice.severity, notice.amount) == (Rule.IDLE, Severity.WARNING, D(1000))
    assert notice.subject == behind.id
    assert notice.figures["set_aside"] == D(400)  # what it is behind, under the excess
    (calm,) = idle_notices([fine], current_free=D(6000), **kwargs)
    assert (calm.severity, calm.subject) == (Severity.INFO, None)
    assert idle_notices([fine], current_free=D(5000), **kwargs) == []
    # with little history, four months of fixed expenses
    assert (
        idle_notices(
            [fine],
            current_free=D(3700),
            income=D(0),
            spending=D(0),
            history_months=1,
            monthly_fixed=D(900),
        )
        != []
    )


def test_the_capstone_one_goal_away() -> None:
    start = add_months(OCT, -2)
    fund = _facts("1000", ["1000", "1000", "1000"], deadline=None, start=start, precaution=True)
    ahead = _facts("1200", ["0", "300", "600"], deadline=add_months(start, 12), start=start)
    near = _facts("1200", ["0", "100", "200"], deadline=add_months(start, 12), start=start)
    rum = _facts("150", ["0", "0", "0"], deadline=None, start=start)
    rum = GoalFacts(**{**rum.__dict__, "pleasure": True})
    (notice,) = capstone_notices([fund, ahead, near, rum])
    assert (notice.rule, notice.severity, notice.subject) == (Rule.CAPSTONE, Severity.GOOD, near.id)
    # expected 200, ahead above 210: 11 more, the fewest whole euros
    assert notice.amount == D(11)
    # in three months expected 500, ahead above 525: 325 more, 109 a month
    assert notice.figures["monthly"] == D(109)


def test_the_capstone_waits_for_the_emergency_fund() -> None:
    start = add_months(OCT, -2)
    fund = _facts("1000", ["600", "700", "820"], deadline=None, start=start, precaution=True)
    rum = _facts("150", ["0", "0", "0"], deadline=None, start=start)
    rum = GoalFacts(**{**rum.__dict__, "pleasure": True})
    (notice,) = capstone_notices([fund, rum])
    assert (notice.amount, notice.figures["progress"]) == (D(180), D("0.82"))
    assert capstone_notices([fund]) == []  # no pleasure goal, nothing to unlock


def test_capacity_left_over_is_good_news() -> None:
    goals = [_due("1200", 12)]
    (notice,) = left_over_notices(goals, unallocated=D(80), capacity_months=6)
    assert (notice.rule, notice.severity, notice.amount) == (Rule.LEFT_OVER, Severity.GOOD, D(80))
    assert left_over_notices(goals, unallocated=D(50), capacity_months=6) == []
    assert left_over_notices(goals, unallocated=D(80), capacity_months=2) == []


@given(
    st.decimals(0, 50_000, places=2),
    st.integers(97, 400),
    st.decimals(D("-0.2"), D("0.02"), places=3),
)
def test_erosion_never_exceeds_the_value(value: Decimal, months: int, ret: Decimal) -> None:
    goal = _held(str(value), months, {A: value}, target="60000")
    for notice in eroding_notices([goal], {A: LineRisk(ret=ret)}, inflation=D("0.02")):
        assert notice.amount is not None
        assert D(0) <= notice.amount <= value


@given(st.decimals(1, 50_000, places=2), st.integers(1, 60))
def test_a_goal_on_safe_lines_is_never_at_short_risk(value: Decimal, months: int) -> None:
    goal = _held(str(value), months, {A: value}, target="60000")
    assert short_risk_notices([goal], {A: LIVRET}) == []


def test_the_capstone_counts_a_reached_goal_as_ahead() -> None:
    """Near its deadline, reaching the target is enough: no need to go past it."""
    start = add_months(OCT, -2)
    fund = _facts("1000", ["1000", "1000", "1000"], deadline=None, start=start, precaution=True)
    ahead = _facts("1200", ["0", "600", "1200"], deadline=add_months(start, 4), start=start)
    due = _facts("1000", ["0", "500", "900"], deadline=OCT, start=start)
    rum = _facts("150", ["0", "0", "0"], deadline=None, start=start)
    rum = GoalFacts(**{**rum.__dict__, "pleasure": True})
    (notice,) = capstone_notices([fund, ahead, due, rum])
    assert (notice.subject, notice.amount) == (due.id, D(100))


@given(
    st.decimals(0, 20_000, places=2),
    st.decimals(1, 20_000, places=2),
    st.decimals(0, 30_000, places=2),
)
def test_the_amount_to_ahead_is_the_fewest_euros(
    expected: Decimal, target: Decimal, value: Decimal
) -> None:
    amount = _to_ahead(expected, value, target, DEFAULT_BAND)

    def ahead(v: Decimal) -> bool:
        return v >= target or v > expected * (1 + DEFAULT_BAND)

    assert ahead(value + amount)
    assert amount == 0 or not ahead(value + amount - 1)


# R6: a regulated ceiling near


def test_a_livret_near_its_ceiling_funding_a_goal() -> None:
    small, big = _held("1000", 30, {A: D(1000)}), _held("1000", 40, {A: D(1000)})
    big = GoalFacts(**{**big.__dict__, "shares": {A: 80}})
    (notice,) = ceiling_notices(
        [small, big], {A: (RegulatedType.LIVRET_A, D(22600)), B: (RegulatedType.LDDS, D(9000))}
    )
    assert (notice.rule, notice.severity, notice.line, notice.goal) == (
        Rule.CEILING,
        Severity.INFO,
        A,
        None,
    )
    assert notice.subject == big.id  # the goal taking most of its rises
    assert notice.amount == D(22600)
    assert notice.figures == {"ceiling": D(22950), "room": D(350)}


@pytest.mark.parametrize(
    ("value", "shown"), [("22449.99", False), ("22450", True), ("23100", True)]
)
def test_the_ceiling_margin(value: str, shown: bool) -> None:
    goal = _held("1000", 30, {A: D(1000)})
    notices = ceiling_notices([goal], {A: (RegulatedType.LIVRET_A, D(value))})
    assert [n.figures["room"] for n in notices] == (
        [max(D(0), D(22950) - D(value))] if shown else []
    )


def test_the_subject_on_equal_shares_is_the_nearest_deadline() -> None:
    far, near = _held("1000", 40, {A: D(500)}), _held("1000", 20, {A: D(500)})
    undated = _facts("1000", ["500"], deadline=None, start=OCT, held={A: D(500)}, shares={A: 50})
    (notice,) = ceiling_notices([undated, far, near], {A: (RegulatedType.LDDS, D(12000))})
    assert (notice.subject, notice.deadline) == (near.id, near.deadline)


def test_a_reached_goal_takes_no_more_rises() -> None:
    reached = _held("1000", 30, {A: D(1000)}, target="1000")
    assert ceiling_notices([reached], {A: (RegulatedType.LIVRET_A, D(22900))}) == []


def test_a_full_livret_no_goal_draws_on_is_left_alone() -> None:
    goal = _held("1000", 30, {B: D(1000)})
    assert ceiling_notices([goal], {A: (RegulatedType.LEP, D(10000))}) == []


# F-ANA-5: where the goals' money sits

SAVINGS, STOCKS_CAT, HOUSE = uuid4(), uuid4(), uuid4()


def _asset(line: UUID, category: UUID, value: str, preset: str | None) -> SankeyLine:
    return SankeyLine(line, category, D(value), preset)


def test_the_goals_money_line_by_line() -> None:
    trip, car = uuid4(), uuid4()
    flows = placement(
        [
            _asset(A, SAVINGS, "5000", "savings"),
            _asset(B, STOCKS_CAT, "8000", "stocks"),
            _asset(C, HOUSE, "200000", "real-estate"),
            _asset(uuid4(), STOCKS_CAT, "0", "stocks"),
        ],
        {(trip, A): D(2000), (car, A): D(1000), (car, B): D(3000)},
    )
    assert flows.categories == {SAVINGS: D(5000), STOCKS_CAT: D(8000)}
    assert flows.lines == {A: D(5000), B: D(8000)}  # real estate and empty lines left out
    assert flows.held == {(trip, A): D(2000), (car, A): D(1000), (car, B): D(3000)}
    assert flows.free == {A: D(2000), B: D(5000)}
    assert flows.elsewhere == {}
    every = placement([_asset(C, HOUSE, "200000", "real-estate")], {}, all_assets=True)
    assert every.free == {C: D(200000)}


def test_what_a_goal_holds_on_lines_left_out() -> None:
    home = uuid4()
    lines = [_asset(A, SAVINGS, "1000", "savings"), _asset(C, HOUSE, "200000", "real-estate")]
    flows = placement(lines, {(home, A): D(1000), (home, C): D(3000)})
    assert (flows.held, flows.elsewhere) == ({(home, A): D(1000)}, {home: D(3000)})
    every = placement(lines, {(home, A): D(1000), (home, C): D(3000)}, all_assets=True)
    assert (every.held[(home, C)], every.elsewhere) == (D(3000), {})


@pytest.mark.parametrize("value", ["100", "0"])
def test_envelopes_cannot_hold_more_than_their_line(value: str) -> None:
    with pytest.raises(ValueError, match="more than"):
        placement([_asset(A, SAVINGS, value, "savings")], {(uuid4(), A): D(101)})


@given(
    st.lists(
        st.tuples(
            st.decimals(0, 100_000, places=2),
            st.sampled_from(["savings", "stocks", "real-estate", "equipment", None]),
        ),
        min_size=1,
        max_size=5,
    ),
    st.lists(st.tuples(st.integers(0, 4), st.integers(0, 2), st.integers(0, 100)), max_size=10),
    st.booleans(),
)
def test_each_line_and_goal_adds_up(
    values: list[tuple[Decimal, str | None]],
    claims: list[tuple[int, int, int]],
    all_assets: bool,
) -> None:
    """Invariant §8.34."""
    lines = [_asset(uuid4(), SAVINGS, str(v), preset) for v, preset in values]
    goals = [uuid4() for _ in range(3)]
    held: dict[tuple[UUID, UUID], Decimal] = {}
    for i, g, pct in claims:
        if i >= len(lines):
            continue
        line = lines[i]
        room = line.value - sum((a for (_, ln), a in held.items() if ln == line.id), D(0))
        key = (goals[g], line.id)
        held[key] = held.get(key, D(0)) + quantize(room * pct / 100)
    flows = placement(lines, held, all_assets=all_assets)
    for line in lines:
        if line.id in flows.lines:
            out = sum((a for (_, ln), a in flows.held.items() if ln == line.id), D(0))
            assert out + flows.free[line.id] == flows.lines[line.id] == line.value
    for g in goals:
        mine = sum((a for (goal, _), a in held.items() if goal == g), D(0))
        shown = sum((a for (goal, _), a in flows.held.items() if goal == g), D(0))
        assert shown + flows.elsewhere.get(g, D(0)) == mine
        if all_assets:
            assert g not in flows.elsewhere
    assert sum(flows.categories.values(), D(0)) == sum(flows.lines.values(), D(0))


def test_the_households_assumption_replaces_the_default_but_not_the_kind() -> None:
    """Once the household sets a category's return and volatility (F-SIM-1), the goals are
    judged on them; liquidity and the current account still follow the preset."""
    own = Assumption(D("0.05"), D("0.1"))
    assert risk_of("real-estate", own) == LineRisk(
        ret=D("0.05"), volatility=D("0.1"), illiquid=True
    )
    assert risk_of("current", Assumption(D("0.01"), D(0))).current
    assert risk_of(None, own) == LineRisk(ret=D("0.05"), volatility=D("0.1"))


LOAN = uuid4()


def test_a_debt_costing_more_than_the_goals_lines_earn() -> None:
    """R12: a rate above the greater of 6 % and the best return of a goal's line plus 1 point."""
    goal = _held("1000", 30, {A: D(1000)})
    risks = {A: LineRisk(ret=D("0.07"), volatility=D("0.16"))}
    (notice,) = costly_debt_notices(
        [goal], risks, {LOAN: (D("0.081"), D(5000)), uuid4(): (D("0.079"), D(9000))}
    )
    assert (notice.rule, notice.severity, notice.line, notice.amount) == (
        Rule.COSTLY_DEBT,
        Severity.INFO,
        LOAN,
        D(5000),
    )
    assert notice.figures == {"rate": D("0.081"), "threshold": D("0.08")}


def test_without_a_goals_line_a_debt_is_costly_above_6_percent() -> None:
    assert [n.line for n in costly_debt_notices([], {}, {LOAN: (D("0.061"), D(100))})] == [LOAN]
    assert costly_debt_notices([], {}, {LOAN: (D("0.06"), D(100))}) == []
    assert costly_debt_notices([], {}, {LOAN: (D("0.2"), D(0))}) == []  # repaid


@pytest.mark.parametrize(("payments", "shown"), [("1050", False), ("1050.01", True)])
def test_debt_payments_above_35_percent_of_income(payments: str, shown: bool) -> None:
    """R13: the lenders' ceiling in France (HCSF), insurance included."""
    notices = debt_payment_notices(payments=D(payments), income=D(3000))
    assert [(n.rule, n.severity, n.amount) for n in notices] == (
        [(Rule.DEBT_PAYMENTS, Severity.INFO, D(payments))] if shown else []
    )
    if shown:
        assert notices[0].figures["ratio"] == D(payments) / 3000
    assert debt_payment_notices(payments=D(500), income=D(0)) == []
