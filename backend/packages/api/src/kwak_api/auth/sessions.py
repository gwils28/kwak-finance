"""Server-side login sessions: opaque cookie token, SHA-256 hash in the database."""

import hashlib
import secrets
from datetime import datetime

from kwak_core.sessions import SessionPolicy, session_is_active
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from kwak_api.models import User, UserSession


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def open_session(db: Session, user: User, now: datetime) -> tuple[str, UserSession]:
    """Return the cookie token (never stored) and the new session."""
    token = secrets.token_urlsafe(32)
    user_session = UserSession(
        user=user,
        token_hash=hash_token(token),
        csrf_token=secrets.token_urlsafe(32),
        created_at=now,
        last_seen_at=now,
    )
    db.add(user_session)
    db.flush()
    return token, user_session


def find_active_session(
    db: Session, token: str, now: datetime, policy: SessionPolicy
) -> UserSession | None:
    """Look up a session by cookie token and record the activity if it is still valid."""
    user_session = db.scalar(
        select(UserSession)
        .where(UserSession.token_hash == hash_token(token))
        .options(joinedload(UserSession.user))
    )
    if user_session is None or not user_session.user.is_active:
        return None
    if not session_is_active(
        policy,
        now=now,
        created_at=user_session.created_at,
        last_seen_at=user_session.last_seen_at,
        revoked_at=user_session.revoked_at,
    ):
        return None
    user_session.last_seen_at = now
    return user_session


def revoke_session(user_session: UserSession, now: datetime) -> None:
    user_session.revoked_at = now
