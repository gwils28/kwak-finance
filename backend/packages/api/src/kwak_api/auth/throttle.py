"""Failed-attempt limits for login and TOTP, stored in the database to survive restarts."""

import math
from collections.abc import Iterable
from datetime import datetime, timedelta
from uuid import UUID

from fastapi import HTTPException, status
from kwak_core.ratelimit import Limit, retry_after
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from kwak_api.models import AuthFailure

_SHORT = timedelta(minutes=15)
_DAY = timedelta(days=1)
PASSWORD_LIMITS = (Limit(5, _SHORT), Limit(20, _DAY))
# Several household members may share one LAN address: keep this one loose.
IP_LIMITS = (Limit(20, _SHORT),)
# 20 codes a day: guessing a 6-digit code would take decades, not days.
TOTP_LIMITS = (Limit(5, _SHORT), Limit(20, _DAY))
_RETENTION = _DAY


def password_subject(email: str) -> str:
    return f"password:{email}"


def ip_subject(address: str) -> str:
    return f"ip:{address}"


def totp_subject(user_id: UUID) -> str:
    return f"totp:{user_id}"


def ensure_allowed(
    db: Session, checks: Iterable[tuple[str, tuple[Limit, ...]]], now: datetime
) -> None:
    """Raise 429 with Retry-After if any subject has used up its attempts."""
    waits: list[timedelta] = []
    for subject, limits in checks:
        since = now - max(limit.window for limit in limits)
        failures = db.scalars(
            select(AuthFailure.occurred_at).where(
                AuthFailure.subject == subject, AuthFailure.occurred_at > since
            )
        ).all()
        wait = retry_after(limits, failures, now=now)
        if wait is not None:
            waits.append(wait)
    if waits:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "too many failed attempts, try again later",
            headers={"Retry-After": str(math.ceil(max(waits).total_seconds()))},
        )


def record_failure(db: Session, subjects: Iterable[str], now: datetime) -> None:
    """Store the failure and commit at once: the error response rolls back the rest."""
    subjects = list(subjects)
    db.add_all(AuthFailure(subject=s, occurred_at=now) for s in subjects)
    db.execute(
        delete(AuthFailure).where(
            AuthFailure.subject.in_(subjects), AuthFailure.occurred_at <= now - _RETENTION
        )
    )
    db.commit()


def clear_failures(db: Session, subject: str) -> None:
    db.execute(delete(AuthFailure).where(AuthFailure.subject == subject))
