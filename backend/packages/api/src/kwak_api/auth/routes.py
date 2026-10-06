import hmac
from datetime import datetime
from functools import cache
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from kwak_core.users import normalize_email
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from kwak_api.auth.passwords import hash_password, needs_rehash, verify_password
from kwak_api.auth.sessions import find_active_session, open_session, revoke_session
from kwak_api.deps import get_db, get_now, get_settings
from kwak_api.models import Role, User, UserSession
from kwak_api.settings import Settings

SESSION_COOKIE = "kwak_session"
CSRF_COOKIE = "kwak_csrf"
CSRF_HEADER = "X-CSRF-Token"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

# scope="function": commit before the response is sent, so a failed commit is a 500.
Db = Annotated[Session, Depends(get_db, scope="function")]
Now = Annotated[datetime, Depends(get_now)]
AppSettings = Annotated[Settings, Depends(get_settings)]

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    password: str


class UserOut(BaseModel):
    id: UUID
    household_id: UUID
    email: str
    display_name: str
    role: Role

    @classmethod
    def of(cls, user: User) -> "UserOut":
        return cls(
            id=user.id,
            household_id=user.household_id,
            email=user.email,
            display_name=user.display_name,
            role=user.role,
        )


@cache
def _dummy_hash() -> str:
    return hash_password("timing equaliser, never a real password")


def current_session(
    request: Request,
    db: Db,
    now: Now,
    settings: AppSettings,
    token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> UserSession:
    """The caller's active session. Unsafe methods must echo the CSRF token in a header."""
    user_session = token and find_active_session(db, token, now, settings.session_policy)
    if not user_session:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "not authenticated")
    if request.method not in SAFE_METHODS:
        sent = request.headers.get(CSRF_HEADER, "")
        if not hmac.compare_digest(sent.encode(), user_session.csrf_token.encode()):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "missing or invalid CSRF token")
    return user_session


CurrentSession = Annotated[UserSession, Depends(current_session)]


@router.post("/login")
def login(
    body: LoginRequest, response: Response, db: Db, now: Now, settings: AppSettings
) -> UserOut:
    invalid = HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid email or password")
    try:
        email = normalize_email(body.email)
    except ValueError:
        raise invalid from None
    user = db.scalar(select(User).where(User.email == email))
    # Hash even for unknown emails so response time does not reveal which accounts exist.
    if not verify_password(user.password_hash if user else _dummy_hash(), body.password):
        raise invalid
    if user is None or not user.is_active:
        raise invalid
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(body.password)

    token, user_session = open_session(db, user, now)
    max_age = int(settings.session_policy.absolute.total_seconds())
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=max_age,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
    )
    # Readable by the SPA, which echoes it in the X-CSRF-Token header.
    response.set_cookie(
        CSRF_COOKIE,
        user_session.csrf_token,
        max_age=max_age,
        secure=settings.cookie_secure,
        samesite="lax",
    )
    return UserOut.of(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    user_session: CurrentSession, response: Response, now: Now, settings: AppSettings
) -> None:
    revoke_session(user_session, now)
    for name in (SESSION_COOKIE, CSRF_COOKIE):
        response.delete_cookie(name, secure=settings.cookie_secure, samesite="lax")


@router.get("/me")
def me(user_session: CurrentSession) -> UserOut:
    return UserOut.of(user_session.user)
