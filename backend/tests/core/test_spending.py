from datetime import date
from decimal import Decimal
from itertools import pairwise
from uuid import uuid4

import pytest
from hypothesis import given
from hypothesis import strategies as st
from kwak_core.categories import CategoryKind
from kwak_core.spending import MonthFigures, Piece, month_figures

D = Decimal
GROCERIES, HOME, SAVINGS, SALARY, REFUNDS = uuid4(), uuid4(), uuid4(), uuid4(), uuid4()
KINDS = {
    GROCERIES: CategoryKind.EXPENSE,
    HOME: CategoryKind.EXPENSE,
    SAVINGS: CategoryKind.SAVINGS,
    SALARY: CategoryKind.INCOME,
    REFUNDS: CategoryKind.INCOME,
}


def test_spent_saved_rest_and_savings_rate() -> None:
    pieces = [
        Piece(SALARY, D("1900.00")),
        Piece(REFUNDS, D("100.00")),
        Piece(GROCERIES, D("-300.00")),
        Piece(HOME, D("-200.00")),
        Piece(SAVINGS, D("-600.00")),
        Piece(SAVINGS, D("100.00")),  # taken back from savings
    ]
    figures = month_figures(pieces, KINDS)
    assert figures == MonthFigures(income=D("2000.00"), spent=D("500.00"), saved=D("500.00"))
    assert figures.rest == D("1000.00")
    assert figures.savings_rate == D("0.75")


def test_no_income_no_savings_rate() -> None:
    assert month_figures([Piece(HOME, D("-5.00"))], KINDS).savings_rate is None


def test_figures_add_up_over_months() -> None:
    a = MonthFigures(D("10.00"), D("3.00"), D("1.00"))
    b = MonthFigures(D("20.00"), D("5.00"), D("2.00"))
    assert a + b == MonthFigures(D("30.00"), D("8.00"), D("3.00"))
    assert sum([a, b], MonthFigures.zero()) == a + b


amounts = st.decimals(min_value=-5000, max_value=5000, places=2)


@given(
    st.lists(
        st.tuples(st.sampled_from([GROCERIES, HOME, SAVINGS, SALARY, REFUNDS]), amounts),
        max_size=12,
    ),
)
def test_invariant_14_savings_are_never_spending(raw: list[tuple[object, Decimal]]) -> None:
    pieces = [Piece(c, a) for c, a in raw]  # type: ignore[arg-type]
    figures = month_figures(pieces, KINDS)
    assert figures.rest == sum((p.amount for p in pieces), D(0))

    def of(kind: CategoryKind) -> Decimal:
        return sum((p.amount for p in pieces if KINDS[p.category_id] is kind), D(0))

    assert figures.income == of(CategoryKind.INCOME)
    assert figures.spent == -of(CategoryKind.EXPENSE)


def test_spending_adds_up_day_by_day_over_the_whole_month() -> None:
    from datetime import date

    from kwak_core.budget import Month
    from kwak_core.spending import cumulative_by_day

    days = cumulative_by_day(
        {date(2026, 2, 3): D("10.00"), date(2026, 2, 10): D("5.50")}, Month(2026, 2)
    )
    assert len(days) == 28
    assert days[0] == (date(2026, 2, 1), D(0))
    assert days[2] == (date(2026, 2, 3), D("10.00"))
    assert days[9] == (date(2026, 2, 10), D("15.50"))
    assert days[-1] == (date(2026, 2, 28), D("15.50"))


@given(
    st.dictionaries(
        st.integers(min_value=1, max_value=30).map(lambda d: date(2026, 4, d)),
        st.decimals(min_value=0, max_value=5000, places=2),
        max_size=10,
    )
)
def test_every_day_of_the_month_once_ending_on_the_month_total(spent: dict[date, Decimal]) -> None:
    from kwak_core.budget import Month
    from kwak_core.spending import cumulative_by_day

    days = cumulative_by_day(spent, Month(2026, 4))
    assert [d for d, _ in days] == [date(2026, 4, n) for n in range(1, 31)]
    assert days[-1][1] == sum(spent.values(), D(0))
    assert all(a[1] <= b[1] for a, b in pairwise(days))


def test_a_line_is_income_or_spending_never_both() -> None:
    from kwak_core.spending import LineKindError, check_line_kinds

    expense, savings, income = CategoryKind.EXPENSE, CategoryKind.SAVINGS, CategoryKind.INCOME
    check_line_kinds(D("-10.00"), {expense, savings})
    check_line_kinds(D("10.00"), {savings})
    check_line_kinds(D("2500.00"), {income})
    refused = ((D("10.00"), {expense}), (D("-10.00"), {income}), (D("10.00"), {income, savings}))
    for amount, kinds in refused:
        with pytest.raises(LineKindError):
            check_line_kinds(amount, kinds)


@given(
    amounts.filter(lambda a: a != 0),
    st.sets(st.sampled_from(list(CategoryKind)), min_size=1),
)
def test_an_accepted_line_flows_the_way_its_kinds_say(
    amount: Decimal, kinds: set[CategoryKind]
) -> None:
    from kwak_core.spending import LineKindError, check_line_kinds

    try:
        check_line_kinds(amount, kinds)
    except LineKindError:
        return
    assert CategoryKind.INCOME not in kinds or (kinds == {CategoryKind.INCOME} and amount > 0)
    assert CategoryKind.EXPENSE not in kinds or amount < 0


def test_a_typed_amount_is_stored_negative_unless_it_is_an_income() -> None:
    from kwak_core.spending import stored_amount

    assert stored_amount(D("12.50"), CategoryKind.EXPENSE) == D("-12.50")
    assert stored_amount(D("-200.00"), CategoryKind.SAVINGS) == D("200.00")
    assert stored_amount(D("2500.00"), CategoryKind.INCOME) == D("2500.00")
    assert stored_amount(D("8.00"), None) == D("-8.00")
