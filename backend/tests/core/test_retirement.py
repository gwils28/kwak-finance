"""Retirement (spec §4.13 F-RET-1 to 3, invariant §8.37): the members' months and amounts, the
household's settings, and the plan's savings month by month."""

from decimal import Decimal
from uuid import uuid4

import pytest
from hypothesis import given
from hypothesis import strategies as st
from kwak_core.budget import Month
from kwak_core.goals import add_months
from kwak_core.money import quantize
from kwak_core.projection import DebtTerms, ProjectionError, amortise, savings_path
from kwak_core.retirement import (
    DEFAULT_HORIZON_AGE,
    DEFAULT_INDEXATION,
    DEFAULT_SPENDING_SHARE,
    MAX_YEARS,
    Debt,
    Member,
    age,
    check_horizon_age,
    check_indexation,
    check_member,
    check_spending_share,
    counted,
    debt_costs,
    horizon,
    household_retirement,
    plan_savings,
    retirement_spending,
    spending_base,
)

D = Decimal
NOW = Month(2026, 10)
BORN = Month(1990, 3)
RETIRES = Month(2054, 3)


def _member(
    birth: Month | None = BORN,
    retirement: Month = RETIRES,
    earnings: str = "2500",
    pension_month: Month | None = None,
    pension: str = "1800",
) -> Member:
    return Member(uuid4(), birth, retirement, D(earnings), pension_month or retirement, D(pension))


def test_the_defaults_are_the_specs() -> None:
    assert (
        D("0.8"),
        D("-0.003"),
        95,
    ) == (DEFAULT_SPENDING_SHARE, DEFAULT_INDEXATION, DEFAULT_HORIZON_AGE)
    assert MAX_YEARS == 80


@pytest.mark.parametrize("share", [D("0.49"), D("1.51"), D("0.805")])
def test_the_spending_share_is_a_whole_percent_from_50_to_150(share: Decimal) -> None:
    with pytest.raises(ProjectionError):
        check_spending_share(share)
    check_spending_share(D("1.5"))


@pytest.mark.parametrize("rate", [D("-0.021"), D("0.011"), D("-0.0035")])
def test_the_indexation_is_from_minus_2_to_plus_1_percent_to_a_tenth(rate: Decimal) -> None:
    with pytest.raises(ProjectionError):
        check_indexation(rate)
    check_indexation(D("-0.02"))


@pytest.mark.parametrize("years", [84, 106])
def test_the_horizon_age_is_from_85_to_105(years: int) -> None:
    with pytest.raises(ProjectionError):
        check_horizon_age(years)


def test_a_member_stops_working_before_claiming_and_after_being_born() -> None:
    check_member(_member(retirement=Month(2054, 3), pension_month=Month(2056, 3)))
    for wrong in (
        _member(retirement=Month(2054, 3), pension_month=Month(2053, 3)),
        _member(birth=Month(2054, 3), retirement=Month(2054, 3)),
        _member(earnings="-1"),
        _member(pension="1800.001"),
    ):
        with pytest.raises(ProjectionError):
            check_member(wrong)


def test_ages_are_whole_years_from_the_birth_month() -> None:
    assert age(Month(1990, 3), Month(2054, 2)) == 63
    assert age(Month(1990, 3), Month(2054, 3)) == 64


def test_the_household_retires_with_its_last_member_and_ends_with_its_youngest() -> None:
    older = _member(birth=Month(1985, 6), retirement=Month(2049, 6))
    younger = _member(birth=Month(1990, 3), retirement=Month(2054, 3))
    unborn = _member(birth=None, retirement=Month(2060, 1))
    assert counted([older, younger, unborn]) == [older, younger]
    assert household_retirement([older, younger]) == Month(2054, 3)
    assert household_retirement([]) is None
    assert horizon([older, younger], DEFAULT_HORIZON_AGE, NOW) == Month(2085, 3)
    # At most 80 years from now.
    baby = _member(birth=Month(2010, 1), retirement=Month(2074, 1))
    assert horizon([baby], 105, NOW) == Month(2106, 10)


def test_retirement_spending_is_a_share_of_spending_outside_the_loans() -> None:
    base = spending_base(D("3200"), D("950"))
    assert base == D("2250")
    assert retirement_spending(base, share=D("0.8")) == D("1800.00")
    assert retirement_spending(base, amount=D("2000")) == D("2000")
    assert spending_base(D("500"), D("950")) == 0  # loans above the measured spending


MONTHS = 12


def _plan(members: list[Member], **extra: object) -> list[Decimal]:
    args: dict[str, object] = {
        "capacity": D(1000),
        "spending": D(2000),
        "debts": [],
        "inflation": D(0),
        "indexation": D(0),
        "this_month": NOW,
        "months": MONTHS,
    } | extra
    return plan_savings(members, **args)  # type: ignore[arg-type]


def test_before_anyone_retires_the_plan_saves_the_projections_savings() -> None:
    """Invariant 37: the same savings as the projection until the first retirement."""
    loan = Debt(D(1500), DebtTerms(D(500), D(0), D(10)))
    member = _member(retirement=Month(2027, 6))
    path = _plan([member], debts=[loan], inflation=D("0.02"))
    freed = amortise(loan.owed, loan.terms, months=MONTHS).freed
    projection = savings_path(D(1000), months=MONTHS, inflation=D("0.02"), freed=freed)
    assert path[:7] == projection[:7]  # November 2026 to May 2027


def test_a_member_retiring_first_takes_their_earnings_out_and_their_pension_in() -> None:
    first = _member(retirement=Month(2027, 1), earnings="2500", pension_month=Month(2027, 3))
    second = _member(retirement=Month(2028, 1))
    path = _plan([first, second])
    # Nov, Dec: the capacity; Jan, Feb: without the earnings; from March: the pension too.
    assert path[:6] == [D(1000), D(1000), D(-1500), D(-1500), D(300), D(300)]


def test_from_the_households_retirement_pensions_pay_the_retirement_spending() -> None:
    a = _member(retirement=Month(2027, 1), pension="1500")
    b = _member(retirement=Month(2027, 1), pension_month=Month(2027, 4), pension="900")
    path = _plan([a, b], spending=D(2000))
    assert path[1] == D(1000)  # December: still the capacity
    assert path[2:6] == [D(-500), D(-500), D(-500), D(400)]  # b's pension from April


def test_a_pension_already_received_is_in_the_capacity_until_the_household_retires() -> None:
    retired = _member(retirement=Month(2020, 1), earnings="2000", pension="1200")
    worker = _member(retirement=Month(2027, 1), earnings="2500", pension="1800")
    path = _plan([retired, worker], spending=D(2500))
    assert path[:2] == [D(1000), D(1000)]  # neither the earnings lost nor the pension added
    assert path[2] == D(500)  # 1,200 + 1,800 - 2,500


def test_pensions_follow_inflation_plus_the_indexation_and_spending_inflation() -> None:
    m = _member(retirement=NOW, pension="2000")
    path = _plan([m], spending=D(1000), inflation=D("0.02"), indexation=D("-0.003"))
    t = 12
    expected = quantize(D(2000) * D("1.017") ** (D(t) / 12)) - quantize(
        D(1000) * D("1.02") ** (D(t) / 12)
    )
    assert path[t - 1] == expected


def test_once_retired_the_loans_are_spent_on_top_until_repaid_and_free_nothing() -> None:
    m = _member(retirement=Month(2026, 11), pension="2000")
    loan = Debt(D(1200), DebtTerms(D(500), D(0), D(20)))
    path = _plan([m], spending=D(1000), debts=[loan])
    # 500 + 20, 500 + 20, then the last 200 + 20, then nothing.
    assert path[:4] == [D(480), D(480), D(780), D(1000)]


@given(
    st.lists(st.integers(-24, 120), min_size=1, max_size=3),
    st.decimals(0, 5000, places=2),
)
def test_earnings_and_pensions_move_the_savings_the_right_way(
    offsets: list[int], extra: Decimal
) -> None:
    members = [_member(retirement=add_months(NOW, k)) for k in offsets]
    richer = [
        Member(m.id, m.birth, m.retirement, m.earnings, m.pension_month, m.pension + extra)
        for m in members
    ]
    base, more = _plan(members, months=150), _plan(richer, months=150)
    assert all(b <= r for b, r in zip(base, more, strict=True))


def test_the_debts_cost_their_payments_and_insurance_until_repaid() -> None:
    loans = [
        Debt(D(1200), DebtTerms(D(500), D(0), D(20))),
        Debt(D(300), DebtTerms(D(300), D(0), D(0))),
    ]
    assert debt_costs(loans, 4) == [D(820), D(520), D(220), D(0)]
