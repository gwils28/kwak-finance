from decimal import Decimal
from uuid import uuid4

from hypothesis import given
from hypothesis import strategies as st
from kwak_core.categories import CategoryKind
from kwak_core.spending import MonthFigures, Piece, month_figures

D = Decimal
GROCERIES, HOME, SAVINGS = uuid4(), uuid4(), uuid4()
KINDS = {GROCERIES: CategoryKind.EXPENSE, HOME: CategoryKind.EXPENSE, SAVINGS: CategoryKind.SAVINGS}


def test_spent_saved_rest_and_savings_rate() -> None:
    pieces = [
        Piece(GROCERIES, D("-300.00")),
        Piece(HOME, D("-200.00")),
        Piece(SAVINGS, D("-600.00")),
        Piece(SAVINGS, D("100.00")),  # taken back from savings
    ]
    figures = month_figures(D("2000.00"), pieces, KINDS)
    assert figures == MonthFigures(income=D("2000.00"), spent=D("500.00"), saved=D("500.00"))
    assert figures.rest == D("1000.00")
    assert figures.savings_rate == D("0.75")


def test_no_income_no_savings_rate() -> None:
    assert month_figures(D(0), [Piece(HOME, D("-5.00"))], KINDS).savings_rate is None


def test_figures_add_up_over_months() -> None:
    a = MonthFigures(D("10.00"), D("3.00"), D("1.00"))
    b = MonthFigures(D("20.00"), D("5.00"), D("2.00"))
    assert a + b == MonthFigures(D("30.00"), D("8.00"), D("3.00"))
    assert sum([a, b], MonthFigures.zero()) == a + b


amounts = st.decimals(min_value=-5000, max_value=5000, places=2)


@given(
    st.decimals(min_value=0, max_value=10000, places=2),
    st.lists(st.tuples(st.sampled_from([GROCERIES, HOME, SAVINGS]), amounts), max_size=12),
)
def test_invariant_14_savings_are_never_spending(
    income: Decimal, raw: list[tuple[object, Decimal]]
) -> None:
    pieces = [Piece(c, a) for c, a in raw]  # type: ignore[arg-type]
    figures = month_figures(income, pieces, KINDS)
    assert figures.rest == income + sum((p.amount for p in pieces), D(0))
    expenses = [p.amount for p in pieces if KINDS[p.category_id] is CategoryKind.EXPENSE]
    assert figures.spent == -sum(expenses, D(0))
