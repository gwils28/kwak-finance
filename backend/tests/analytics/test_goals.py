"""The chance of reaching each goal (spec §4.12 F-ANA-7, invariant §8.35)."""

from decimal import Decimal
from uuid import uuid4

from hypothesis import given, settings
from hypothesis import strategies as st
from kwak_analytics.goals import GoalLine, chance_of_goal
from kwak_core.projection import Assumption

D = Decimal
FLAT = Assumption(D(0), D(0))
STOCKS = Assumption(D("0.07"), D("0.16"))
SAVINGS_ID, STOCKS_ID = uuid4(), uuid4()


def _line(held: str, share: str = "1", assumption: Assumption = FLAT) -> GoalLine:
    category = SAVINGS_ID if assumption == FLAT else STOCKS_ID
    return GoalLine(category, assumption, D(held), D(share))


def test_without_volatility_a_goal_is_reached_or_short_by_an_amount() -> None:
    """Invariant 35: 0 or 1, matching the allocation compounded month by month."""
    reached = chance_of_goal([_line("1000")], target=D(2200), monthly=D(100), months=12)
    assert (reached.chance, reached.certain, reached.short) == (D(1), True, D(0))
    short = chance_of_goal([_line("1000")], target=D(2500), monthly=D(100), months=12)
    assert (short.chance, short.certain, short.short) == (D(0), True, D(300))


def test_a_goal_already_reached_is_certain() -> None:
    out = chance_of_goal([_line("3000")], target=D(2000), monthly=D(0), months=6)
    assert out.chance == 1


def test_new_money_follows_the_lines_shares() -> None:
    # 100 a month, a quarter on a line losing 50 % a year: less than 1,200 in a year.
    losing = GoalLine(uuid4(), Assumption(D("-0.5"), D(0)), D(0), D("0.25"))
    out = chance_of_goal([_line("0", "0.75"), losing], target=D(1200), monthly=D(100), months=12)
    assert out.certain
    assert D(0) < out.short < D(300)


def test_with_volatility_the_chance_is_between_0_and_1() -> None:
    out = chance_of_goal(
        [_line("5000", assumption=STOCKS)], target=D(8000), monthly=D(200), months=12, paths=500
    )
    assert not out.certain
    assert D(0) < out.chance < D(1)


@settings(max_examples=15, deadline=None)
@given(
    st.integers(0, 20_000),
    st.integers(0, 1_000),
    st.integers(1, 500),
    st.integers(1_000, 60_000),
    st.integers(1, 120),
)
def test_more_allocation_or_a_lower_target_never_lowers_the_chance(
    held: int, monthly: int, extra: int, target: int, months: int
) -> None:
    """Invariant 35."""

    def chance(m: int, goal: int) -> Decimal:
        lines = [_line(str(held), "0.6", STOCKS), _line("0", "0.4")]
        return chance_of_goal(lines, target=D(goal), monthly=D(m), months=months, paths=200).chance

    base = chance(monthly, target)
    assert chance(monthly + extra, target) >= base
    assert chance(monthly, max(1, target - extra)) >= base
