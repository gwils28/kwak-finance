"""The cash-flow forecast read from a household (spec §4.14), on the demo's three years of
fictitious data (F-ADM-5)."""

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from kwak_api.models import SpendingLine, User
from kwak_api.services import demo, forecast, spending
from kwak_core.budget import Month
from kwak_core.categories import CategoryKind
from kwak_core.demo import generate
from kwak_core.forecast import HORIZON
from kwak_core.users import Language
from sqlalchemy.orm import Session

D = Decimal
TODAY = date(2026, 10, 28)
NOW = datetime(2026, 10, 28, 9, tzinfo=UTC)


@pytest.fixture
def demo_owner(session: Session) -> User:
    return demo.build(session, generate(TODAY, Language.EN), NOW)


@pytest.fixture
def result(session: Session, demo_owner: User) -> forecast.Result:
    return forecast.compute(session, demo_owner.household_id, TODAY)


def test_the_demo_is_forecast_from_its_last_complete_month(result: forecast.Result) -> None:
    assert result.origin == Month(2026, 9)
    assert result.ahead[0] == Month(2026, 10)
    assert len(result.ahead) == HORIZON
    assert len(result.history) == 36


def test_every_category_has_twelve_bands(result: forecast.Result) -> None:
    for c in result.categories:
        bands = result.forecast.categories[c.id].bands
        assert len(bands) == HORIZON
        assert all(b.low <= b.point <= b.high for b in bands)


def test_the_totals_add_up(result: forecast.Result) -> None:
    """Invariant §8.42."""
    f = result.forecast
    for k in range(HORIZON):
        by_kind: dict[CategoryKind, Decimal] = {kind: D(0) for kind in CategoryKind}
        for c in result.categories:
            by_kind[c.kind] += f.categories[c.id].bands[k].point
        assert f.income[k].point == by_kind[CategoryKind.INCOME]
        assert f.spent[k].point == by_kind[CategoryKind.EXPENSE]
        assert f.saved[k].point == by_kind[CategoryKind.SAVINGS]
        assert f.rest[k].point == f.income[k].point - f.spent[k].point - f.saved[k].point


def test_the_salaries_are_forecast_close_to_what_they_were(
    session: Session, result: forecast.Result
) -> None:
    income = result.forecast.income[0]
    assert D(4000) < income.point < D(9000)
    assert income.low < income.high


def test_the_fixed_expenses_are_known(
    session: Session, demo_owner: User, result: forecast.Result
) -> None:
    """The mortgage is due every month: its category's known part is its amount."""
    items = spending.fixed_expenses(session, demo_owner.household_id)
    mortgage = next(i for i in items if i.label == "Mortgage")
    known = result.forecast.categories[mortgage.category_id].known
    assert all(k >= -mortgage.amount for k in known)


def test_the_lines_of_this_month_are_not_used(
    session: Session, demo_owner: User, result: forecast.Result
) -> None:
    """Invariant §8.41: a line entered this month changes what is entered, not the forecast."""
    groceries = next(c for c in result.categories if c.name == "Groceries")
    session.add(
        SpendingLine(
            household_id=demo_owner.household_id,
            day=TODAY,
            label="Huge shop",
            amount=D("-5000"),
            category_id=groceries.id,
            entered_by_id=demo_owner.id,
            created_at=NOW,
        )
    )
    session.flush()
    again = forecast.compute(session, demo_owner.household_id, TODAY)
    assert again.forecast == result.forecast
    assert again.entered[groceries.id] == result.entered[groceries.id] + D(5000)


def test_the_forecast_is_reproducible(
    session: Session, demo_owner: User, result: forecast.Result
) -> None:
    forecast._cache.clear()
    assert forecast.compute(session, demo_owner.household_id, TODAY).forecast == result.forecast


def test_a_new_household_has_not_enough_history(session: Session, owner: User) -> None:
    with pytest.raises(forecast.NotEnoughHistoryError) as caught:
        forecast.compute(session, owner.household_id, TODAY)
    assert caught.value.months == 0


def test_another_household_s_lines_are_never_read(
    session: Session, owner: User, demo_owner: User
) -> None:
    """The real household and the demo never meet (invariant §8.40)."""
    with pytest.raises(forecast.NotEnoughHistoryError):
        forecast.compute(session, owner.household_id, TODAY)
