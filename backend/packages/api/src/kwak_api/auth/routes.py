"""Login in two steps: password (opens a pending session), then TOTP (verifies it)."""

import base64
import hmac
import ipaddress
from collections.abc import Callable
from datetime import datetime
from functools import cache
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from kwak_core.audit import AuditAction
from kwak_core.totp import provisioning_uri
from kwak_core.users import Language, normalize_email
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from kwak_api.auth.crypto import SecretBox
from kwak_api.auth.passwords import hash_password, needs_rehash, verify_password
from kwak_api.auth.recovery import issue_recovery_codes, use_recovery_code
from kwak_api.auth.sessions import find_active_session, open_session, revoke_session
from kwak_api.auth.throttle import (
    IP_LIMITS,
    PASSWORD_LIMITS,
    TOTP_LIMITS,
    clear_failures,
    ensure_allowed,
    ip_subject,
    password_subject,
    record_failure,
    totp_subject,
)
from kwak_api.auth.totp import check_code, start_enrollment
from kwak_api.deps import get_db, get_now, get_secret_box, get_settings
from kwak_api.models import Household, Role, User, UserSession
from kwak_api.services import audit
from kwak_api.settings import Settings

SESSION_COOKIE = "kwak_session"
CSRF_COOKIE = "kwak_csrf"
CSRF_HEADER = "X-CSRF-Token"
HOUSEHOLD_HEADER = "X-Kwak-Household"
"""The household the page shows (F-ADM-5): a change sent from a page left in the demo, or
left outside it, is refused rather than saved in the other household."""
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
    language: Language | None
    """The interface language; null until chosen (follow the browser)."""
    demo: bool
    """In the demo (F-ADM-5): the user is the demo's owner, the language still the account's."""

    @classmethod
    def of(cls, user: User, account: User | None = None) -> "UserOut":
        return cls(
            id=user.id,
            household_id=user.household_id,
            email=user.email,
            display_name=user.display_name,
            role=user.role,
            language=(account or user).language,
            demo=user.household.is_demo,
        )

    @classmethod
    def of_session(cls, user_session: UserSession) -> "UserOut":
        return cls.of(user_session.user, user_session.account)


class LoginOut(BaseModel):
    user: UserOut
    next_step: Literal["totp_setup", "totp_verify"]


class PasswordConfirmation(BaseModel):
    password: str


class RecoveryCodeIn(BaseModel):
    code: str


class RecoveryCodesOut(BaseModel):
    recovery_codes: list[str]
    """Shown once: only their hashes are stored."""


class TotpConfirmOut(RecoveryCodesOut):
    user: UserOut


class TotpSetupOut(BaseModel):
    secret: str
    """Base32, for manual entry."""
    uri: str
    """otpauth:// URI, to show as a QR code."""


def client_ip(request: Request) -> str | None:
    """The client's address, if it is one. Behind Caddy, uvicorn --proxy-headers puts the
    real client address here, taken from a header."""
    host = request.client.host if request.client else None
    try:
        return str(ipaddress.ip_address(host)) if host else None
    except ValueError:
        return None


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
        shown = request.headers.get(HOUSEHOLD_HEADER)
        if shown is not None and shown != str(user_session.user.household_id):
            raise HTTPException(
                status.HTTP_409_CONFLICT, "this page shows another household: reload it"
            )
    return user_session


PendingSession = Annotated[UserSession, Depends(pending_session)]


def current_session(user_session: PendingSession) -> UserSession:
    """A fully authenticated session: what every endpoint outside this module requires."""
    if user_session.mfa_verified_at is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "second factor required")
    return user_session


CurrentSession = Annotated[UserSession, Depends(current_session)]

NOT_IN_DEMO = "not available in the demo"


def check_outside_demo(user_session: UserSession) -> None:
    """F-ADM-5: what touches people, passwords and second factors stays out of the demo."""
    if user_session.acting_user_id is not None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, NOT_IN_DEMO)


def outside_demo(user_session: CurrentSession) -> UserSession:
    check_outside_demo(user_session)
    return user_session


OutsideDemoSession = Annotated[UserSession, Depends(outside_demo)]


@router.post("/login")
def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: Db,
    now: Now,
    settings: AppSettings,
) -> LoginOut:
    invalid = HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid email or password")
    ip = ip_subject(client_ip(request) or "unknown")
    try:
        email = normalize_email(body.email)
    except ValueError:
        record_failure(db, [ip], now)
        raise invalid from None
    account = password_subject(email)
    # Checked before the password, so a blocked caller learns nothing from the answer.
    ensure_allowed(db, [(account, PASSWORD_LIMITS), (ip, IP_LIMITS)], now)

    # F-ADM-5: nobody signs in as one of the demo's fictitious members.
    user = db.scalar(
        select(User).join(Household).where(User.email == email, Household.is_demo.is_(False))
    )
    # Hash even for unknown emails so response time does not reveal which accounts exist.
    password_ok = verify_password(user.password_hash if user else _dummy_hash(), body.password)
    if user is None or not user.is_active or not password_ok:
        if user is not None:
            # Committed by record_failure, with the failure it counts.
            audit.record(
                db, user, AuditAction.SIGN_IN_FAILED, now, ip=client_ip(request), step="password"
            )
        record_failure(db, [account, ip], now)
        raise invalid
    clear_failures(db, account)
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
    check_outside_demo(user_session)
    user = user_session.account
    if user.totp_confirmed_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "TOTP is already set up")
    secret = start_enrollment(user, box)
    return TotpSetupOut(
        secret=base64.b32encode(secret).decode().rstrip("="),
        uri=provisioning_uri(secret, account=user.email, issuer=TOTP_ISSUER),
    )


def _check_second_factor(
    db: Session, user: User, now: datetime, ip: str | None, check: Callable[[], bool]
) -> None:
    """TOTP and recovery codes share one attempt limit: both are the second factor."""
    subject = totp_subject(user.id)
    ensure_allowed(db, [(subject, TOTP_LIMITS)], now)
    if not check():
        audit.record(db, user, AuditAction.SIGN_IN_FAILED, now, ip=ip, step="code")
        record_failure(db, [subject], now)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid code")
    clear_failures(db, subject)


def _check_totp(
    db: Session, user: User, box: SecretBox, code: str, now: datetime, ip: str | None
) -> None:
    _check_second_factor(db, user, now, ip, lambda: check_code(user, box, code, now))


def _signed_in(
    db: Session, user_session: UserSession, now: datetime, ip: str | None, method: str
) -> None:
    user_session.mfa_verified_at = now
    audit.record(db, user_session.account, AuditAction.SIGNED_IN, now, ip=ip, method=method)


@router.post("/totp/confirm")
def totp_confirm(
    body: TotpCode, request: Request, user_session: PendingSession, db: Db, box: Box, now: Now
) -> TotpConfirmOut:
    """Prove the authenticator app works; this completes the login and issues recovery codes."""
    check_outside_demo(user_session)
    user = user_session.account
    if user.totp_confirmed_at is not None or user.totp_secret_enc is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "no TOTP setup in progress")
    ip = client_ip(request)
    _check_totp(db, user, box, body.code, now, ip)
    user.totp_confirmed_at = now
    _signed_in(db, user_session, now, ip, "totp")
    return TotpConfirmOut(user=UserOut.of(user), recovery_codes=issue_recovery_codes(db, user))


@router.post("/totp/verify")
def totp_verify(
    body: TotpCode, request: Request, user_session: PendingSession, db: Db, box: Box, now: Now
) -> UserOut:
    check_outside_demo(user_session)
    user = user_session.account
    if user.totp_confirmed_at is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "TOTP is not set up")
    ip = client_ip(request)
    _check_totp(db, user, box, body.code, now, ip)
    _signed_in(db, user_session, now, ip, "totp")
    return UserOut.of(user)


@router.post("/recovery")
def recovery(
    body: RecoveryCodeIn, request: Request, user_session: PendingSession, db: Db, now: Now
) -> UserOut:
    """Complete the login with a recovery code instead of a TOTP code."""
    check_outside_demo(user_session)
    user = user_session.account
    if user.totp_confirmed_at is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "TOTP is not set up")
    ip = client_ip(request)
    _check_second_factor(db, user, now, ip, lambda: use_recovery_code(db, user, body.code, now))
    _signed_in(db, user_session, now, ip, "recovery_code")
    return UserOut.of(user)


@router.post("/recovery-codes")
def regenerate_recovery_codes(
    body: PasswordConfirmation, user_session: OutsideDemoSession, db: Db, now: Now
) -> RecoveryCodesOut:
    """Replace every recovery code. Asks for the password again: a session alone is not enough."""
    user = user_session.account
    subject = password_subject(user.email)
    ensure_allowed(db, [(subject, PASSWORD_LIMITS)], now)
    if not verify_password(user.password_hash, body.password):
        record_failure(db, [subject], now)
        raise HTTPException(status.HTTP_403_FORBIDDEN, "invalid password")
    audit.record(db, user, AuditAction.RECOVERY_CODES_RENEWED, now)
    return RecoveryCodesOut(recovery_codes=issue_recovery_codes(db, user))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    user_session: PendingSession,
    request: Request,
    response: Response,
    db: Db,
    now: Now,
    settings: AppSettings,
) -> None:
    revoke_session(user_session, now)
    if user_session.mfa_verified_at is not None:  # an abandoned sign-in is not a sign-out
        audit.record(db, user_session.account, AuditAction.SIGNED_OUT, now, ip=client_ip(request))
    for name in (SESSION_COOKIE, CSRF_COOKIE):
        response.delete_cookie(name, secure=settings.cookie_secure, samesite="lax")


@router.get("/me")
def me(user_session: CurrentSession) -> UserOut:
    return UserOut.of_session(user_session)


class Preferences(BaseModel):
    language: Language


@router.patch("/me")
def update_me(body: Preferences, user_session: CurrentSession) -> UserOut:
    """Save the signed-in user's preferences: the account's, in the demo too."""
    user_session.account.language = body.language
    return UserOut.of_session(user_session)
