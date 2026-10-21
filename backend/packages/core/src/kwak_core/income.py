"""The household's monthly income (F-INC-1, invariant §8.5): one amount, carried forward."""

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal

from kwak_core.budget import Month
from kwak_core.money import require_cents


@dataclass(frozen=True)
class Income:
    amount: Decimal
    carried: bool
    """No income entered this month: the previous one carried forward."""


def check_income(amount: Decimal) -> Decimal:
    if amount < 0:
        raise ValueError("an income is zero or more")
    return require_cents(amount)


def income_of(month: Month, entered: Mapping[Month, Decimal]) -> Income | None:
    """The income entered in `month`, else the latest one before it; none before the first."""
    if month in entered:
        return Income(entered[month], carried=False)
    earlier = [m for m in entered if m < month]
    return Income(entered[max(earlier)], carried=True) if earlier else None
