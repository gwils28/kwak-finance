"""Retirement's data (spec §4.13 F-RET-1, 2): each member's months and amounts, and the
household's settings."""

from datetime import date
from decimal import Decimal

import pytest
from kwak_api.models import Household, MemberRetirement, Role, User
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


@pytest.fixture
def user(session: Session) -> User:
    member = User(
        household=Household(name="Home"),
        email="m@example.com",
        display_name="M",
        password_hash="$argon2id$placeholder",
        role=Role.OWNER,
    )
    session.add(member)
    session.flush()
    return member


def _plan(session: Session, user: User, **fields: object) -> MemberRetirement:
    values: dict[str, object] = {
        "birth": date(1990, 3, 1),
        "retirement": date(2054, 3, 1),
        "earnings": Decimal(2500),
        "pension_month": date(2054, 3, 1),
        "pension": Decimal(1800),
    } | fields
    plan = MemberRetirement(user_id=user.id, **values)
    session.add(plan)
    session.flush()
    return plan


def test_a_member_has_one_retirement(session: Session, user: User) -> None:
    _plan(session, user)
    with pytest.raises(IntegrityError, match="uq_member_retirement_user_id"):
        _plan(session, user)


@pytest.mark.parametrize(
    ("fields", "name"),
    [
        ({"birth": date(1990, 3, 2)}, "ck_member_retirement_birth_month"),
        ({"pension_month": date(2054, 2, 1)}, "ck_member_retirement_pension_after_retirement"),
        ({"birth": date(2054, 3, 1)}, "ck_member_retirement_born_before"),
        ({"earnings": Decimal(-1)}, "ck_member_retirement_earnings_positive"),
        ({"pension": Decimal(-1)}, "ck_member_retirement_pension_positive"),
    ],
)
def test_a_retirement_is_consistent(
    session: Session, user: User, fields: dict[str, object], name: str
) -> None:
    with pytest.raises(IntegrityError, match=name):
        _plan(session, user, **fields)


def test_the_household_starts_with_the_defaults(session: Session, user: User) -> None:
    household = user.household
    session.refresh(household)
    assert (
        household.retirement_share,
        household.retirement_spending,
        household.pension_indexation,
        household.horizon_age,
    ) == (None, None, None, None)


@pytest.mark.parametrize(
    ("fields", "name"),
    [
        ({"retirement_share": Decimal("1.51")}, "ck_household_retirement_share_range"),
        ({"pension_indexation": Decimal("0.011")}, "ck_household_pension_indexation_range"),
        ({"horizon_age": 106}, "ck_household_horizon_age_range"),
        (
            {"retirement_share": Decimal("0.8"), "retirement_spending": Decimal(3000)},
            "ck_household_retirement_share_or_amount",
        ),
    ],
)
def test_the_households_settings_stay_within_bounds(
    session: Session, user: User, fields: dict[str, object], name: str
) -> None:
    for key, value in fields.items():
        setattr(user.household, key, value)
    with pytest.raises(IntegrityError, match=name):
        session.flush()
