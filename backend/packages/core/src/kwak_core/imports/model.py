"""What a bank file parser produces, whatever the bank."""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class ParsedRow:
    line: int
    """1-based line in the file, for error messages and the import preview."""
    booked_on: date
    label: str
    """The most detailed label the bank gives."""
    amount: Decimal
    """Negative = outflow."""


@dataclass(frozen=True)
class RowError:
    line: int
    """0 for a problem with the whole file."""
    message: str


@dataclass(frozen=True)
class Balance:
    on: date
    amount: Decimal


@dataclass
class Statement:
    rows: list[ParsedRow] = field(default_factory=list)
    errors: list[RowError] = field(default_factory=list)
    period: tuple[date, date] | None = None
    """Dates the export covers, when the file states them."""
    balance: Balance | None = None
    """Account balance the bank reports, usable as a reconciliation checkpoint."""


@dataclass(frozen=True)
class BankFormat:
    key: str
    """Stable identifier, stored with each import."""
    label: str
    matches: Callable[[list[str]], bool]
    """True if the file's first lines are in this format."""
    parse: Callable[[list[str]], Statement]
