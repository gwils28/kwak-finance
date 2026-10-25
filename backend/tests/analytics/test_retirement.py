"""Retirement on the Monte Carlo engine (spec §4.13 F-RET-4, invariants §8.38-39): the
sustainable withdrawal, and when the liquid wealth runs out."""

from decimal import Decimal
from uuid import uuid4

from hypothesis import given, settings
from hypothesis import strategies as st
from kwak_analytics.montecarlo import Category, Scenario, simulate
from kwak_analytics.retirement import failing_share, sustainable_withdrawal
from kwak_core.projection import Assumption

D = Decimal
FLAT = Assumption(D(0), D(0))
STOCKS = Assumption(D("0.07"), D("0.16"))


def _scenario(categories: list[Category], savings: list[Decimal], inflation: str = "0") -> Scenario:
    months = len(savings)
    return Scenario(categories, savings, [D(0)] * months, D(0), D(inflation))


def _livret(start: str, assumption: Assumption = FLAT, share: str = "1") -> Category:
    return Category(uuid4(), "savings", D(start), assumption, D(share))


def test_without_volatility_the_withdrawal_empties_the_wealth_at_the_horizon() -> None:
    """Invariant 39: the constant real payment that empties the liquid wealth exactly at the
    horizon, rounded down to €100."""
    plan = _scenario([_livret("120050")], [D(0)] * 120)
    w = sustainable_withdrawal(plan, retired_at=1, paths=20)
    assert (w.nine_tenths, w.half) == (D(1000), D(1000))
    assert failing_share(plan, retired_at=1, amount=D(1000), paths=20) == 0
    assert failing_share(plan, retired_at=1, amount=D(1100), paths=20) == 1


def test_the_withdrawal_is_indexed_to_inflation() -> None:
    plan = _scenario([_livret("120000")], [D(0)] * 120, inflation="0.02")
    w = sustainable_withdrawal(plan, retired_at=1, paths=10)
    assert w.half is not None
    assert D(800) < w.half < D(1000)  # current euros grow, so the payment in today's ones falls


def test_the_savings_before_the_retirement_build_the_wealth_it_pays_from() -> None:
    # 12 months of 1,000 saved, then 12 months paid from it: 1,000 a month.
    plan = _scenario([_livret("0")], [D(1000)] * 12 + [D(0)] * 12)
    assert sustainable_withdrawal(plan, retired_at=13, paths=5).nine_tenths == D(1000)


def test_the_home_and_locked_in_funds_pay_nothing() -> None:
    house = Category(uuid4(), "real-estate", D(500_000), FLAT, D(0))
    plan = _scenario([_livret("0"), house], [D(0)] * 12)
    assert sustainable_withdrawal(plan, retired_at=1, paths=5).nine_tenths == D(0)


def test_a_wealth_already_in_shortfall_at_the_retirement_pays_none() -> None:
    plan = _scenario([_livret("100")], [D(-500)] * 3 + [D(0)] * 12)
    w = sustainable_withdrawal(plan, retired_at=4, paths=5)
    assert (w.nine_tenths, w.half) == (None, None)


def test_with_volatility_one_outcome_in_ten_at_most_fails_and_one_more_hundred_fails() -> None:
    """Invariant 38's definition: the largest multiple of €100 at which no more than one
    outcome in ten runs into a Shortfall."""
    plan = _scenario([_livret("200000", STOCKS)], [D(0)] * 240)
    w = sustainable_withdrawal(plan, retired_at=1, paths=400)
    assert w.nine_tenths is not None
    assert w.half is not None
    assert w.nine_tenths <= w.half
    assert w.nine_tenths % 100 == 0
    assert failing_share(plan, retired_at=1, amount=w.nine_tenths, paths=400) <= D("0.1")
    assert failing_share(plan, retired_at=1, amount=w.nine_tenths + 100, paths=400) > D("0.1")


@settings(max_examples=10, deadline=None)
@given(st.integers(10_000, 300_000), st.integers(1, 50_000), st.integers(24, 240))
def test_more_wealth_or_a_nearer_horizon_never_lowers_the_withdrawal(
    start: int, extra: int, months: int
) -> None:
    """Invariant 38, on the starting value and the horizon."""

    def withdrawal(value: int, n: int) -> Decimal:
        livret = Category(stable_id, "stocks", D(value), STOCKS, D(1))
        w = sustainable_withdrawal(_scenario([livret], [D(0)] * n), retired_at=1, paths=100)
        assert w.nine_tenths is not None
        return w.nine_tenths

    base = withdrawal(start, months)
    assert withdrawal(start + extra, months) >= base
    assert withdrawal(start, months // 2) >= base


stable_id = uuid4()


def test_the_month_the_liquid_wealth_runs_out() -> None:
    out = simulate(_scenario([_livret("1000")], [D(-300)] * 12), paths=5)
    # 1,000 pays three months of 300; the fourth needs 200 more.
    assert out.ran_out_by(D("0.1")) == 4
    assert out.ran_out_by(D("0.5")) == 4
    rich = simulate(_scenario([_livret("100000")], [D(-300)] * 12), paths=5)
    assert rich.ran_out_by(D("0.1")) is None
