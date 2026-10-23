from datetime import date
from decimal import Decimal

import pytest
from kwak_api.models import Goal, GoalNoticeDismissal, Household, Role, User
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


def test_a_point_is_snoozed_or_dismissed_once_per_member(session: Session) -> None:
    goal = _rum(session)
    session.add(goal)
    session.flush()

    def point(**fields: object) -> GoalNoticeDismissal:
        return GoalNoticeDismissal(user_id=goal.owner_id, rule="behind", goal_id=goal.id, **fields)

    session.add(point(until=date(2026, 11, 1)))
    session.flush()
    session.add(point(severity="warning", amount=Decimal("100.00")))
    with pytest.raises(IntegrityError, match="uq_goal_notice_dismissal"):
        session.flush()


@pytest.mark.parametrize("fields", [{}, {"until": date(2026, 11, 1), "severity": "warning"}])
def test_a_point_is_either_snoozed_or_dismissed(
    session: Session, fields: dict[str, object]
) -> None:
    goal = _rum(session)
    session.add(goal)
    session.flush()
    session.add(
        GoalNoticeDismissal(user_id=goal.owner_id, rule="behind", goal_id=goal.id, **fields)
    )
    with pytest.raises(IntegrityError, match="ck_goal_notice_dismissal_snoozed_or_dismissed"):
        session.flush()


def test_a_household_wide_point_has_no_goal_nor_line(session: Session) -> None:
    goal = _rum(session)
    session.add(goal)
    session.flush()
    for _ in range(2):
        session.add(
            GoalNoticeDismissal(
                user_id=goal.owner_id, rule="overcommitted", until=date(2026, 11, 1)
            )
        )
    with pytest.raises(IntegrityError, match="uq_goal_notice_dismissal"):
        session.flush()
