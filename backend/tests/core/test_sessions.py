from datetime import UTC, datetime, timedelta

from hypothesis import given
from hypothesis import strategies as st
from kwak_core.sessions import SessionPolicy, session_is_active

POLICY = SessionPolicy(idle=timedelta(days=7), absolute=timedelta(days=30))
T0 = datetime(2026, 1, 1, tzinfo=UTC)
offsets = st.timedeltas(min_value=timedelta(0), max_value=timedelta(days=60))


def test_a_fresh_session_is_active() -> None:
    assert session_is_active(POLICY, now=T0, created_at=T0, last_seen_at=T0, revoked_at=None)


def test_a_revoked_session_is_inactive() -> None:
    assert not session_is_active(POLICY, now=T0, created_at=T0, last_seen_at=T0, revoked_at=T0)


def test_idle_timeout_is_exclusive() -> None:
    now = T0 + POLICY.idle
    assert not session_is_active(POLICY, now=now, created_at=T0, last_seen_at=T0, revoked_at=None)
    now -= timedelta(seconds=1)
    assert session_is_active(POLICY, now=now, created_at=T0, last_seen_at=T0, revoked_at=None)


@given(offsets, offsets)
def test_activity_never_extends_past_the_absolute_lifetime(seen: timedelta, age: timedelta) -> None:
    last_seen = T0 + min(seen, age)
    now = T0 + age
    active = session_is_active(
        POLICY, now=now, created_at=T0, last_seen_at=last_seen, revoked_at=None
    )
    if age >= POLICY.absolute:
        assert not active
    if now - last_seen >= POLICY.idle:
        assert not active
    if age < POLICY.absolute and now - last_seen < POLICY.idle:
        assert active
