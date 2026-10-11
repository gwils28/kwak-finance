from decimal import Decimal
from uuid import UUID, uuid4

from hypothesis import given
from hypothesis import strategies as st
from kwak_core.flows import Flow, FlowKind, Side, money_flows, saved
from kwak_core.kpis import TransferLeg

D = Decimal
SALARY, OTHER_INCOME, RENT, GROCERIES = uuid4(), uuid4(), uuid4(), uuid4()


def _total(flows: list[Flow], side: Side) -> Decimal:
    return sum((f.amount for f in flows if f.side is side), D(0))


def test_income_feeds_spending_savings_and_what_is_left() -> None:
    flows = money_flows(
        income={SALARY: D("2600"), OTHER_INCOME: D("100")},
        spending={RENT: D("1150"), GROCERIES: D("300")},
        uncategorised_in=D("0"),
        uncategorised_out=D("50"),
        paid_in=D("0"),
        paid_out=D("400"),
        saved=D("500"),
    )
    assert flows == [
        Flow(FlowKind.INCOME, Side.IN, D("2600"), SALARY),
        Flow(FlowKind.INCOME, Side.IN, D("100"), OTHER_INCOME),
        Flow(FlowKind.SPENDING, Side.OUT, D("1150"), RENT),
        Flow(FlowKind.SPENDING, Side.OUT, D("300"), GROCERIES),
        Flow(FlowKind.UNCATEGORISED, Side.OUT, D("50")),
        Flow(FlowKind.PAID_OUT, Side.OUT, D("400")),
        Flow(FlowKind.SAVED, Side.OUT, D("500")),
        Flow(FlowKind.UNALLOCATED, Side.OUT, D("300")),
    ]


def test_a_deficit_and_money_taken_from_savings_come_in_on_the_left() -> None:
    flows = money_flows(
        income={SALARY: D("1000")},
        spending={RENT: D("1150")},
        uncategorised_in=D("20"),
        uncategorised_out=D("0"),
        paid_in=D("100"),
        paid_out=D("0"),
        saved=D("-200"),
    )
    left = [(f.kind, f.amount) for f in flows if f.side is Side.IN]
    assert left == [
        (FlowKind.INCOME, D("1000")),
        (FlowKind.UNCATEGORISED, D("20")),
        (FlowKind.PAID_IN, D("100")),
        (FlowKind.FROM_SAVINGS, D("200")),
    ]
    assert Flow(FlowKind.UNALLOCATED, Side.OUT, D("170")) in flows


def test_a_category_netting_the_wrong_way_crosses_over() -> None:
    flows = money_flows(
        income={SALARY: D("-30")},  # a reversed salary, nothing else
        spending={RENT: D("-80")},  # a refund larger than the spending
        uncategorised_in=D("0"),
        uncategorised_out=D("0"),
        paid_in=D("0"),
        paid_out=D("0"),
        saved=D("0"),
    )
    assert Flow(FlowKind.INCOME, Side.OUT, D("30"), SALARY) in flows
    assert Flow(FlowKind.SPENDING, Side.IN, D("80"), RENT) in flows
    assert Flow(FlowKind.UNALLOCATED, Side.OUT, D("50")) in flows


amounts = st.decimals(min_value=D("-5000"), max_value=D("5000"), places=2)
positive = st.decimals(min_value=D("0"), max_value=D("5000"), places=2)


@given(
    st.dictionaries(st.sampled_from([SALARY, OTHER_INCOME]), amounts),
    st.dictionaries(st.sampled_from([RENT, GROCERIES]), amounts),
    positive,
    positive,
    positive,
    positive,
    amounts,
)
def test_what_comes_in_always_equals_what_goes_out(
    income: dict[UUID, Decimal],
    spending: dict[UUID, Decimal],
    uncategorised_in: Decimal,
    uncategorised_out: Decimal,
    paid_in: Decimal,
    paid_out: Decimal,
    saved_amount: Decimal,
) -> None:
    flows = money_flows(
        income=income,
        spending=spending,
        uncategorised_in=uncategorised_in,
        uncategorised_out=uncategorised_out,
        paid_in=paid_in,
        paid_out=paid_out,
        saved=saved_amount,
    )
    assert _total(flows, Side.IN) == _total(flows, Side.OUT)
    assert all(f.amount > 0 for f in flows)


CHECKING, LIVRET, LDDS, OUTSIDE = uuid4(), uuid4(), uuid4(), uuid4()


def _transfer(source: UUID, target: UUID, amount: str) -> list[TransferLeg]:
    group = uuid4()
    return [TransferLeg(group, source, -D(amount)), TransferLeg(group, target, D(amount))]


def test_saved_is_what_moved_from_spending_accounts_to_savings_ones() -> None:
    legs = (
        _transfer(CHECKING, LIVRET, "500")
        + _transfer(LIVRET, CHECKING, "120")
        + _transfer(LIVRET, LDDS, "1000")  # savings to savings: nothing newly saved
        + _transfer(OUTSIDE, LIVRET, "300")  # paid in from outside the scope, counted there
    )
    scope = {CHECKING, LIVRET, LDDS}
    assert saved(legs, scope, savings={LIVRET, LDDS}) == D("380")
