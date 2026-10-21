"""Label memory (F-ENT-3): suggest the labels already used, remember their category."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

from kwak_core.quickline import fold

DEFAULT_LIMIT = 8


@dataclass(frozen=True)
class Use:
    """A line with a category of its own (a split line gives none)."""

    label: str
    category_id: UUID
    day: date
    entered_at: datetime


def normalise(label: str) -> str:
    return " ".join(fold(label).split())


def remembered_category(label: str, uses: Sequence[Use]) -> UUID | None:
    """The category of the latest line entered with this label."""
    wanted = normalise(label)
    same = [u for u in uses if normalise(u.label) == wanted]
    return max(same, key=lambda u: u.entered_at).category_id if same else None


def suggest(typed: str, uses: Sequence[Use], today: date, limit: int = DEFAULT_LIMIT) -> list[str]:
    """Labels starting with `typed`, the most used over the last 12 months first.

    Each label is given as it was spelt last.
    """
    prefix = normalise(typed)
    if not prefix:
        return []
    since = date(today.year - 1, today.month, 1)
    counts: dict[str, int] = {}
    latest: dict[str, Use] = {}
    for use in uses:
        key = normalise(use.label)
        if not key.startswith(prefix):
            continue
        counts[key] = counts.get(key, 0) + (use.day >= since)
        if key not in latest or use.entered_at > latest[key].entered_at:
            latest[key] = use
    ranked = sorted(counts, key=lambda k: (-counts[k], -latest[k].entered_at.timestamp()))
    return [latest[k].label for k in ranked[:limit]]
