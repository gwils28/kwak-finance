from uuid import UUID

from kwak_core.budget import Month
from kwak_core.users import Language, check_password_policy, normalize_email
from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from kwak_api.auth.passwords import hash_password
from kwak_api.models import Household, Role, User
from kwak_api.services import spending, wealth


class HouseholdAlreadyExistsError(Exception):
    """The app hosts a single household (see docs/SPECIFICATIONS.md §2)."""


def wealth_start(db: Session, household_id: UUID) -> Month | None:
    """The first month the wealth matrix shows by default (F-WLT-5); None: no limit."""
    start = db.get_one(Household, household_id).wealth_start
    return Month.of(start) if start else None


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
    if session.scalar(select(exists().where(Household.is_demo.is_(False)))):
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
    wealth.seed_defaults(session, owner.household_id, language or Language.EN)
    spending.seed_categories(session, owner.household_id, language or Language.EN)
    return owner
