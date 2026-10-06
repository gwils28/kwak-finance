import pytest
from kwak_api.models import Household, Role, User
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


def _user(household: Household, email: str, role: Role = Role.MEMBER) -> User:
    return User(
        household=household,
        email=email,
        display_name=email.split("@")[0],
        password_hash="$argon2id$placeholder",
        role=role,
    )


def test_household_with_owner_and_member(session: Session) -> None:
    household = Household(name="Home")
    session.add_all(
        [_user(household, "owner@example.com", Role.OWNER), _user(household, "m@example.com")]
    )
    session.flush()
    session.expire_all()

    loaded = session.get_one(Household, household.id)
    assert {u.role for u in loaded.users} == {Role.OWNER, Role.MEMBER}
    assert all(u.is_active for u in loaded.users)


def test_email_is_unique(session: Session) -> None:
    household = Household(name="Home")
    session.add_all([_user(household, "a@example.com"), _user(household, "a@example.com")])
    with pytest.raises(IntegrityError, match="uq_app_user_email"):
        session.flush()


def test_email_must_be_normalized(session: Session) -> None:
    session.add(_user(Household(name="Home"), "Alice@Example.com"))
    with pytest.raises(IntegrityError, match="ck_app_user_email_normalized"):
        session.flush()


def test_a_household_has_at_most_one_owner(session: Session) -> None:
    household = Household(name="Home")
    session.add_all(
        [
            _user(household, "a@example.com", Role.OWNER),
            _user(household, "b@example.com", Role.OWNER),
        ]
    )
    with pytest.raises(IntegrityError, match="uq_app_user_household_owner"):
        session.flush()


def test_role_is_restricted_to_known_values(session: Session) -> None:
    household = Household(name="Home")
    session.add(household)
    session.flush()
    with pytest.raises(IntegrityError, match="ck_app_user_role"):
        session.execute(
            text(
                "INSERT INTO app_user (id, household_id, email, display_name, password_hash, role)"
                " VALUES (gen_random_uuid(), :h, 'x@example.com', 'x', 'h', 'admin')"
            ),
            {"h": household.id},
        )
