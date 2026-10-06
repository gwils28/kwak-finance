"""Login in two steps: password (opens a pending session), then TOTP (verifies it)."""

import base64
import hmac
from datetime import datetime
from functools import cache
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from kwak_core.totp import provisioning_uri
from kwak_core.users import normalize_email
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from kwak_api.auth.crypto import SecretBox
from kwak_api.auth.passwords import hash_password, needs_rehash, verify_password
from kwak_api.auth.sessions import find_active_session, open_session, revoke_session
from kwak_api.auth.totp import check_code, start_enrollment
from kwak_api.deps import get_db, get_now, get_secret_box, get_settings
from kwak_api.models import Role, User, UserSession
from kwak_api.settings import Settings

SESSION_COOKIE = "kwak_session"
CSRF_COOKIE = "kwak_csrf"
CSRF_HEADER = "X-CSRF-Token"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
TOTP_ISSUER = "Kwak Finance"

# scope="function": commit before the response is sent, so a failed commit is a 500.
Db = Annotated[Session, Depends(get_db, scope="function")]
Now = Annotated[datetime, Depends(get_now)]
AppSettings = Annotated[Settings, Depends(get_settings)]
Box = Annotated[SecretBox, Depends(get_secret_box)]

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    password: str


class TotpCode(BaseModel):
    code: str


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


class LoginOut(BaseModel):
    user: UserOut
    next_step: Literal["totp_setup", "totp_verify"]


class TotpSetupOut(BaseModel):
    secret: str
    """Base32, for manual entry."""
    uri: str
    """otpauth:// URI, to show as a QR code."""


@cache
def _dummy_hash() -> str:
    return hash_password("timing equaliser, never a real password")


def pending_session(
    request: Request,
    db: Db,
    now: Now,
    settings: AppSettings,
    token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> UserSession:
    """An active session, second factor checked or not. Unsafe methods need the CSRF header."""
    user_session = token and find_active_session(db, token, now, settings.session_policy)
    if not user_session:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "not authenticated")
    if request.method not in SAFE_METHODS:
        sent = request.headers.get(CSRF_HEADER, "")
        if not hmac.compare_digest(sent.encode(), user_session.csrf_token.encode()):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "missing or invalid CSRF token")
    return user_session


PendingSession = Annotated[UserSession, Depends(pending_session)]


def current_session(user_session: PendingSession) -> UserSession:
    """A fully authenticated session: what every endpoint outside this module requires."""
    if user_session.mfa_verified_at is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "second factor required")
    return user_session


CurrentSession = Annotated[UserSession, Depends(current_session)]


@router.post("/login")
def login(
    body: LoginRequest, response: Response, db: Db, now: Now, settings: AppSettings
) -> LoginOut:
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
    next_step = "totp_verify" if user.totp_confirmed_at else "totp_setup"
    return LoginOut(user=UserOut.of(user), next_step=next_step)


@router.post("/totp/setup")
def totp_setup(user_session: PendingSession, box: Box) -> TotpSetupOut:
    """Issue a new seed. Only before enrollment: a password alone must not replace the factor."""
    user = user_session.user
    if user.totp_confirmed_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "TOTP is already set up")
    secret = start_enrollment(user, box)
    return TotpSetupOut(
        secret=base64.b32encode(secret).decode().rstrip("="),
        uri=provisioning_uri(secret, account=user.email, issuer=TOTP_ISSUER),
    )


@router.post("/totp/confirm")
def totp_confirm(body: TotpCode, user_session: PendingSession, box: Box, now: Now) -> UserOut:
    """Prove the authenticator app works; this also completes the current login."""
    user = user_session.user
    if user.totp_confirmed_at is not None or user.totp_secret_enc is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "no TOTP setup in progress")
    if not check_code(user, box, body.code, now):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid code")
    user.totp_confirmed_at = now
    user_session.mfa_verified_at = now
    return UserOut.of(user)


@router.post("/totp/verify")
def totp_verify(body: TotpCode, user_session: PendingSession, box: Box, now: Now) -> UserOut:
    user = user_session.user
    if user.totp_confirmed_at is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "TOTP is not set up")
    if not check_code(user, box, body.code, now):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid code")
    user_session.mfa_verified_at = now
    return UserOut.of(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    user_session: PendingSession, response: Response, now: Now, settings: AppSettings
) -> None:
    revoke_session(user_session, now)
    for name in (SESSION_COOKIE, CSRF_COOKIE):
        response.delete_cookie(name, secure=settings.cookie_secure, samesite="lax")


@router.get("/me")
def me(user_session: CurrentSession) -> UserOut:
    return UserOut.of(user_session.user)
