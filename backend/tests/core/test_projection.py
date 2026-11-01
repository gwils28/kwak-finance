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
    DEFAULT_WITHDRAWAL,
    FIRST_TAKEN,
    MAX_CONTRIBUTION,
    MIN_CONTRIBUTION,
    NEVER_TAKEN,
    SHORTFALL_RATE,
    Assumption,
    Contribution,
    DebtTerms,
    ProjectionError,
    SavingsSource,
    amortise,
    assumption_of,
    beyond_ceilings,
    breakdown,
    check_allocation,
    check_assumption,
    check_contributions,
    check_debt_terms,
    check_inflation,
    check_withdrawal_rate,
    contribution_plan,
    contribution_shares,
    debt_grows,
    default_allocation,
    median_growth,
    monthly_params,
    savings_path,
    savings_source,
    starting_point,
    to_today,
    withdrawal_income,
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


# F-SIM-3: the monthly contributions

PEA, LIVRET_A = uuid4(), uuid4()


@pytest.mark.parametrize(
    "contributions",
    [
        [Contribution(PEA, D("0.99"))],
        [Contribution(PEA, D("100000.01"))],
        [Contribution(PEA, D("10.001"))],
        [Contribution(PEA, D(100)), Contribution(PEA, D(50))],
    ],
)
def test_impossible_contributions_are_refused(contributions: list[Contribution]) -> None:
    with pytest.raises(ProjectionError):
        check_contributions(contributions)


def test_a_contribution_is_from_one_euro_to_a_hundred_thousand_a_month() -> None:
    assert (D(1), D(100_000)) == (MIN_CONTRIBUTION, MAX_CONTRIBUTION)
    check_contributions([Contribution(PEA, D(1)), Contribution(LIVRET_A, D(100_000))])
    check_contributions([])


def test_an_indexed_contribution_follows_prices_and_a_fixed_one_does_not() -> None:
    plan = contribution_plan(
        [Contribution(PEA, D(300)), Contribution(LIVRET_A, D(150), indexed=False)],
        months=240,
        inflation=D("0.02"),
    )
    grown = quantize(D(300) * D("1.02") ** 20)
    assert plan.put_in[239] == grown + D(150)
    assert plan.savings == plan.put_in  # no debt frees anything
    # Each category receives its own contribution only, month after month.
    last = plan.split[239]
    assert last[LIVRET_A] * plan.put_in[239] == pytest.approx(D(150), abs=D("1e-6"))
    assert last[PEA] * plan.put_in[239] == pytest.approx(grown, abs=D("1e-6"))
    assert plan.split[0][PEA] > D("0.66")


def test_the_freed_payments_join_the_savings_split_like_the_contributions() -> None:
    plan = contribution_plan(
        [Contribution(PEA, D(100)), Contribution(LIVRET_A, D(100))],
        months=3,
        inflation=D(0),
        freed=[D(0), D(0), D(500)],
    )
    assert plan.put_in == [D(200)] * 3
    assert plan.savings == [D(200), D(200), D(700)]
    assert plan.split[2] == {PEA: D("0.5"), LIVRET_A: D("0.5")}


def test_a_what_if_scales_every_contribution() -> None:
    plan = contribution_plan(
        [Contribution(PEA, D(300)), Contribution(LIVRET_A, D(100), indexed=False)],
        months=1,
        inflation=D(0),
        scale=D(2),
    )
    assert plan.put_in == [D(800)]
    assert plan.split[0] == {PEA: D("0.75"), LIVRET_A: D("0.25")}
    with pytest.raises(ProjectionError):
        contribution_plan([Contribution(PEA, D(1))], months=1, inflation=D(0), scale=D(0))


def test_a_plan_needs_a_contribution() -> None:
    with pytest.raises(ProjectionError):
        contribution_plan([], months=12, inflation=D(0))


@given(
    st.lists(st.tuples(st.decimals(1, 100_000, places=2), st.booleans()), min_size=1, max_size=4),
    st.integers(1, 120),
    st.decimals("-0.05", "0.2", places=3),
)
def test_each_month_s_split_sums_to_one(
    amounts: list[tuple[Decimal, bool]], months: int, inflation: Decimal
) -> None:
    """Invariant §8.45: the savings are the contributions' sum, the allocation their split."""
    contributions = [Contribution(uuid4(), a, indexed=i) for a, i in amounts]
    plan = contribution_plan(contributions, months=months, inflation=inflation)
    for t in (0, months - 1):
        assert sum(plan.split[t].values()) == 1
        assert all(0 <= v <= 1 for v in plan.split[t].values())
    for t in (1, months):
        for c in contributions:
            own = c.amount * (1 + inflation) ** (D(t) / 12) if c.indexed else c.amount
            assert plan.split[t - 1][c.category_id] * plan.put_in[t - 1] == pytest.approx(
                quantize(own), abs=D("0.01")
            )


# F-SIM-5: where the money comes from


def test_in_current_euros_the_parts_are_the_amounts_as_paid() -> None:
    parts = breakdown(
        start_net=D(10_000),
        savings=[D(100), D(100)],
        start_debts=D(1_000),
        owed=[D(900), D(800)],
        medians=[D(10_000), D(10_250), D(10_500)],
        inflation=D("0.02"),
        today=False,
    )
    assert [(p.today, p.contributed, p.repaid, p.gains) for p in parts] == [
        (D(10_000), D(0), D(0), D(0)),
        (D(10_000), D(100), D(100), D(50)),
        (D(10_000), D(200), D(200), D(100)),
    ]


def test_in_today_s_euros_each_amount_counts_when_it_was_added() -> None:
    """Indexed savings keep their value; a part paid later is worth less today, so the gains
    are after inflation (negative when the holdings earn less than prices rise)."""
    rate = D("0.02")
    savings = savings_path(D(500), months=24, inflation=rate)
    parts = breakdown(
        start_net=D(1_000),
        savings=savings,
        start_debts=D(0),
        owed=[D(0)] * 24,
        medians=[D(1_000)] + [D(1_000) + D(500) * t - D(10) for t in range(1, 25)],
        inflation=rate,
        today=True,
    )
    assert parts[24].contributed == pytest.approx(D(12_000), abs=D("0.2"))
    assert parts[24].gains < 0
    assert parts[24].today == D(1_000)


@given(
    st.lists(st.decimals(-500, 5_000, places=2), min_size=1, max_size=36),
    st.decimals(0, 50_000, places=2),
    st.decimals("-0.05", "0.2", places=3),
    st.booleans(),
)
def test_the_four_parts_add_up_to_the_median(
    savings: list[Decimal], start_debts: Decimal, inflation: Decimal, today: bool
) -> None:
    """Invariant §8.46."""
    n = len(savings)
    path = amortise(start_debts, DebtTerms(D(400), D("0.03")), months=n)
    medians = [D(20_000) + D(37) * t for t in range(n + 1)]
    parts = breakdown(
        start_net=D(20_000),
        savings=savings,
        start_debts=start_debts,
        owed=path.owed,
        medians=medians,
        inflation=inflation,
        today=today,
    )
    assert len(parts) == n + 1
    for p, m in zip(parts, medians, strict=True):
        assert p.today + p.contributed + p.repaid + p.gains == quantize(m)


def test_the_income_is_the_liquid_holdings_at_a_withdrawal_rate_from_2_to_5_percent() -> None:
    assert D("0.04") == DEFAULT_WITHDRAWAL
    assert withdrawal_income(D("300000"), D("0.04")) == D(1000)
    assert withdrawal_income(D("100000"), D("0.035")) == D("291.67")
    for rate in (D("0.019"), D("0.051"), D("0.0405")):
        with pytest.raises(ProjectionError):
            check_withdrawal_rate(rate)
    check_withdrawal_rate(D("0.02"))
    check_withdrawal_rate(D("0.05"))


def test_savings_accounts_beyond_a_full_livret_a_and_ldds_a_member_are_noted() -> None:
    """In current euros: the ceilings are not indexed."""
    assert beyond_ceilings(D("34950"), members=1) is False
    assert beyond_ceilings(D("34950.01"), members=1) is True
    assert beyond_ceilings(D("60000"), members=2) is False


# F-SIM-3: where the monthly savings come from


def test_the_savings_are_declared_by_default_once_a_contribution_exists() -> None:
    assert savings_source(None, has_contributions=True) is SavingsSource.DECLARED
    assert savings_source(None, has_contributions=False) is SavingsSource.MEASURED


def test_a_chosen_source_is_kept_with_or_without_contributions() -> None:
    for has in (True, False):
        assert savings_source(SavingsSource.DECLARED, has_contributions=has) is (
            SavingsSource.DECLARED
        )
        assert savings_source(SavingsSource.MEASURED, has_contributions=has) is (
            SavingsSource.MEASURED
        )


def test_measured_savings_are_split_like_the_contributions() -> None:
    livret, stocks = uuid4(), uuid4()
    shares = contribution_shares([Contribution(livret, D(200)), Contribution(stocks, D(400))])
    third = (D(1) / 3).quantize(D("1e-12"))
    assert shares == {livret: third, stocks: 1 - third}


@given(
    st.lists(
        st.decimals(min_value=1, max_value=100_000, places=2),
        min_size=1,
        max_size=8,
    )
)
def test_the_contributions_shares_sum_to_exactly_one(amounts: list[Decimal]) -> None:
    shares = contribution_shares([Contribution(uuid4(), a) for a in amounts])
    assert sum(shares.values()) == 1
    assert all(s >= 0 for s in shares.values())


def test_no_contribution_has_no_shares() -> None:
    with pytest.raises(ProjectionError):
        contribution_shares([])
