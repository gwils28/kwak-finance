from datetime import UTC, datetime, timedelta

import pytest
from kwak_core.invites import INVITE_LIFETIME, InviteState, invite_state

T0 = datetime(2026, 1, 1, tzinfo=UTC)


def _state(
    now: datetime, *, accepted: datetime | None = None, revoked: datetime | None = None
) -> InviteState:
    return invite_state(
        now=now, expires_at=T0 + INVITE_LIFETIME, accepted_at=accepted, revoked_at=revoked
    )


def test_an_invite_lasts_seven_days() -> None:
    assert timedelta(days=7) == INVITE_LIFETIME
    assert _state(T0) is InviteState.PENDING
    assert _state(T0 + INVITE_LIFETIME - timedelta(seconds=1)) is InviteState.PENDING
    assert _state(T0 + INVITE_LIFETIME) is InviteState.EXPIRED


@pytest.mark.parametrize("now", [T0, T0 + timedelta(days=30)])
def test_acceptance_and_revocation_are_final(now: datetime) -> None:
    assert _state(now, accepted=T0) is InviteState.ACCEPTED
    assert _state(now, revoked=T0) is InviteState.REVOKED
