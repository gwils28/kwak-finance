from decimal import Decimal
from uuid import UUID, uuid4

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from kwak_analytics.montecarlo import (
    DEFAULT_SEED,
    ENGINE_VERSION,
    PATHS,
    Category,
    Scenario,
    simulate,
)
from kwak_core.projection import SHORTFALL_RATE, Assumption

D = Decimal
GOLDEN = [1131.346816, 1243.498215, 1244.608543]
"""Engine 1, seed 20261022, 3 paths: 1,000 in stocks and 100 a month for 3 months."""


def _category(
    preset: str | None, start: str, ret: str = "0", vol: str = "0", share: str = "0"
) -> Category:
    return Category(uuid4(), preset, D(start), Assumption(D(ret), D(vol)), D(share))


def _scenario(
    categories: list[Category],
    months: int,
    savings: str = "0",
    debts: list[str] | None = None,
    start_debts: str = "0",
    inflation: str = "0",
) -> Scenario:
    return Scenario(
        categories,
        [D(savings)] * months,
        [D(d) for d in debts] if debts is not None else [D(start_debts)] * months,
        D(start_debts),
        D(inflation),
    )


def test_the_paths_never_change_without_a_new_engine_version() -> None:
    """A golden run: if numpy or the engine draws differently, this fails, and ENGINE_VERSION
    must be raised with the expected values (invariant §8.24, F-SIM-4)."""
    assert (ENGINE_VERSION, PATHS, DEFAULT_SEED) == (1, 5000, 20261022)
    stocks = Category(UUID(int=1), "stocks", D(1000), Assumption(D("0.07"), D("0.16")), D(1))
    out = simulate(_scenario([stocks], months=3, savings="100"), paths=3)
    assert np.round(out.net[3], 6).tolist() == GOLDEN


def test_month_zero_is_the_starting_point() -> None:
    """Invariant §8.23."""
    s = _scenario(
        [_category("savings", "1000", share="1"), _category("stocks", "3000", "0.07", "0.16")],
        months=3,
        start_debts="500",
    )
    out = simulate(s, paths=50)
    assert np.all(out.net[0] == 3500)


# Invariants §8.24 and 26: with no volatility, the paths are the compounding


def test_without_volatility_a_category_grows_by_its_return_over_a_year() -> None:
    s = _scenario([_category("savings", "10000", "0.017", share="1")], months=12)
    out = simulate(s, paths=20)
    assert np.allclose(out.net[12], 10170, rtol=1e-12)
    assert np.all(out.net == out.net[:, :1])  # every path the same


@settings(max_examples=25, deadline=None)
@given(
    st.lists(
        st.tuples(st.decimals(0, 50_000, places=2), st.decimals("-0.2", "0.1", places=3)),
        min_size=1,
        max_size=4,
    ),
    st.lists(st.integers(1, 10), min_size=4, max_size=4),
    st.decimals(0, 2_000, places=2),
    st.integers(1, 60),
)
def test_without_volatility_every_path_is_the_month_by_month_compounding(
    held: list[tuple[Decimal, Decimal]], parts: list[int], savings: Decimal, months: int
) -> None:
    parts = parts[: len(held)]
    weights = [(D(p) / sum(parts)).quantize(D("1e-12")) for p in parts]
    weights[-1] = 1 - sum(weights[:-1], D(0))
    categories = [
        Category(uuid4(), "stocks", v, Assumption(r, D(0)), w)
        for (v, r), w in zip(held, weights, strict=True)
    ]
    out = simulate(_scenario(categories, months, savings=str(savings)), paths=10)
    # The reference, in Decimal: grow, then receive the savings.
    values = [v for v, _ in held]
    for _ in range(months):
        values = [
            v * (1 + r) ** (D(1) / 12) + savings * w
            for v, (_, r), w in zip(values, held, weights, strict=True)
        ]
    expected = float(sum(values, D(0)))
    assert np.allclose(out.net[months], expected, rtol=1e-9, atol=1e-6)
    assert len(set(out.percentiles(today=False)[months].values())) == 1


def test_the_simulated_annual_growth_has_the_category_s_mean_and_volatility() -> None:
    """Invariant §8.26, within the Monte Carlo error."""
    s = _scenario([_category("stocks", "1000", "0.07", "0.16", "1")], months=12)
    out = simulate(s, paths=40_000, seed=7)
    growth = out.net[12] / 1000 - 1
    error = 0.16 / np.sqrt(40_000)
    assert abs(growth.mean() - 0.07) < 4 * error
    assert abs(growth.std() - 0.16) < 0.005


def test_the_same_seed_gives_the_same_paths_and_scenarios_share_their_draws() -> None:
    cats = [_category("stocks", "1000", "0.07", "0.16", "1")]
    a = simulate(_scenario(cats, 24), paths=200, seed=3)
    b = simulate(_scenario(cats, 24), paths=200, seed=3)
    assert np.array_equal(a.net, b.net)
    # A what-if adding savings changes the outcome by the same draws: never below the base.
    c = simulate(_scenario(cats, 24, savings="100"), paths=200, seed=3)
    assert np.all(c.net[24] > a.net[24])


def test_a_category_keeps_its_draws_whatever_the_other_categories() -> None:
    """F-SIM-4: every scenario uses the same draws, even one that adds a category (an
    allocation into crypto, held at nothing today)."""
    stocks = _category("stocks", "1000", "0.07", "0.16", "1")
    crypto = _category("crypto", "0", "0.08", "0.6")
    alone = simulate(_scenario([stocks], 24), paths=50, seed=3, keep=True)
    both = simulate(_scenario([crypto, stocks], 24), paths=50, seed=3, keep=True)
    assert alone.assets is not None
    assert both.assets is not None
    assert np.array_equal(alone.assets[:, :, 0], both.assets[:, :, 1])


# Invariants §8.25 and 27: never below zero, money conserved, the Shortfall


def test_withdrawals_take_current_accounts_then_savings_then_the_others_in_proportion() -> None:
    current = _category("current", "100")
    livret = _category("savings", "300")
    stocks = _category("stocks", "600", share="0.5")
    gold = _category("gold", "200", share="0.5")
    house = _category("real-estate", "200000")
    pe = _category("private-equity", "5000")
    wine = _category("exotic", "3000")
    s = _scenario([current, livret, stocks, gold, house, pe, wine], months=1, savings="-600")
    out = simulate(s, paths=5, keep=True)
    assert out.assets is not None
    after = out.assets[1, 0]
    # 100, then 300, then 200 from stocks and gold in proportion (600 and 200); the illiquid
    # holdings (a home, private equity, wine) are never sold for spending.
    assert np.allclose(after, [0, 0, 450, 150, 200000, 5000, 3000])
    assert np.all(out.shortfall[1] == 0)


def test_what_cannot_be_taken_becomes_the_shortfall_borrowed_and_repaid_first() -> None:
    livret = _category("savings", "300", share="1")
    house = _category("real-estate", "200000")
    savings = [D(-500), D(100), D(400)]
    s = Scenario([livret, house], savings, [D(0)] * 3, D(0), D(0))
    out = simulate(s, paths=3, keep=True)
    assert out.assets is not None
    month = 1 + float(SHORTFALL_RATE) / 12  # it is borrowed, at the Shortfall's rate
    assert np.allclose(out.shortfall[1], 200)
    assert np.allclose(out.shortfall[2], 200 * month - 100)
    assert np.allclose(out.shortfall[3], 0)
    # The livret was emptied in month 1; in month 3 it takes 400 less what is still owed,
    # with a month's interest.
    assert np.allclose(out.assets[3, 0, 0], 400 - (200 * month - 100) * month)
    assert np.allclose(out.net[1], 200000 - 200)
    assert out.shortfall_share() == 1


@settings(max_examples=25, deadline=None)
@given(
    st.lists(st.decimals(-3_000, 3_000, places=2), min_size=1, max_size=24),
    st.sampled_from([0, 1, 2]),
)
def test_money_is_conserved_and_nothing_goes_below_zero(savings: list[Decimal], seed: int) -> None:
    """Invariants §8.25 and 27: each month the assets change by their returns plus what is
    added minus what is taken, never below zero; what is missing is the Shortfall."""
    cats = [
        _category("current", "500"),
        _category("savings", "2000", "0.017", share="0.4"),
        _category("stocks", "3000", "0.07", "0.16", "0.6"),
        _category("real-estate", "100000", "0.025", "0.08"),
    ]
    s = Scenario(cats, savings, [D(0)] * len(savings), D(0), D(0))
    out = simulate(s, paths=20, seed=seed, keep=True)
    assert out.assets is not None
    assert out.flows is not None
    assert np.all(out.assets >= 0)
    assert np.all(out.shortfall >= 0)
    for t in range(1, len(savings) + 1):
        f = out.flows[t - 1]
        change = out.assets[t].sum(axis=1) - out.assets[t - 1].sum(axis=1)
        assert np.allclose(change, f.returns + f.added - f.taken, atol=1e-6)
        assert np.all(f.taken <= out.assets[t - 1].sum(axis=1) + f.returns + 1e-6)
        missing = out.shortfall[t] - out.shortfall[t - 1]
        assert np.allclose(missing, f.missing + f.interest - f.repaid, atol=1e-6)
        # Real estate only ever moves by its growth: never sold, never bought by default.
        house = out.assets[t, :, 3] / out.assets[t - 1, :, 3]
        assert np.all(house > 0)
        # Stocks give only once current and savings accounts are empty on that path.
        sold = out.assets[t, :, 2] < out.assets[t - 1, :, 2] * 0.5
        assert np.all(~sold | (out.assets[t, :, :2].sum(axis=1) == 0))


def test_the_debts_follow_their_repayment() -> None:
    s = _scenario(
        [_category("savings", "10000", share="1")],
        3,
        debts=["900", "600", "300"],
        start_debts="1200",
    )
    out = simulate(s, paths=2)
    assert out.net[:, 0].tolist() == [8800, 9100, 9400, 9700]


def test_the_percentiles_are_ordered_and_chances_fall_as_the_amount_rises() -> None:
    s = _scenario([_category("stocks", "10000", "0.07", "0.16", "1")], 120, savings="200")
    out = simulate(s, paths=2000)
    for row in out.percentiles(today=True):
        values = [row[p] for p in (10, 25, 50, 75, 90)]
        assert values == sorted(values)
    chances = [out.chance(D(a), 120) for a in range(0, 200_001, 20_000)]
    assert chances == sorted(chances, reverse=True)
    assert chances[0] == 1


# Invariants §8.28 and 29: today's euros, the months by which an amount is reached


def test_switching_to_current_euros_never_changes_a_chance_or_a_month() -> None:
    s = _scenario(
        [_category("stocks", "10000", "0.07", "0.16", "1")], 240, savings="300", inflation="0.02"
    )
    out = simulate(s, paths=1000)
    amount, month = D(100_000), 180
    grown = amount * D("1.02") ** (D(month) / 12)
    assert out.chance(amount, month, today=True) == out.chance(grown, month, today=False)
    median = out.percentiles(today=False)[month][50]
    assert out.percentiles(today=True)[month][50] == pytest.approx(
        median / D("1.02") ** (D(month) / 12), abs=D("0.01")
    )


def test_half_the_outcomes_reach_an_amount_no_later_than_nine_tenths() -> None:
    s = _scenario(
        [_category("stocks", "10000", "0.07", "0.16", "1")], 360, savings="300", inflation="0.02"
    )
    out = simulate(s, paths=1000)
    half = out.reached_by(D(150_000), D("0.5"))
    nine = out.reached_by(D(150_000), D("0.9"))
    assert half is not None
    assert nine is None or half <= nine
    for month in (60, 180, 360):
        assert out.reached_share(D(150_000), month) >= out.chance(D(150_000), month)
    assert out.reached_by(D(10**9), D("0.5")) is None


@pytest.mark.parametrize(
    ("categories", "message"),
    [
        ([_category("stocks", "1000", share="0.5")], "sum to 1"),
        ([_category("stocks", "-1", share="1")], "positive"),
        ([], "nowhere"),
    ],
)
def test_impossible_inputs_are_refused(categories: list[Category], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        simulate(_scenario(categories, 3, savings="100"), paths=5)


def test_paths_and_months_are_bounded() -> None:
    s = _scenario([_category("stocks", "1000", share="1")], 3)
    with pytest.raises(ValueError, match="path"):
        simulate(s, paths=0)
    out = simulate(s, paths=5)
    with pytest.raises(ValueError, match="month"):
        out.chance(D(1), 4)
    with pytest.raises(ValueError, match="month"):
        out.chance(D(1), -1)


def test_amounts_are_rounded_half_up_to_the_cent() -> None:
    s = _scenario([_category("savings", "0.125", share="1")], 1)
    assert simulate(s, paths=1).percentiles(today=False)[0][50] == D("0.13")


def test_the_shortfall_has_its_own_median_month_by_month() -> None:
    """The stacked chart draws it below zero next to the debts (F-SIM-5)."""
    livret = _category("savings", "300", share="1")
    s = Scenario([livret], [D(-500), D(0)], [D(0)] * 2, D(0), D("0.12"))
    out = simulate(s, paths=3)
    owed = 200 * (1 + float(SHORTFALL_RATE) / 12)
    assert out.shortfall_median(today=False) == [D(0), D("200.00"), D(f"{owed:.2f}")]
    assert out.shortfall_median()[2] == D(f"{owed / 1.12 ** (2 / 12):.2f}")


def test_the_liquid_holdings_have_their_own_median() -> None:
    """The retirement fan draws the liquid part apart: the home is never taken (F-RET-4)."""
    livret = _category("savings", "1000", share="1")
    house = _category("real-estate", "200000")
    out = simulate(Scenario([livret, house], [D(100)] * 2, [D(0)] * 2, D(0), D(0)), paths=3)
    assert out.liquid_medians(today=False) == [D(1000), D(1100), D(1200)]


def test_a_split_by_month_sends_each_month_s_savings_where_it_says() -> None:
    """F-SIM-3: indexed and fixed contributions mix, so the allocation moves month by month."""
    a, b = _category("stocks", "0"), _category("savings", "0")
    s = Scenario(
        [a, b],
        [D(100), D(100)],
        [D(0)] * 2,
        D(0),
        D(0),
        split=[[D(1), D(0)], [D("0.25"), D("0.75")]],
    )
    out = simulate(s, paths=2)
    assert out.medians_by_category(today=False)[2] == [D(125), D(75)]


@pytest.mark.parametrize(
    "split",
    [[[D(1), D(0)]], [[D("0.5"), D("0.4")], [D(1), D(0)]], [[D(1)], [D(1)]]],
)
def test_a_split_has_a_row_per_month_summing_to_one(split: list[list[Decimal]]) -> None:
    a, b = _category("stocks", "0"), _category("savings", "0", share="1")
    s = Scenario([a, b], [D(100)] * 2, [D(0)] * 2, D(0), D(0), split=split)
    with pytest.raises(ValueError, match="split"):
        simulate(s, paths=2)


def test_the_liquid_holdings_have_a_tenth_percentile() -> None:
    """F-SIM-5: the income in nine outcomes in ten draws on it."""
    stocks = _category("stocks", "10000", "0.07", "0.16", share="1")
    house = _category("real-estate", "200000")
    out = simulate(Scenario([stocks, house], [D(100)] * 24, [D(0)] * 24, D(0), D(0)), paths=500)
    lows, medians = out.liquid_lows(today=False), out.liquid_medians(today=False)
    assert lows[0] == medians[0] == D(10000)
    assert all(low <= m for low, m in zip(lows, medians, strict=True))
    assert lows[24] < medians[24]
