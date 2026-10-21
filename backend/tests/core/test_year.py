from datetime import date
from decimal import Decimal
from uuid import uuid4

from hypothesis import given
from hypothesis import strategies as st
from kwak_core.budget import BudgetStatus, Month, month_range, target_for
from kwak_core.year import months_to_date, year_lines

D = Decimal
GROCERIES, HOME, SAVINGS = uuid4(), uuid4(), uuid4()
TODAY = date(2026, 3, 10)


def m(month: int, year: int = 2026) -> Month:
    return Month(year, month)


def test_months_to_date() -> None:
    assert months_to_date(2026, TODAY) == [m(1), m(2), m(3)]
    assert months_to_date(2025, TODAY) == month_range(m(1, 2025), m(12, 2025))
    assert months_to_date(2027, TODAY) == []


def test_a_year_to_date_with_a_target_changed_in_february() -> None:
    targets = {GROCERIES: [(m(11, 2025), D("400.00")), (m(2), D("500.00"))]}
    spending = {(GROCERIES, m(1)): D("370.00"), (GROCERIES, m(2)): D("620.00")}
    spending[(GROCERIES, m(3))] = D("100.00")  # the running month
    (line,) = year_lines(2026, TODAY, [GROCERIES], targets, spending)
    assert line.target_to_date == D("1400.00")  # 400 + 500 + 500, March in full
    assert line.target_full == D("5900.00")  # 400 + 11 x 500
    assert line.spent_to_date == D("1090.00")
    assert line.gap == D("-310.00")
    assert line.status is BudgetStatus.UNDER
    # completed months only: January under (-7.5 %), February over
    assert (line.above, line.on, line.below) == (1, 0, 1)


def test_a_category_without_target_has_no_status() -> None:
    (line,) = year_lines(2026, TODAY, [HOME], {}, {(HOME, m(1)): D("40.00")})
    assert (line.target_to_date, line.target_full, line.status) == (None, None, BudgetStatus.NONE)
    assert line.spent_to_date == D("40.00")


def test_a_savings_objective_is_a_minimum() -> None:
    targets = {SAVINGS: [(m(1, 2025), D("300.00"))]}
    spending = {
        (SAVINGS, m(1, 2025)): D("500.00"),
        (SAVINGS, m(2, 2025)): D("500.00"),
        (SAVINGS, m(1)): D("450.00"),
        (SAVINGS, m(2)): D("480.00"),
    }
    (line,) = year_lines(2025, TODAY, [SAVINGS], targets, spending, minimum=True)
    assert line.status is BudgetStatus.BEHIND  # 1000 saved against 3600 over the past year
    (line,) = year_lines(2026, TODAY, [SAVINGS], targets, spending, minimum=True)
    assert line.status is BudgetStatus.ON  # 930 against 900
    assert (line.above, line.on, line.below) == (2, 0, 0)  # both completed months ahead


history = st.lists(
    st.tuples(
        st.builds(Month, st.integers(2025, 2026), st.integers(1, 12)),
        st.none() | st.decimals(min_value=0, max_value=1000, places=2),
    ),
    max_size=5,
)


@given(history, st.integers(1, 12))
def test_invariants_8_and_9_targets_add_up_month_by_month(
    targets: list[tuple[Month, Decimal | None]], today_month: int
) -> None:
    today = date(2026, today_month, 1)
    (line,) = year_lines(2026, today, [GROCERIES], {GROCERIES: targets}, {})
    in_force: list[Decimal | None] = [target_for(targets, m(k)) for k in range(1, 13)]
    to_date = [t for t in in_force[:today_month] if t is not None]
    full = [t for t in in_force if t is not None]
    assert line.target_to_date == (sum(to_date, D(0)) if to_date else None)
    assert line.target_full == (sum(full, D(0)) if full else None)
