from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from hypothesis import given
from hypothesis import strategies as st
from kwak_core.categories import CategoryKind
from kwak_core.kpis import (
    Flow,
    change,
    cumulative_by_day,
    month_figures,
    savings_rate,
    top_categories,
)

D = Decimal
FOOD, GROCERIES, HOUSING, SALARY = uuid4(), uuid4(), uuid4(), uuid4()
KINDS = {
    FOOD: CategoryKind.EXPENSE,
    GROCERIES: CategoryKind.EXPENSE,
    HOUSING: CategoryKind.EXPENSE,
    SALARY: CategoryKind.INCOME,
}


def test_spending_and_income_follow_the_category_kind_and_sign_for_the_rest() -> None:
    flows = [
        Flow(GROCERIES, D("-300")),
        Flow(GROCERIES, D("20")),  # a refund lowers spending
        Flow(SALARY, D("2500")),
        Flow(None, D("-40")),  # to categorise: an outflow is spending...
        Flow(None, D("15")),  # ...and an inflow is income
    ]
    figures = month_figures(flows, KINDS)
    assert (figures.spent, figures.income) == (D("320"), D("2515"))
    assert figures.net == D("2195")


amounts = st.integers(min_value=-1_000_00, max_value=1_000_00).map(lambda c: Decimal(c) / 100)


@given(
    st.lists(
        st.tuples(st.sampled_from([FOOD, GROCERIES, HOUSING, SALARY, None]), amounts), max_size=40
    )
)
def test_net_is_the_sum_of_the_months_transactions(raw: list[tuple[object, Decimal]]) -> None:
    flows = [Flow(c, a) for c, a in raw]  # type: ignore[arg-type]
    assert month_figures(flows, KINDS).net == sum((a for _, a in raw), Decimal(0))


@pytest.mark.parametrize(
    ("income", "net", "rate"),
    [("2000", "500", D("0.25")), ("2000", "-100", D("-0.05")), ("0", "-100", None)],
)
def test_savings_rate(income: str, net: str, rate: Decimal | None) -> None:
    assert savings_rate(D(income), D(net)) == rate


def test_change_is_relative_and_undefined_from_zero() -> None:
    assert change(D("110"), D("100")) == D("0.1")
    assert change(D("90"), D("100")) == D("-0.1")
    assert change(D("10"), D("0")) is None


def test_top_categories_roll_subcategories_up_and_give_their_share() -> None:
    spending = {FOOD: D("10"), GROCERIES: D("290"), HOUSING: D("700")}
    parents = {GROCERIES: FOOD}
    top = top_categories(spending, parents, total=D("1000"), limit=5)
    assert [(t.category_id, t.spent, t.share) for t in top] == [
        (HOUSING, D("700"), D("0.7")),
        (FOOD, D("300"), D("0.3")),
    ]


def test_top_categories_are_limited() -> None:
    spending = {uuid4(): D(i) for i in range(1, 9)}
    assert len(top_categories(spending, {}, total=D("36"), limit=5)) == 5


def test_cumulative_spending_by_day_covers_every_day_of_the_month() -> None:
    daily = {date(2026, 2, 3): D("10"), date(2026, 2, 10): D("5")}
    series = cumulative_by_day(2026, 2, daily)
    assert len(series) == 28
    assert series[0] == (date(2026, 2, 1), D("0"))
    assert series[2] == (date(2026, 2, 3), D("10"))
    assert series[-1] == (date(2026, 2, 28), D("15"))
