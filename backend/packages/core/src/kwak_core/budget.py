"""Monthly budget: targets per category and the budget matrix (F-BUD-1, 2, 4, 6).

Spending is a positive number: the outflows of a category minus its refunds.
"""

import enum
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from uuid import UUID

DEFAULT_BAND = Decimal("0.05")


@dataclass(frozen=True, order=True)
class Month:
    year: int
    month: int

    @classmethod
    def of(cls, day: date) -> "Month":
        return cls(day.year, day.month)

    @classmethod
    def parse(cls, text: str) -> "Month":
        """ "2026-03" -> Month(2026, 3)."""
        year, _, month = text.partition("-")
        value = cls(int(year), int(month))
        if not 1 <= value.month <= 12:
            raise ValueError(f"invalid month {text!r}, expected YYYY-MM")
        return value

    def first_day(self) -> date:
        return date(self.year, self.month, 1)

    def next(self) -> "Month":
        return Month(self.year + self.month // 12, self.month % 12 + 1)

    def __str__(self) -> str:
        return f"{self.year:04d}-{self.month:02d}"


def month_range(start: Month, end: Month) -> list[Month]:
    """Every month from start to end, both included."""
    months = []
    current = start
    while current <= end:
        months.append(current)
        current = current.next()
    return months


def target_for(history: Sequence[tuple[Month, Decimal | None]], month: Month) -> Decimal | None:
    """The target in force in `month`: the latest one set on or before it (None = removed)."""
    in_force = [(start, amount) for start, amount in history if start <= month]
    return max(in_force, key=lambda item: item[0])[1] if in_force else None


class BudgetStatus(enum.StrEnum):
    UNDER = "under"
    ON = "on"
    OVER = "over"
    NONE = "none"
    """No target to compare with."""


def budget_status(
    spent: Decimal, target: Decimal | None, band: Decimal = DEFAULT_BAND
) -> BudgetStatus:
    """Under or over when the gap exceeds `band` (a share of the target) either way."""
    if target is None:
        return BudgetStatus.NONE
    if target == 0:
        return BudgetStatus.ON if spent <= 0 else BudgetStatus.OVER
    ratio = (spent - target) / target
    if ratio < -band:
        return BudgetStatus.UNDER
    if ratio > band:
        return BudgetStatus.OVER
    return BudgetStatus.ON


@dataclass(frozen=True)
class Cell:
    month: Month
    spent: Decimal
    target: Decimal | None
    gap: Decimal | None
    """spent - target."""
    gap_ratio: Decimal | None
    """gap / target, e.g. 0.1 for 10 % over; None without a (non-zero) target."""
    status: BudgetStatus


def _cell(month: Month, spent: Decimal, target: Decimal | None, band: Decimal) -> Cell:
    gap = None if target is None else spent - target
    ratio = None if gap is None or not target else gap / target
    return Cell(month, spent, target, gap, ratio, budget_status(spent, target, band))


@dataclass(frozen=True)
class Row:
    category_id: UUID | None
    name: str
    parent_id: UUID | None
    level: int
    """0 for a top-level category, 1 for a subcategory."""
    target: Decimal | None
    """The target in force in the last month shown."""
    cells: list[Cell] = field(default_factory=list)


@dataclass(frozen=True)
class Matrix:
    months: list[Month]
    rows: list[Row]
    uncategorised: Row
    total: Row


def build_matrix(
    categories: Sequence[tuple[UUID, UUID | None, str]],
    targets: Mapping[UUID, Sequence[tuple[Month, Decimal | None]]],
    spending: Mapping[tuple[UUID | None, Month], Decimal],
    months: Sequence[Month],
    band: Decimal = DEFAULT_BAND,
) -> Matrix:
    """`categories` are (id, parent_id, name) of expense categories, two levels deep."""
    zero = Decimal(0)
    children: dict[UUID, list[tuple[UUID, str]]] = {}
    for cid, parent, name in categories:
        if parent is not None:
            children.setdefault(parent, []).append((cid, name))

    def spent(cid: UUID | None, month: Month) -> Decimal:
        return spending.get((cid, month), zero)

    def own_target(cid: UUID, month: Month) -> Decimal | None:
        return target_for(targets.get(cid, ()), month)

    def row(cid: UUID, parent: UUID | None, name: str, level: int, kids: list[UUID]) -> Row:
        cells = []
        targets_by_month = []
        for month in months:
            total = spent(cid, month) + sum((spent(k, month) for k in kids), zero)
            target = own_target(cid, month)
            if target is None and kids:
                child_targets = [t for k in kids if (t := own_target(k, month)) is not None]
                target = sum(child_targets, zero) if child_targets else None
            targets_by_month.append(target)
            cells.append(_cell(month, total, target, band))
        return Row(cid, name, parent, level, targets_by_month[-1] if months else None, cells)

    rows = []
    for cid, _parent, name in sorted(
        (c for c in categories if c[1] is None), key=lambda c: c[2].lower()
    ):
        kids = sorted(children.get(cid, []), key=lambda k: k[1].lower())
        rows.append(row(cid, None, name, 0, [k for k, _ in kids]))
        rows.extend(row(k, cid, kname, 1, []) for k, kname in kids)

    uncategorised = Row(
        None,
        "To categorise",
        None,
        0,
        None,
        [_cell(m, spent(None, m), None, band) for m in months],
    )
    top = [r for r in rows if r.level == 0]

    def total_target(i: int) -> Decimal | None:
        set_targets = [t for r in top if (t := r.cells[i].target) is not None]
        return sum(set_targets, zero) if set_targets else None

    total_cells = [
        _cell(
            m,
            sum((r.cells[i].spent for r in top), zero) + uncategorised.cells[i].spent,
            total_target(i),
            band,
        )
        for i, m in enumerate(months)
    ]
    last_target = total_cells[-1].target if total_cells else None
    total = Row(None, "Total", None, 0, last_target, total_cells)
    return Matrix(list(months), rows, uncategorised, total)
