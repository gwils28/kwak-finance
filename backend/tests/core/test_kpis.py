from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from hypothesis import given
from hypothesis import strategies as st
from kwak_core.categories import CategoryKind
from kwak_core.kpis import (
    Flow,
    MonthFigures,
    TransferLeg,
    change,
    crossing,
    cumulative_by_day,
    month_figures,
    savings_rate,
    top_categories,
)

D = Decimal
FOOD, GROCERIES, HOUSING, SALARY, PEA = uuid4(), uuid4(), uuid4(), uuid4(), uuid4()
KINDS = {
    FOOD: CategoryKind.EXPENSE,
    GROCERIES: CategoryKind.EXPENSE,
    HOUSING: CategoryKind.EXPENSE,
    SALARY: CategoryKind.INCOME,
    PEA: CategoryKind.SAVINGS,
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


def test_savings_categories_are_saved_not_spent() -> None:
    flows = [
        Flow(SALARY, D("2500")),
        Flow(GROCERIES, D("-300")),
        Flow(PEA, D("-500")),
        Flow(PEA, D("100")),  # a withdrawal brought back counts against it
    ]
    figures = month_figures(flows, KINDS)
    assert (figures.spent, figures.income, figures.saved) == (D("300"), D("2500"), D("400"))
    # The money put in the PEA is kept, not spent: it stays in the net cash flow.
    assert figures.net == D("2200")
    assert savings_rate(figures.inflow, figures.net) == D("0.88")


@given(
    st.lists(
        st.tuples(st.sampled_from([FOOD, GROCERIES, HOUSING, SALARY, None]), amounts), max_size=40
    )
)
def test_net_is_the_sum_of_the_months_transactions(raw: list[tuple[object, Decimal]]) -> None:
    flows = [Flow(c, a) for c, a in raw]  # type: ignore[arg-type]
    assert month_figures(flows, KINDS).net == sum((a for _, a in raw), Decimal(0))


@given(
    st.lists(st.tuples(st.sampled_from([FOOD, GROCERIES, SALARY, PEA, None]), amounts), max_size=40)
)
def test_invariant_14_savings_categories_are_neither_spending_nor_income(
    raw: list[tuple[object, Decimal]],
) -> None:
    flows = [Flow(c, a) for c, a in raw]  # type: ignore[arg-type]
    figures = month_figures(flows, KINDS)
    without_savings = month_figures([f for f in flows if f.category_id != PEA], KINDS)
    assert (figures.spent, figures.income) == (without_savings.spent, without_savings.income)
    assert figures.net == sum((a for _, a in raw), Decimal(0)) + figures.saved


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


PERSONAL, JOINT, PARTNER = uuid4(), uuid4(), uuid4()


def _transfer(source: UUID, target: UUID, amount: str) -> list[TransferLeg]:
    group = uuid4()
    return [TransferLeg(group, source, -D(amount)), TransferLeg(group, target, D(amount))]


def test_a_transfer_into_the_scope_is_paid_in_and_one_out_of_it_paid_out() -> None:
    legs = _transfer(PERSONAL, JOINT, "1100") + _transfer(JOINT, PARTNER, "50")

    assert crossing(legs, {JOINT}) == (D("1100"), D("50"))
    assert crossing(legs, {PERSONAL}) == (D(0), D("1100"))


def test_a_transfer_within_the_scope_crosses_nothing() -> None:
    assert crossing(_transfer(PERSONAL, JOINT, "1100"), {PERSONAL, JOINT}) == (D(0), D(0))


def test_paid_in_counts_with_income_and_paid_out_with_spending() -> None:
    figures = MonthFigures(spent=D("141"), income=D("2600"), paid_out=D("1100"))
    assert figures.net == D("1359")
    assert figures.inflow == D("2600")

    joint = MonthFigures(spent=D("2151"), income=D("1300"), paid_in=D("1100"))
    assert joint.net == D("249")
    assert joint.inflow == D("2400")


ACCOUNTS = [PERSONAL, JOINT, PARTNER, uuid4()]
transfers = st.lists(
    st.tuples(
        st.sampled_from(ACCOUNTS),
        st.sampled_from(ACCOUNTS),
        st.decimals(min_value=D("0.01"), max_value=D("10000"), places=2),
    ).filter(lambda t: t[0] != t[1]),
    max_size=10,
)


@given(transfers, st.sets(st.sampled_from(ACCOUNTS)))
def test_what_leaves_some_accounts_reaches_the_others(
    raw: list[tuple[UUID, UUID, Decimal]], scope: set[UUID]
) -> None:
    legs = [leg for source, target, amount in raw for leg in _transfer(source, target, str(amount))]
    rest = set(ACCOUNTS) - scope

    paid_in, paid_out = crossing(legs, scope)
    other_in, other_out = crossing(legs, rest)

    assert (paid_in, paid_out) == (other_out, other_in)
    assert crossing(legs, set(ACCOUNTS)) == (D(0), D(0))
