"""Household invitation lifecycle."""

import enum
from datetime import datetime, timedelta

INVITE_LIFETIME = timedelta(days=7)


class InviteState(enum.StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REVOKED = "revoked"
    EXPIRED = "expired"


def invite_state(
    *,
    now: datetime,
    expires_at: datetime,
    accepted_at: datetime | None,
    revoked_at: datetime | None,
) -> InviteState:
    """Acceptance and revocation are final; otherwise an invite expires on its own."""
    if accepted_at is not None:
        return InviteState.ACCEPTED
    if revoked_at is not None:
        return InviteState.REVOKED
    if now >= expires_at:
        return InviteState.EXPIRED
    return InviteState.PENDING
