"""The monthly wealth matrix (F-WLT, invariants §8.5 and §8.6).

Wealth categories are assets or debts; their lines are holdings, each with at most one value
per calendar month. A month without a value carries the previous one forward; before its first
value, and from the month it is closed, a line is empty. Debts are entered as what is still
owed (positive) and count negatively: net worth = gross assets - debts.

Ratios and shares are exact: the API rounds them for display.
"""

import enum
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from kwak_core.accounts import AccountType, Scope, Visibility
from kwak_core.accounts import in_scope as account_in_scope
from kwak_core.budget import Month
from kwak_core.categories import Names

ZERO = Decimal(0)
CENT = Decimal("0.01")


class WealthKind(enum.StrEnum):
    ASSET = "asset"
    DEBT = "debt"


class WealthValueError(ValueError):
    """A value a line cannot hold."""


@dataclass(frozen=True)
class DefaultWealthCategory:
    names: Names
    kind: WealthKind
    colour: str
    """The key of the category's `wealth-<key>` colour token (§7)."""
    holds: AccountType | None = None
    """The app's cash accounts of this type are its lines, valued automatically (F-WLT-4)."""


def _asset(
    en: str, fr: str, colour: str, holds: AccountType | None = None
) -> DefaultWealthCategory:
    return DefaultWealthCategory(Names(en, fr), WealthKind.ASSET, colour, holds)


DEFAULT_WEALTH_CATEGORIES: tuple[DefaultWealthCategory, ...] = (
    _asset("Savings accounts", "Livrets", "savings", AccountType.SAVINGS),
    _asset("Current accounts", "Comptes courants", "current", AccountType.CHECKING),
    _asset("Stocks", "Actions", "stocks"),
    _asset("Crypto", "Cryptos", "crypto"),
    _asset("Bonds", "Obligations", "bonds"),
    _asset("Private equity", "Private equity", "private-equity"),
    _asset("Gold", "Or", "gold"),
    _asset("Real estate", "Immobilier", "real-estate"),
    _asset("Equipment", "Matériels", "equipment"),
    _asset("Exotic", "Exotiques", "exotic"),
    DefaultWealthCategory(Names("Debts", "Dettes"), WealthKind.DEBT, "debts"),
)


WEALTH_COLOURS = frozenset(c.colour for c in DEFAULT_WEALTH_CATEGORIES)
"""The colour keys a category can take (§7)."""


def check_value(amount: Decimal, *, cash: bool) -> None:
    """Cents at most, and positive: a debt is what is still owed. Only a cash line, read from
    its account, can be negative (an overdrawn current account)."""
    if amount != amount.quantize(CENT):
        raise WealthValueError("a value has cents at most")
    if amount < 0 and not cash:
        raise WealthValueError("a value is positive: enter a debt as what is still owed")


@dataclass(frozen=True)
class Cell:
    amount: Decimal
    carried: bool
    """No value entered this month: the previous one carried forward."""


def line_cell(
    values: Mapping[Month, Decimal], month: Month, *, closed_from: Month | None = None
) -> Cell | None:
    """A line's value in `month`; None before its first value or once it is closed."""
    if closed_from is not None and month >= closed_from:
        return None
    if month in values:
        return Cell(values[month], carried=False)
    earlier = [m for m in values if m < month]
    return Cell(values[max(earlier)], carried=True) if earlier else None


@dataclass(frozen=True)
class CategoryInput:
    id: UUID
    kind: WealthKind


@dataclass(frozen=True)
class LineInput:
    id: UUID
    category_id: UUID
    values: Mapping[Month, Decimal]
    """Entered by hand; for a cash line (F-WLT-4), its account's balance at each month's end,
    so it is never carried."""
    owner_id: UUID
    visibility: Visibility
    closed_from: Month | None = None


def in_scope(lines: Sequence[LineInput], scope: Scope, viewer_id: UUID) -> list[LineInput]:
    """The lines a view covers, by the accounts' rules (§3)."""
    return [
        line
        for line in lines
        if account_in_scope(
            scope, owner_id=line.owner_id, visibility=line.visibility, viewer_id=viewer_id
        )
    ]


def to_update(lines: Sequence[LineInput], month: Month) -> list[tuple[LineInput, Decimal | None]]:
    """ "Update this month": the lines still open, with their last value (None: none yet)."""
    out: list[tuple[LineInput, Decimal | None]] = []
    for line in lines:
        if line.closed_from is not None and month >= line.closed_from:
            continue
        cell = line_cell(line.values, month)
        out.append((line, cell.amount if cell else None))
    return out


@dataclass(frozen=True)
class WealthMatrix:
    months: list[Month]
    lines: dict[UUID, list[Cell | None]]
    categories: dict[UUID, list[Decimal]]
    """Every category, in the given order: its subtotal per month (a debt: what is owed)."""
    gross: list[Decimal]
    debts: list[Decimal]
    net: list[Decimal]
    change: list[Decimal | None]
    """Net worth against the month before, None when that month held nothing."""
    change_ratio: list[Decimal | None]
    """Against the size of the month before: from -1000 to -800 is +0.2."""
    shares: dict[UUID, Decimal]
    """Each asset category's share of gross assets in the last month (none without any)."""
    line_shares: dict[UUID, Decimal]
    """Each asset line's share of gross assets in the last month."""


def wealth_matrix(
    categories: Sequence[CategoryInput], lines: Sequence[LineInput], months: Sequence[Month]
) -> WealthMatrix:
    """`categories` gives the rows' order and each category's kind; `lines` are in scope."""
    kinds = {c.id: c.kind for c in categories}
    for line in lines:
        if line.category_id not in kinds:
            raise ValueError(f"line {line.id} has an unknown category")

    def column(month: Month) -> tuple[dict[UUID, Cell | None], bool]:
        cells = {ln.id: line_cell(ln.values, month, closed_from=ln.closed_from) for ln in lines}
        return cells, any(c is not None for c in cells.values())

    by_category: dict[UUID, list[Decimal]] = {c.id: [] for c in categories}
    by_line: dict[UUID, list[Cell | None]] = {ln.id: [] for ln in lines}
    gross: list[Decimal] = []
    debts: list[Decimal] = []
    change: list[Decimal | None] = []
    ratio: list[Decimal | None] = []
    previous: Decimal | None = None
    if months:
        before, held = column(months[0].previous())
        previous = _net(before, lines, kinds) if held else None
    for month in months:
        cells, held = column(month)
        totals = dict.fromkeys(by_category, ZERO)
        for ln in lines:
            cell = cells[ln.id]
            by_line[ln.id].append(cell)
            if cell is not None:
                totals[ln.category_id] += cell.amount
        for category_id, subtotal in totals.items():
            by_category[category_id].append(subtotal)
        g = sum((t for c, t in totals.items() if kinds[c] is WealthKind.ASSET), ZERO)
        d = sum((t for c, t in totals.items() if kinds[c] is WealthKind.DEBT), ZERO)
        gross.append(g)
        debts.append(d)
        net = g - d
        change.append(net - previous if previous is not None and held else None)
        ratio.append((net - previous) / abs(previous) if previous and held else None)
        previous = net if held else None
    last_gross = gross[-1] if gross else ZERO
    shares: dict[UUID, Decimal] = {}
    line_shares: dict[UUID, Decimal] = {}
    if last_gross > 0:
        shares = {
            c: subtotals[-1] / last_gross
            for c, subtotals in by_category.items()
            if kinds[c] is WealthKind.ASSET
        }
        line_shares = {
            ln.id: cell.amount / last_gross
            for ln in lines
            if kinds[ln.category_id] is WealthKind.ASSET and (cell := by_line[ln.id][-1])
        }
    return WealthMatrix(
        list(months),
        by_line,
        by_category,
        gross,
        debts,
        [g - d for g, d in zip(gross, debts, strict=True)],
        change,
        ratio,
        shares,
        line_shares,
    )


def _net(
    cells: Mapping[UUID, Cell | None], lines: Sequence[LineInput], kinds: Mapping[UUID, WealthKind]
) -> Decimal:
    total = ZERO
    for ln in lines:
        cell = cells[ln.id]
        if cell is not None:
            total += -cell.amount if kinds[ln.category_id] is WealthKind.DEBT else cell.amount
    return total


def month_end_balances(
    opening_balance: Decimal,
    opening_date: date,
    movements: Mapping[Month, Decimal],
    *,
    last: Month,
) -> dict[Month, Decimal]:
    """A cash account's balance at the end of each month from its opening one to `last`
    (F-WLT-4): the opening balance plus every movement booked up to then, as
    kwak_core.balances.balance_on. Movements booked before the opening month count in it."""
    first = Month.of(opening_date)
    running = opening_balance + sum((a for m, a in movements.items() if m < first), ZERO)
    balances: dict[Month, Decimal] = {}
    month = first
    while month <= last:
        running += movements.get(month, ZERO)
        balances[month] = running
        month = month.next()
    return balances
