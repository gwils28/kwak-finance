from kwak_core.users import Language, check_password_policy, normalize_email
from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from kwak_api.auth.passwords import hash_password
from kwak_api.models import Household, Role, User
from kwak_api.services.categories import seed_defaults


class HouseholdAlreadyExistsError(Exception):
    """The app hosts a single household (see docs/SPECIFICATIONS.md §2)."""


def create_household(
    session: Session,
    *,
    household_name: str,
    email: str,
    display_name: str,
    password: str,
    language: Language | None = None,
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
        language=language,
    )
    session.add(owner)
    session.flush()
    seed_defaults(session, owner.household_id, language or Language.EN)
    return owner
