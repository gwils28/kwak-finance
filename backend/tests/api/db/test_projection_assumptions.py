"""The projection's assumptions, saved per household (spec §4.11 F-SIM-1)."""

from decimal import Decimal

import pytest
from kwak_api.models import Household, Role, User, WealthCategory, WealthLine
from kwak_core.visibility import Visibility
from kwak_core.wealth import WealthKind
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


@pytest.fixture
def household(session: Session) -> Household:
    household = Household(name="Home")
    session.add(household)
    session.flush()
    return household


def _category(session: Session, household: Household, **fields: object) -> WealthCategory:
    category = WealthCategory(
        household_id=household.id,
        name="Stocks",
        kind=WealthKind.ASSET,
        colour="stocks",
        position=0,
        **fields,
    )
    session.add(category)
    session.flush()
    return category


def test_a_household_starts_with_the_default_assumptions(
    session: Session, household: Household
) -> None:
    category = _category(session, household)
    session.refresh(household)
    assert household.inflation is None
    assert (category.expected_return, category.volatility) == (None, None)


def test_a_category_sets_its_return_and_volatility_together(
    session: Session, household: Household
) -> None:
    with pytest.raises(IntegrityError, match="ck_wealth_category_assumption_whole"):
        _category(session, household, expected_return=Decimal("0.065"))


@pytest.mark.parametrize(
    ("ret", "volatility"),
    [(Decimal(-1), Decimal(0)), (Decimal("1.001"), Decimal(0)), (Decimal(0), Decimal("2.001"))],
)
def test_a_categorys_assumption_stays_within_bounds(
    session: Session, household: Household, ret: Decimal, volatility: Decimal
) -> None:
    with pytest.raises(IntegrityError, match="ck_wealth_category_assumption_range"):
        _category(session, household, expected_return=ret, volatility=volatility)


def test_the_inflation_stays_within_bounds(session: Session, household: Household) -> None:
    household.inflation = Decimal("0.201")
    with pytest.raises(IntegrityError, match="ck_household_inflation_range"):
        session.flush()


def _debt(session: Session, household: Household, **fields: object) -> WealthLine:
    owner = User(
        household=household,
        email="o@example.com",
        display_name="O",
        password_hash="$argon2id$placeholder",
        role=Role.OWNER,
    )
    category = _category(session, household)
    line = WealthLine(
        household_id=household.id,
        category_id=category.id,
        name="Prêt",
        owner=owner,
        visibility=Visibility.SHARED,
        **fields,
    )
    session.add(line)
    session.flush()
    return line


def test_a_debt_line_has_no_payment_until_one_is_set(
    session: Session, household: Household
) -> None:
    line = _debt(session, household)
    session.refresh(line)
    assert (line.debt_payment, line.debt_rate, line.debt_insurance) == (None, 0, 0)


@pytest.mark.parametrize(
    ("fields", "name"),
    [
        ({"debt_payment": Decimal(-1)}, "ck_wealth_line_debt_payment_positive"),
        ({"debt_rate": Decimal("1.0001")}, "ck_wealth_line_debt_rate_range"),
        ({"debt_insurance": Decimal(-1)}, "ck_wealth_line_debt_insurance_positive"),
    ],
)
def test_debt_terms_stay_within_bounds(
    session: Session, household: Household, fields: dict[str, object], name: str
) -> None:
    with pytest.raises(IntegrityError, match=name):
        _debt(session, household, **fields)
