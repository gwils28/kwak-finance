"""Login session lifetime rules."""

from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True)
class SessionPolicy:
    idle: timedelta
    """A session unused for this long expires."""
    absolute: timedelta
    """A session expires this long after login, however active it is."""


def session_is_active(
    policy: SessionPolicy,
    *,
    now: datetime,
    created_at: datetime,
    last_seen_at: datetime,
    revoked_at: datetime | None,
) -> bool:
    return (
        revoked_at is None
        and now - last_seen_at < policy.idle
        and now - created_at < policy.absolute
    )
