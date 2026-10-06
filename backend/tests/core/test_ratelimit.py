from datetime import UTC, datetime, timedelta

from hypothesis import given
from hypothesis import strategies as st
from kwak_core.ratelimit import Limit, retry_after

T0 = datetime(2026, 1, 1, tzinfo=UTC)
LIMITS = (Limit(5, timedelta(minutes=15)), Limit(20, timedelta(days=1)))
failure_times = st.lists(
    st.timedeltas(min_value=timedelta(0), max_value=timedelta(days=2)), max_size=40
).map(lambda offsets: [T0 + o for o in offsets])


def test_under_the_limit_is_allowed() -> None:
    assert retry_after(LIMITS, [T0] * 4, now=T0) is None


def test_reaching_the_limit_blocks_until_the_oldest_counted_failure_expires() -> None:
    failures = [T0 + timedelta(minutes=m) for m in range(5)]
    now = T0 + timedelta(minutes=5)
    assert retry_after(LIMITS, failures, now=now) == timedelta(minutes=10)


def test_old_failures_do_not_count() -> None:
    assert retry_after(LIMITS, [T0] * 5, now=T0 + timedelta(minutes=15)) is None


def test_the_daily_limit_applies_when_failures_are_spread_out() -> None:
    failures = [T0 + timedelta(minutes=16 * i) for i in range(20)]
    now = failures[-1] + timedelta(minutes=16)
    wait = retry_after(LIMITS, failures, now=now)
    assert wait == failures[0] + timedelta(days=1) - now


@given(failure_times, st.timedeltas(min_value=timedelta(0), max_value=timedelta(days=3)))
def test_waiting_the_returned_delay_is_enough(failures: list[datetime], at: timedelta) -> None:
    now = T0 + at
    past = [t for t in failures if t <= now]
    wait = retry_after(LIMITS, past, now=now)
    if wait is not None:
        assert wait > timedelta(0)
        assert retry_after(LIMITS, past, now=now + wait) is None


@given(failure_times, st.timedeltas(min_value=timedelta(0), max_value=timedelta(days=3)))
def test_allowed_means_every_window_is_under_its_limit(
    failures: list[datetime], at: timedelta
) -> None:
    now = T0 + at
    past = [t for t in failures if t <= now]
    if retry_after(LIMITS, past, now=now) is None:
        for limit in LIMITS:
            assert sum(now - t < limit.window for t in past) < limit.max_failures
