"""The month so far (F-BUD-2): each category's spending against its monthly target, with a
warning threshold and the pace of the month; one-off categories (F-CAT-6) skip the pace.

Lines are read from a one-month budget matrix, so they never disagree with it (§8.10).
"""

import calendar
import enum
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from kwak_core.budget import Matrix, Month

DEFAULT_WARN_AT = Decimal("0.80")
MIN_WARN_AT, MAX_WARN_AT = Decimal("0.50"), Decimal("1")


class ProgressStatus(enum.StrEnum):
    ON_TRACK = "on_track"
    WATCH = "watch"
    """From the warning threshold up to the whole target."""
    OVER = "over"


def check_warn_at(value: Decimal) -> None:
    if not MIN_WARN_AT <= value <= MAX_WARN_AT:
        raise ValueError("the warning threshold is between 50 % and 100 %")


def one_off(*, own: bool | None, parent: bool | None) -> bool:
    """A subcategory follows its parent unless it has a setting of its own."""
    return bool(own if own is not None else parent)


def progress_status(spent: Decimal, target: Decimal, warn_at: Decimal) -> ProgressStatus:
    if target == 0:
        return ProgressStatus.OVER if spent > 0 else ProgressStatus.ON_TRACK
    share = spent / target
    if share > 1:
        return ProgressStatus.OVER
    return ProgressStatus.WATCH if share >= warn_at else ProgressStatus.ON_TRACK


def month_pace(month: Month, today: date) -> Decimal | None:
    """The share of `month` elapsed at the end of `today`; None unless it is today's month."""
    if Month.of(today) != month:
        return None
    return Decimal(today.day) / calendar.monthrange(month.year, month.month)[1]


@dataclass(frozen=True)
class ProgressLine:
    category_id: UUID
    name: str
    parent_id: UUID | None
    spent: Decimal
    target: Decimal
    remaining: Decimal
    """target - spent: negative once over."""
    share: Decimal | None
    """spent / target; None for a zero target."""
    status: ProgressStatus
    pace: Decimal | None
    """None for a one-off category or another month than today's."""

    @property
    def rank(self) -> Decimal:
        """Higher first: a zero target with spending ranks above everything."""
        if self.share is not None:
            return self.share
        return Decimal("Infinity") if self.spent > 0 else Decimal(-1)


def month_progress(
    matrix: Matrix,
    *,
    today: date,
    settings: Mapping[UUID, bool],
    warn_at: Decimal = DEFAULT_WARN_AT,
) -> list[ProgressLine]:
    """One line per expense category with a target of its own in the matrix's single month
    (a parent's covers its children; one summed from the children is left to them).
    `settings` hold each category's own one-off setting (F-CAT-6), followed by its children."""
    check_warn_at(warn_at)
    (month,) = matrix.months
    pace = month_pace(month, today)
    lines = []
    for row in matrix.rows:
        cell = row.cells[0]
        if row.category_id is None or cell.target is None or row.target_from_children:
            continue
        own = settings.get(row.category_id)
        parent = settings.get(row.parent_id) if row.parent_id else None
        lines.append(
            ProgressLine(
                row.category_id,
                row.name,
                row.parent_id,
                cell.spent,
                cell.target,
                cell.target - cell.spent,
                cell.spent / cell.target if cell.target else None,
                progress_status(cell.spent, cell.target, warn_at),
                None if one_off(own=own, parent=parent) else pace,
            )
        )
    return sorted(lines, key=lambda line: (-line.rank, line.name.lower()))
