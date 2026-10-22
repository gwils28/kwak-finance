from datetime import date
from decimal import Decimal

import pytest
from kwak_api.models import Goal, Household, Role, User
from kwak_core.visibility import Visibility
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


def _rum(session: Session, **fields: object) -> Goal:
    household = Household(name="Home")
    owner = User(
        household=household,
        email="owner@example.com",
        display_name="Owner",
        password_hash="$argon2id$placeholder",
        role=Role.OWNER,
    )
    session.add(owner)
    session.flush()
    return Goal(
        household_id=household.id,
        name="Rhum",
        target=Decimal("120.00"),
        start=date(2026, 10, 1),
        owner_id=owner.id,
        visibility=Visibility.SHARED,
        pleasure=True,
        **fields,
    )


def test_a_pleasure_goal_needs_no_deadline(session: Session) -> None:
    session.add(_rum(session))
    session.flush()


@pytest.mark.parametrize(
    "fields",
    [{"deadline": date(2027, 1, 1)}, {"permanent": True}, {"permanent": True, "precaution": True}],
)
def test_a_pleasure_goal_has_no_deadline_and_is_neither_permanent_nor_the_precaution(
    session: Session, fields: dict[str, object]
) -> None:
    session.add(_rum(session, **fields))
    with pytest.raises(IntegrityError, match="ck_goal_pleasure_alone"):
        session.flush()
