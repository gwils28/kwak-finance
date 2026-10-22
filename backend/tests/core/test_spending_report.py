from decimal import Decimal
from uuid import uuid4

from hypothesis import given
from hypothesis import strategies as st
from kwak_core.budget import Month
from kwak_core.spending_report import (
    Flow,
    FlowKind,
    Side,
    overspent,
    period_lines,
    report_flows,
)

D = Decimal
GROCERIES, HOME, LEISURE = uuid4(), uuid4(), uuid4()
OCT, NOV, DEC = Month(2026, 10), Month(2026, 11), Month(2026, 12)


def test_flows_go_from_income_to_spending_savings_and_the_rest() -> None:
    flows = report_flows(
        income=D("3000.00"),
        spent={GROCERIES: D("400.00"), HOME: D("100.00")},
        saved=D("500.00"),
        over={HOME},
    )
    assert flows == [
        Flow(FlowKind.INCOME, Side.IN, D("3000.00")),
        Flow(FlowKind.SPENDING, Side.OUT, D("400.00"), GROCERIES),
        Flow(FlowKind.SPENDING, Side.OUT, D("100.00"), HOME, over=True),
        Flow(FlowKind.SAVED, Side.OUT, D("500.00")),
        Flow(FlowKind.UNALLOCATED, Side.OUT, D("2000.00")),
    ]


def test_a_shortfall_comes_in_as_a_deficit_and_a_withdrawal_as_taken_from_savings() -> None:
    flows = report_flows(
        income=D("1000.00"), spent={GROCERIES: D("1500.00")}, saved=D("-200.00"), over=set()
    )
    assert Flow(FlowKind.FROM_SAVINGS, Side.IN, D("200.00")) in flows
    assert flows[-1] == Flow(FlowKind.DEFICIT, Side.IN, D("300.00"))


def test_nothing_flows_from_nothing() -> None:
    assert report_flows(income=D(0), spent={GROCERIES: D(0)}, saved=D(0), over=set()) == []


amounts = st.decimals(min_value=0, max_value=50_000, places=2)


@given(
    income=amounts,
    spent=st.lists(amounts, max_size=5),
    saved=st.decimals(min_value=-5000, max_value=5000, places=2),
)
def test_flows_balance(income: Decimal, spent: list[Decimal], saved: Decimal) -> None:
    """Invariant 13: what comes in equals what goes out, every flow positive."""
    flows = report_flows(income=income, spent={uuid4(): s for s in spent}, saved=saved, over=set())
    total_in = sum((f.amount for f in flows if f.side is Side.IN), D(0))
    total_out = sum((f.amount for f in flows if f.side is Side.OUT), D(0))
    assert total_in == total_out
    assert all(f.amount > 0 for f in flows)


def test_period_lines_rank_the_largest_first_and_leave_out_the_empty() -> None:
    lines = period_lines(
        {GROCERIES: D("400.00"), HOME: D("100.00"), LEISURE: D(0)},
        {HOME: D("150.00"), LEISURE: D(0)},
    )
    assert lines == [(GROCERIES, D("400.00"), D(0)), (HOME, D("100.00"), D("150.00"))]


def test_a_category_is_overspent_against_the_targets_of_its_months_with_one() -> None:
    spending = {
        (GROCERIES, OCT): D("120.00"),
        (GROCERIES, NOV): D("90.00"),
        # December has no target: its spending is not judged.
        (GROCERIES, DEC): D("500.00"),
        (HOME, OCT): D("100.00"),
        (LEISURE, OCT): D("80.00"),
    }
    targets = {
        GROCERIES: [(OCT, D("100.00")), (DEC, None)],
        HOME: [(OCT, D("100.00"))],
    }
    assert overspent(spending, targets, [OCT, NOV, DEC]) == {GROCERIES}
    # Within its target, or without one, a category is not overspent.
    assert overspent(spending, targets, [OCT]) == {GROCERIES}
    assert overspent({(HOME, OCT): D("100.00")}, targets, [OCT]) == set()
