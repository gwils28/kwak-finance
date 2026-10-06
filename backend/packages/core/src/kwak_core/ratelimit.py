"""Sliding-window limits on failed authentication attempts."""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True)
class Limit:
    max_failures: int
    window: timedelta


def retry_after(
    limits: Iterable[Limit], failures: Sequence[datetime], *, now: datetime
) -> timedelta | None:
    """How long to wait before the next attempt is allowed, or None if it is allowed now.

    An attempt is blocked while any window holds `max_failures` failures or more. It is
    allowed again once enough of them have aged out of every window.
    """
    waits: list[timedelta] = []
    for limit in limits:
        recent = sorted(t for t in failures if now - t < limit.window)
        if len(recent) >= limit.max_failures:
            waits.append(recent[-limit.max_failures] + limit.window - now)
    return max(waits, default=None)
