from kwak_core.users import check_password_policy, normalize_email
from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from kwak_api.auth.passwords import hash_password
from kwak_api.models import Household, Role, User


class HouseholdAlreadyExistsError(Exception):
    """The app hosts a single household (see docs/SPECIFICATIONS.md §2)."""


def create_household(
    session: Session, *, household_name: str, email: str, display_name: str, password: str
) -> User:
    """Create the household and its owner. The caller commits."""
    check_password_policy(password)
    email = normalize_email(email)
    if session.scalar(select(exists().select_from(Household))):
        raise HouseholdAlreadyExistsError("a household already exists")

    owner = User(
        household=Household(name=household_name.strip()),
        email=email,
        display_name=display_name.strip(),
        password_hash=hash_password(password),
        role=Role.OWNER,
    )
    session.add(owner)
    session.flush()
    return owner
