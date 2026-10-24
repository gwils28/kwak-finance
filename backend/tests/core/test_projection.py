import math
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from hypothesis import given
from hypothesis import strategies as st
from kwak_core.budget import Month
from kwak_core.money import quantize
from kwak_core.projection import (
    DEFAULT_ASSUMPTIONS,
    DEFAULT_INFLATION,
    FIRST_TAKEN,
    NEVER_TAKEN,
    SHORTFALL_RATE,
    Assumption,
    DebtTerms,
    ProjectionError,
    amortise,
    assumption_of,
    check_allocation,
    check_assumption,
    check_debt_terms,
    check_inflation,
    debt_grows,
    default_allocation,
    median_growth,
    monthly_params,
    savings_path,
    starting_point,
    to_today,
)
from kwak_core.visibility import Visibility
from kwak_core.wealth import (
    DEFAULT_WEALTH_CATEGORIES,
    CategoryInput,
    LineInput,
    WealthKind,
    wealth_matrix,
)

D = Decimal
SEP, OCT, NOV = Month(2026, 9), Month(2026, 10), Month(2026, 11)
ME = uuid4()


# F-SIM-1: assumptions


def test_the_defaults_follow_the_spec() -> None:
    assert {c.colour for c in DEFAULT_WEALTH_CATEGORIES} - {"debts"} == set(DEFAULT_ASSUMPTIONS)
    assert DEFAULT_ASSUMPTIONS["savings"] == Assumption(D("0.017"), D(0))
    assert DEFAULT_ASSUMPTIONS["stocks"] == Assumption(D("0.07"), D("0.16"))
    assert DEFAULT_ASSUMPTIONS["crypto"] == Assumption(D("0.08"), D("0.6"))
    assert DEFAULT_ASSUMPTIONS["private-equity"] == Assumption(D("0.06"), D("0.25"))
    assert DEFAULT_ASSUMPTIONS["gold"] == Assumption(D("0.03"), D("0.15"))
    assert DEFAULT_ASSUMPTIONS["real-estate"] == Assumption(D("0.025"), D("0.08"))
    assert DEFAULT_ASSUMPTIONS["equipment"] == Assumption(D("-0.15"), D(0))
    assert DEFAULT_ASSUMPTIONS["exotic"] == Assumption(D(0), D("0.2"))
    assert assumption_of(None) == assumption_of("unknown") == Assumption(D(0), D(0))
    assert D("0.02") == DEFAULT_INFLATION


@pytest.mark.parametrize(
    ("ret", "volatility"),
    [("-1", "0"), ("1.01", "0"), ("0.07", "-0.01"), ("0.07", "2.01"), ("0.0715", "0")],
)
def test_an_impossible_assumption_is_refused(ret: str, volatility: str) -> None:
    with pytest.raises(ProjectionError):
        check_assumption(Assumption(D(ret), D(volatility)))
    with pytest.raises(ProjectionError):
        monthly_params(Assumption(D(ret), D(volatility)))


@pytest.mark.parametrize(("ret", "volatility"), [("-0.999", "0"), ("1", "2"), ("0.071", "0")])
def test_the_bounds_are_allowed(ret: str, volatility: str) -> None:
    check_assumption(Assumption(D(ret), D(volatility)))


@pytest.mark.parametrize(
    ("inflation", "ok"),
    [
        ("-0.05", True),
        ("0.2", True),
        ("0.021", True),
        ("-0.051", False),
        ("0.201", False),
        ("0.0215", False),
    ],
)
def test_the_inflation_bounds(inflation: str, ok: bool) -> None:
    if ok:
        check_inflation(D(inflation))
    else:
        with pytest.raises(ProjectionError):
            check_inflation(D(inflation))


def test_the_median_growth_is_below_the_mean() -> None:
    """F-SIM-1's examples: stocks 7 % ± 16 % grow by 5.8 % in the median, crypto lose 5.6 %."""
    assert median_growth(Assumption(D("0.07"), D("0.16"))).quantize(D("0.001")) == D("0.058")
    assert median_growth(Assumption(D("0.08"), D("0.6"))).quantize(D("0.001")) == D("-0.056")
    assert median_growth(Assumption(D("0.017"), D(0))) == D("0.017")


@given(st.decimals("-0.999", "1", places=3), st.decimals(0, "2", places=3))
def test_twelve_monthly_draws_compound_to_the_annual_mean_and_volatility(
    ret: Decimal, volatility: Decimal
) -> None:
    """F-SIM-4: a monthly log-return N(mu_m, sigma_m^2) over 12 months is lognormal with mean
    1 + ret and standard deviation volatility (the drift is ln(1+ret)/12 - sigma_m^2/2)."""
    mu_m, sigma_m = monthly_params(Assumption(ret, volatility))
    m, s2 = 12 * float(mu_m), 12 * float(sigma_m) ** 2
    mean = math.exp(m + s2 / 2)
    sd = math.sqrt((math.exp(s2) - 1) * math.exp(2 * m + s2))
    assert mean == pytest.approx(1 + float(ret), rel=1e-9)
    assert sd == pytest.approx(float(volatility), rel=1e-9, abs=1e-12)


# F-SIM-2: the starting point


SAVINGS, STOCKS, DEBTS = uuid4(), uuid4(), uuid4()
CATEGORIES = [
    CategoryInput(SAVINGS, WealthKind.ASSET),
    CategoryInput(STOCKS, WealthKind.ASSET),
    CategoryInput(DEBTS, WealthKind.DEBT),
]


def _line(category: UUID, values: dict[Month, str], **kw: object) -> LineInput:
    return LineInput(
        uuid4(),
        category,
        {m: D(v) for m, v in values.items()},
        ME,
        Visibility.SHARED,
        **kw,  # type: ignore[arg-type]
    )


def test_the_start_is_the_current_month_carried_forward() -> None:
    livret = _line(SAVINGS, {SEP: "1000", NOV: "9999"})  # November is after the start
    pea = _line(STOCKS, {OCT: "3000"})
    loan = _line(DEBTS, {SEP: "500"})
    closed = _line(STOCKS, {SEP: "700"}, closed_from=OCT)
    start = starting_point(CATEGORIES, [livret, pea, loan, closed], OCT)
    assert start.month == OCT
    assert start.assets == {SAVINGS: D(1000), STOCKS: D(3000)}
    assert start.debts == {loan.id: D(500)}
    assert start.net == D(3500)


@given(
    st.lists(
        st.tuples(
            st.sampled_from([SAVINGS, STOCKS, DEBTS]),
            st.dictionaries(st.sampled_from([SEP, OCT, NOV]), st.decimals(0, 10_000, places=2)),
        ),
        max_size=6,
    )
)
def test_the_start_matches_the_wealth_matrix(
    lines: list[tuple[UUID, dict[Month, Decimal]]],
) -> None:
    """Invariant §8.23: the first month is exactly the scope's matrix that month, and nothing
    entered after it is read."""
    inputs = [LineInput(uuid4(), c, values, ME, Visibility.SHARED) for c, values in lines]
    start = starting_point(CATEGORIES, inputs, OCT)
    matrix = wealth_matrix(CATEGORIES, inputs, [OCT])
    assert start.net == matrix.net[0]
    for c in (SAVINGS, STOCKS):
        assert start.assets.get(c, D(0)) == matrix.categories[c][0]
    later = [
        LineInput(i.id, i.category_id, {**i.values, NOV: D(1)}, ME, Visibility.SHARED)
        for i in inputs
    ]
    assert starting_point(CATEGORIES, later, OCT) == start


# F-SIM-3: the allocation


def test_the_default_allocation_leaves_out_what_monthly_savings_do_not_buy() -> None:
    """Current accounts (a working balance), real estate, equipment and private equity."""
    current, house, pe = uuid4(), uuid4(), uuid4()
    presets = {
        SAVINGS: "savings",
        STOCKS: "stocks",
        current: "current",
        house: "real-estate",
        pe: "private-equity",
    }
    assets = {SAVINGS: D(1000), STOCKS: D(3000), current: D(5000), house: D(200000), pe: D(9000)}
    assert default_allocation(assets, presets) == {SAVINGS: D("0.25"), STOCKS: D("0.75")}


def test_with_nothing_to_share_by_savings_go_to_savings_accounts() -> None:
    current, house = uuid4(), uuid4()
    presets = {SAVINGS: "savings", current: "current"}
    assert default_allocation({current: D(5000)}, presets) == {SAVINGS: D(1)}
    # Savings accounts deleted: current accounts; neither: the scenario sets its own.
    assert default_allocation({}, {current: "current", house: "real-estate"}) == {current: D(1)}
    with pytest.raises(ProjectionError, match="allocation"):
        default_allocation({house: D(1000)}, {house: "real-estate"})


PRESETS = [
    "savings",
    "current",
    "stocks",
    "crypto",
    "real-estate",
    "equipment",
    "private-equity",
    "exotic",
    None,
]


@given(
    st.lists(
        st.tuples(st.sampled_from(PRESETS), st.decimals(0, 100_000, places=2)),
        min_size=1,
        max_size=8,
    )
)
def test_the_shares_sum_to_one_and_skip_what_savings_do_not_buy(
    held: list[tuple[str | None, Decimal]],
) -> None:
    ids = [uuid4() for _ in held]
    presets = {i: p for i, (p, _) in zip(ids, held, strict=True)} | {uuid4(): "savings"}
    assets = {i: v for i, (_, v) in zip(ids, held, strict=True)}
    shares = default_allocation(assets, presets)
    assert sum(shares.values(), D(0)) == 1
    assert all(v >= 0 for v in shares.values())
    kept = [c for c in shares if assets.get(c, D(0)) > 0]
    assert all(
        presets[c] not in ("current", "real-estate", "equipment", "private-equity", "exotic")
        for c in kept
    )


def test_exotic_holdings_take_no_monthly_savings_and_are_never_sold_for_spending() -> None:
    """Wine, art and watches are illiquid, as the goals analysis judges them (F-ANA-1)."""
    wine = uuid4()
    presets = {SAVINGS: "savings", wine: "exotic"}
    assert default_allocation({SAVINGS: D(1000), wine: D(5000)}, presets) == {SAVINGS: D(1)}
    assert "exotic" in NEVER_TAKEN
    assert {"real-estate", "equipment", "private-equity", "exotic"} == NEVER_TAKEN
    assert FIRST_TAKEN == ("current", "savings")
    assert D("0.08") == SHORTFALL_RATE


def test_a_scenario_allocation_sums_to_100() -> None:
    check_allocation({SAVINGS: 40, STOCKS: 60})
    with pytest.raises(ProjectionError, match="100"):
        check_allocation({SAVINGS: 40, STOCKS: 50})
    with pytest.raises(ProjectionError):
        check_allocation({SAVINGS: -10, STOCKS: 110})


# F-SIM-3: the debts


def test_a_debt_falls_by_its_payment_less_its_interest_then_frees_it() -> None:
    path = amortise(D(1000), DebtTerms(payment=D(400), rate=D("0.12")), months=4)
    # 1000 + 10 - 400, 610 + 6.10 - 400, 216.10 + 2.16 - 218.26 (the rest), then nothing
    assert path.owed == [D("610.00"), D("216.10"), D(0), D(0)]
    # In the month it is repaid, what the payment did not need; then all of it.
    assert path.freed == [D(0), D(0), D("181.74"), D(400)]


def test_the_borrower_insurance_repays_nothing_and_stops_with_the_loan() -> None:
    terms = DebtTerms(payment=D(400), rate=D("0.12"), insurance=D(30))
    path = amortise(D(1000), terms, months=4)
    assert path.owed == [D("610.00"), D("216.10"), D(0), D(0)]
    # Paid until the loan ends, then freed with the payment.
    assert path.freed == [D(0), D(0), D("181.74"), D(430)]
    with pytest.raises(ProjectionError):
        check_debt_terms(DebtTerms(D(400), insurance=D("-1")))


def test_a_debt_repaid_before_the_start_frees_nothing() -> None:
    """Its payment is no longer spent: the capacity already counts it."""
    path = amortise(D(0), DebtTerms(payment=D(500), rate=D("0.03"), insurance=D(20)), months=3)
    assert path.owed == path.freed == [D(0)] * 3


def test_a_payment_below_the_interest_lets_the_debt_grow() -> None:
    assert debt_grows(D(1000), DebtTerms(payment=D(5), rate=D("0.12")))
    assert debt_grows(D(1000), DebtTerms(payment=D(0), rate=D("0.12")))
    assert not debt_grows(D(1000), DebtTerms(payment=D(11), rate=D("0.12")))
    assert not debt_grows(D(1000), DebtTerms(payment=None, rate=D("0.12")))
    assert amortise(D(1000), DebtTerms(D(5), D("0.12")), months=2).owed == [
        D("1005.00"),
        D("1010.05"),
    ]


@pytest.mark.parametrize(
    "terms",
    [
        DebtTerms(D("-1")),
        DebtTerms(D("100.001")),
        DebtTerms(D(100), D("-0.01")),
        DebtTerms(D(100), D("1.01")),
        DebtTerms(D(100), D("0.03255")),
    ],
)
def test_impossible_debt_terms_are_refused(terms: DebtTerms) -> None:
    with pytest.raises(ProjectionError):
        check_debt_terms(terms)


def test_a_loan_rate_takes_hundredths_of_a_percent() -> None:
    check_debt_terms(DebtTerms(D("1250.00"), D("0.0325")))
    check_debt_terms(DebtTerms(None))
    check_debt_terms(DebtTerms(D(0), D(1)))


def test_a_debt_without_a_payment_stays_owed() -> None:
    path = amortise(D(1000), DebtTerms(payment=None, rate=D("0.05")), months=3)
    assert path.owed == [D(1000)] * 3
    assert path.freed == [D(0)] * 3


@given(
    st.decimals(0, 300_000, places=2),
    st.decimals(1, 5_000, places=2),
    st.decimals(0, "0.2", places=4),
    st.integers(1, 480),
)
def test_a_debt_falls_by_its_payment_less_its_interest_never_below_zero(
    owed: Decimal, payment: Decimal, rate: Decimal, months: int
) -> None:
    """Invariants §8.25 and 27: each month exactly by the payment less the interest, never
    below zero, never above the start when the payment covers the interest; what the payment
    no longer needs joins the savings, and payment plus freed add up to the payment."""
    path = amortise(owed, DebtTerms(payment=payment, rate=rate), months=months)
    assert len(path.owed) == len(path.freed) == months
    before = owed
    for now, freed in zip(path.owed, path.freed, strict=True):
        due = before + quantize(before * rate / 12)
        assert now == (max(D(0), due - payment) if before > 0 else D(0))
        assert now >= 0
        if not debt_grows(owed, DebtTerms(payment, rate)):
            assert now <= owed
        if before > 0 and now == 0:
            assert freed == payment - due
        elif before == 0 and owed > 0:
            assert freed == payment
        else:
            assert freed == 0
        before = now


# F-SIM-3 and 4: savings and today's euros


def test_savings_keep_pace_with_prices_and_take_the_freed_payments() -> None:
    path = savings_path(D(1200), months=12, inflation=D("0.02"), freed=[D(0)] * 11 + [D(400)])
    assert path[0] == (D(1200) * D("1.02") ** (D(1) / 12)).quantize(D("0.01"))
    assert path[11] == D(1224) + D(400)


@given(
    st.decimals(-1_000_000, 1_000_000, places=2),
    st.integers(0, 480),
    st.decimals("-0.05", "0.2", places=3),
)
def test_today_s_euros_undo_the_inflation(amount: Decimal, month: int, inflation: Decimal) -> None:
    """Invariant §8.28: an amount grown by the inflation comes back to itself."""
    grown = amount * (1 + inflation) ** (D(month) / 12)
    assert to_today(grown, month, inflation) == pytest.approx(amount, abs=D("1e-15"))
    assert to_today(amount, 0, inflation) == amount


@given(st.decimals(0, 10_000, places=2), st.integers(1, 480), st.decimals("-0.05", "0.2", places=3))
def test_savings_are_constant_in_today_s_euros(
    monthly: Decimal, months: int, inflation: Decimal
) -> None:
    """F-SIM-3: savings in today's euros keep their value, but for the half-cent each month's
    amount is rounded to, in that month's euros."""
    path = savings_path(monthly, months=months, inflation=inflation)
    for t in (1, months):
        rounding = D("0.005") / (1 + inflation) ** (D(t) / 12)
        assert abs(to_today(path[t - 1], t, inflation) - monthly) <= rounding + D("1e-20")
