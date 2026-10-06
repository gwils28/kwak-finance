import pytest
from kwak_api.auth.passwords import verify_password
from kwak_api.models import Role
from kwak_api.services.households import HouseholdAlreadyExistsError, create_household
from sqlalchemy.orm import Session

PASSWORD = "correct horse battery"


def test_create_household_with_its_owner(session: Session) -> None:
    owner = create_household(
        session,
        household_name="Home",
        email=" Owner@Example.com ",
        display_name="Owner",
        password=PASSWORD,
    )

    assert owner.role is Role.OWNER
    assert owner.email == "owner@example.com"
    assert owner.household.name == "Home"
    assert verify_password(owner.password_hash, PASSWORD)


def test_only_one_household_can_exist(session: Session) -> None:
    create_household(
        session, household_name="A", email="a@example.com", display_name="A", password=PASSWORD
    )
    with pytest.raises(HouseholdAlreadyExistsError):
        create_household(
            session, household_name="B", email="b@example.com", display_name="B", password=PASSWORD
        )


def test_weak_password_is_rejected_before_anything_is_written(session: Session) -> None:
    with pytest.raises(ValueError, match="password"):
        create_household(
            session, household_name="A", email="a@example.com", display_name="A", password="short"
        )
    assert not session.new
