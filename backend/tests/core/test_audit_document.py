from decimal import Decimal
from uuid import uuid4

import pytest
from hypothesis import given
from hypothesis import strategies as st
from kwak_core.audit_document import (
    DEBT_CEILING,
    Audience,
    AuditError,
    Duration,
    Privacy,
    Project,
    PropertyAge,
    before_tax,
    by_year,
    check_period,
    check_project,
    check_withholding,
    counted_by_default,
    debt_end,
    debt_ratio,
    default_period,
    default_privacy,
    duration_check,
    largest_first,
    member_letter,
    monthly_payment,
    months_of,
    notary_fees,
    number_within,
    percent,
    project_figures,
    ratio_income,
    rounded,
    rounded_parts,
    rounded_wealth,
    spread,
)
from kwak_core.budget import Month, month_range
from kwak_core.projection import DebtTerms
from kwak_core.spending import MonthFigures

D = Decimal
NOV = Month(2026, 11)
OCT = Month(2026, 10)


# F-AUD-1: the period


def test_the_default_period_is_the_last_twelve_complete_months() -> None:
    period = default_period(current=NOV, since=Month(2024, 1))
    assert (period.start, period.end, period.shortened) == (Month(2025, 11), OCT, False)


def test_a_shorter_history_starts_at_the_first_month_with_a_line_and_says_so() -> None:
    period = default_period(current=NOV, since=Month(2026, 6))
    assert (period.start, period.end, period.shortened) == (Month(2026, 6), OCT, True)


def test_a_history_starting_this_month_still_gives_one_month() -> None:
    period = default_period(current=NOV, since=NOV)
    assert (period.start, period.end, period.shortened) == (OCT, OCT, True)


def test_without_any_line_the_period_is_the_default_one() -> None:
    period = default_period(current=NOV, since=None)
    assert (period.start, period.end, period.shortened) == (Month(2025, 11), OCT, False)


@pytest.mark.parametrize(
    ("start", "end"),
    [
        (Month(2026, 1), NOV),  # the current month is not complete
        (OCT, Month(2026, 9)),  # ends before it starts
        (Month(2021, 10), OCT),  # 61 months
    ],
)
def test_a_period_is_1_to_60_complete_months(start: Month, end: Month) -> None:
    with pytest.raises(AuditError):
        check_period(start, end, current=NOV)


def test_sixty_complete_months_are_fine() -> None:
    check_period(Month(2021, 11), OCT, current=NOV)
    check_period(OCT, OCT, current=NOV)


# F-AUD-4: privacy


def test_privacy_defaults_by_audience() -> None:
    named = Privacy(named_members=True, named_lines=True, exact_amounts=True)
    assert default_privacy(Audience.BANKER) == named
    assert default_privacy(Audience.ADVISOR) == named
    assert default_privacy(Audience.NOTARY) == named
    assert default_privacy(Audience.AI) == Privacy(
        named_members=False, named_lines=False, exact_amounts=True
    )


def test_members_are_lettered_in_order() -> None:
    assert [member_letter(i) for i in (0, 1, 25, 26, 27)] == ["A", "B", "Z", "AA", "AB"]


def test_lines_and_goals_are_numbered_within_their_group_in_order() -> None:
    a, b, c, d = (uuid4() for _ in range(4))
    numbers = number_within([(a, "pea"), (b, "savings"), (c, "pea"), (d, "pea")])
    assert numbers == {a: 1, b: 1, c: 2, d: 3}


def test_amounts_round_half_up_to_their_step() -> None:
    assert rounded(D("1234.56"), D(10)) == D(1230)
    assert rounded(D("1235.00"), D(10)) == D(1240)
    assert rounded(D("-1235.00"), D(10)) == D(-1240)
    assert rounded(D("152499.99"), D(1000)) == D(152000)
    assert rounded(D("152500"), D(1000)) == D(153000)


def test_rounded_parts_add_up_to_the_rounded_total() -> None:
    parts = {"a": D("1400"), "b": D("1400"), "c": D("1400")}
    out = rounded_parts(parts, D(1000))
    assert sum(out.values()) == D(4000)  # 4200 rounds to 4000, not 3 x 1000
    assert sorted(out.values()) == [D(1000), D(1000), D(2000)]


@given(
    st.lists(
        st.decimals(min_value=-10_000_000, max_value=10_000_000, places=2, allow_nan=False),
        min_size=0,
        max_size=12,
    ),
    st.sampled_from([D(10), D(1000)]),
)
def test_rounded_parts_always_sum_to_the_rounded_total_invariant_48(
    amounts: list[Decimal], step: Decimal
) -> None:
    parts = dict(enumerate(amounts))
    out = rounded_parts(parts, step)
    assert set(out) == set(parts)
    assert sum(out.values(), D(0)) == rounded(sum(amounts, D(0)), step)
    for key, value in out.items():
        assert value % step == 0
        assert abs(value - parts[key]) < step  # never more than a step away


def test_rounded_net_worth_is_rounded_assets_minus_rounded_debts() -> None:
    a, d = uuid4(), uuid4()
    w = rounded_wealth({a: D(1600)}, {d: D(400)}, D(1000))
    assert (w.gross, w.owed, w.net) == (D(2000), D(0), D(2000))


@given(
    st.lists(st.decimals(min_value=0, max_value=5_000_000, places=2), max_size=8),
    st.lists(st.decimals(min_value=0, max_value=5_000_000, places=2), max_size=4),
)
def test_rounded_wealth_adds_up_invariant_48(assets: list[Decimal], debts: list[Decimal]) -> None:
    w = rounded_wealth({uuid4(): v for v in assets}, {uuid4(): v for v in debts}, D(1000))
    assert w.gross == sum(w.assets.values(), D(0))
    assert w.owed == sum(w.debts.values(), D(0))
    assert w.net == w.gross - w.owed


def test_a_ratio_shows_as_a_percent_to_one_decimal() -> None:
    assert percent(D("0.34951")) == D("35.0")
    assert percent(D("0.3449")) == D("34.5")


# F-AUD-2: the facts


def test_spread_gives_total_average_lowest_and_highest_month() -> None:
    values = [(Month(2026, 8), D(100)), (Month(2026, 9), D(400)), (OCT, D(100))]
    s = spread(values)
    assert (s.total, s.average) == (D(600), D(200))
    assert s.lowest == (Month(2026, 8), D(100))  # the first of equals
    assert s.highest == (Month(2026, 9), D(400))


def test_an_average_is_to_the_cent() -> None:
    s = spread([(Month(2026, 9), D(100)), (OCT, D(0)), (NOV, D(0))])
    assert s.average == D("33.33")


def test_largest_first_groups_the_rest() -> None:
    a, b, c, d = (uuid4() for _ in range(4))
    top, rest = largest_first({a: D(10), b: D(50), c: D(30), d: D(0)}, limit=2)
    assert top == [(b, D(50)), (c, D(30))]
    assert rest == D(10)


def test_years_total_their_months_and_say_when_partial() -> None:
    months = month_range(Month(2025, 11), OCT)
    figures = [(m, MonthFigures(D(1000), D(600), D(100))) for m in months]
    years = by_year(figures)
    assert [(y.year, y.months, y.partial) for y in years] == [(2025, 2, True), (2026, 10, True)]
    assert years[0].figures == MonthFigures(D(2000), D(1200), D(200))
    full = by_year([(m, MonthFigures.zero()) for m in month_range(Month(2025, 1), Month(2025, 12))])
    assert [(y.year, y.partial) for y in full] == [(2025, False)]


def test_ratio_income_averages_the_counted_categories_over_the_period() -> None:
    salary, refunds = uuid4(), uuid4()
    totals = {salary: D(36000), refunds: D(1200)}
    assert ratio_income(totals, counted={salary}, months=12) == D(3000)
    assert ratio_income(totals, counted={salary, refunds}, months=12) == D(3100)


def test_refunds_are_left_out_of_the_ratio_income_by_default_whatever_their_name() -> None:
    salary, refunds, custom = uuid4(), uuid4(), uuid4()
    presets = {salary: "salaries", refunds: "refunds", custom: None}
    assert counted_by_default(presets) == {salary, custom}


def test_the_before_tax_income_is_estimated_from_the_withholding() -> None:
    # 34 % after a 9 % withholding is about 31 % before tax (F-AUD-2).
    income = D(3000)
    ratio = debt_ratio(D(1020), before_tax(income, D("0.09")))
    assert ratio is not None
    assert percent(ratio) == D("30.9")


def test_the_debt_ratio_is_none_without_income() -> None:
    assert debt_ratio(D(1000), D(3000)) == D(1000) / D(3000)
    assert debt_ratio(D(1000), D(0)) is None
    assert debt_ratio(D(0), D(0)) is None


def test_the_precaution_in_months_of_fixed_expenses() -> None:
    assert months_of(D(9000), D(1500)) == D(6)
    assert months_of(D(9000), D(0)) is None


def test_a_debt_ends_the_month_its_payment_repays_it() -> None:
    # 1,000 owed at 0 %, 300 a month from November: Nov 700, Dec 400, Jan 100, Feb 0.
    assert debt_end(D(1000), DebtTerms(D(300)), last=OCT) == Month(2027, 2)


def test_a_debt_end_is_unknown_without_a_payment_or_when_it_grows() -> None:
    assert debt_end(D(1000), DebtTerms(None), last=OCT) is None
    assert debt_end(D(100_000), DebtTerms(D(100), rate=D("0.05")), last=OCT) is None
    assert debt_end(D(0), DebtTerms(D(100)), last=OCT) is None


# F-AUD-5: the property project


def test_the_payment_is_the_constant_amortised_one_at_the_proportional_rate() -> None:
    # 200,000 over 20 years at 3.5 %: 1,159.92 a month.
    assert monthly_payment(D(200_000), D("0.035"), 20) == D("1159.92")


def test_with_a_zero_rate_the_payment_is_the_amount_over_the_months() -> None:
    assert monthly_payment(D(120_000), D(0), 10) == D(1000)


def test_notary_fees_by_property_age() -> None:
    assert notary_fees(D(300_000), PropertyAge.OLD) == D(24_000)
    assert notary_fees(D(300_000), PropertyAge.NEW) == D(7_500)


def test_durations_against_the_hcsf_maximum() -> None:
    assert duration_check(25) is Duration.WITHIN
    assert duration_check(26) is Duration.DEFERRED_ONLY
    assert duration_check(27) is Duration.DEFERRED_ONLY
    assert duration_check(28) is Duration.ABOVE


def test_the_withholding_rate_is_0_to_45_percent_to_the_tenth() -> None:
    check_withholding(D("0.091"))
    check_withholding(D("0.45"))
    for bad in (D("-0.01"), D("0.451"), D("0.0905")):
        with pytest.raises(AuditError):
            check_withholding(bad)


def _project(**changes: object) -> Project:
    base: dict[str, object] = {
        "price": D(250_000),
        "notary_fees": D(20_000),
        "agency_fees": D(0),
        "guarantee_fees": D(3_000),
        "down_payment": D(33_000),
        "loan": None,
        "years": 25,
        "rate": D("0.035"),
        "insurance": D(50),
        "rent": D(900),
        "rent_stops": True,
    }
    base.update(changes)
    return Project(**base)  # type: ignore[arg-type]


def test_project_figures() -> None:
    out = project_figures(
        _project(), ratio_income=D(5000), running_payments=D(200), liquid=D(50_000)
    )
    assert out.cost == D(273_000)
    assert out.loan == D(240_000)  # price + fees - down payment
    assert out.payment == monthly_payment(D(240_000), D("0.035"), 25)
    housing = out.payment + D(50)
    assert out.ratio_after == (D(200) + housing) / D(5000)
    assert out.remaining_after_housing == D(5000) - D(200) - housing  # the rent stops
    assert out.housing_change == housing - D(900)
    assert out.down_share == D(33_000) / D(273_000)
    assert out.liquid_left == D(17_000)
    assert out.above_ceiling == (out.ratio_after is not None and out.ratio_after > DEBT_CEILING)


def test_a_rent_that_goes_on_weighs_on_the_remaining_income_not_on_the_ratio() -> None:
    out = project_figures(
        _project(rent_stops=False), ratio_income=D(5000), running_payments=D(0), liquid=D(0)
    )
    housing = out.payment + D(50)
    assert out.ratio_after == housing / D(5000)
    assert out.remaining_after_housing == D(5000) - housing - D(900)
    assert out.housing_change == housing


def test_a_loan_amount_entered_replaces_the_default() -> None:
    out = project_figures(
        _project(loan=D(200_000)), ratio_income=D(5000), running_payments=D(0), liquid=D(0)
    )
    assert out.loan == D(200_000)


def test_project_bounds() -> None:
    check_project(_project())
    for bad in (
        _project(years=0),
        _project(years=31),
        _project(rate=D("-0.01")),
        _project(rate=D("0.2001")),
        _project(price=D(0)),
        _project(down_payment=D(-1)),
        _project(insurance=D("1.234")),
        _project(down_payment=D(300_000)),  # nothing left to borrow
        _project(down_payment=D(300_000), loan=D(1000)),  # more than price and fees
        _project(rate=D("Infinity")),
    ):
        with pytest.raises(AuditError):
            check_project(bad)


AMOUNTS = st.decimals(min_value=1_000, max_value=1_000_000, places=2, allow_nan=False)
RATES = st.decimals(min_value=0, max_value=D("0.2"), places=4, allow_nan=False)
YEARS = st.integers(min_value=1, max_value=30)


@given(AMOUNTS, RATES, YEARS)
def test_the_payment_is_the_annuity_formula_to_the_cent_invariant_49(
    amount: Decimal, rate: Decimal, years: int
) -> None:
    n = years * 12
    r = float(rate) / 12
    expected = float(amount) / n if r == 0 else float(amount) * r / (1 - (1 + r) ** -n)
    assert abs(float(monthly_payment(amount, rate, years)) - expected) <= 0.005 + 1e-6


@given(AMOUNTS, AMOUNTS, RATES, RATES, YEARS, st.decimals(min_value=1, max_value=50_000, places=2))
def test_the_ratio_after_the_loan_never_falls_as_the_loan_or_its_rate_rises_invariant_49(
    a: Decimal, b: Decimal, r1: Decimal, r2: Decimal, years: int, income: Decimal
) -> None:
    def ratio(loan: Decimal, rate: Decimal, income: Decimal) -> Decimal:
        out = project_figures(
            _project(price=D(1_100_000), loan=loan, rate=rate, years=years),
            ratio_income=income,
            running_payments=D(100),
            liquid=D(0),
        )
        assert out.ratio_after is not None
        return out.ratio_after

    low, high = sorted((a, b))
    slow, shigh = sorted((r1, r2))
    assert ratio(low, slow, income) <= ratio(high, slow, income)
    assert ratio(low, slow, income) <= ratio(low, shigh, income)
    assert ratio(low, slow, income + 1) <= ratio(low, slow, income)
