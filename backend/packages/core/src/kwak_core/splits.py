"""Split transactions (F-TX-4, invariant §8.2).

A transaction spread over several categories: the user gives every part but the last, which
takes the rest, so the parts always add up exactly to the transaction.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID


@dataclass(frozen=True)
class Part:
    category_id: UUID | None
    """None: to categorise (its category was deleted, or not chosen yet)."""
    amount: Decimal
    """Signed, as the transaction's."""


class SplitError(ValueError):
    """The parts cannot split this amount."""


def _check(amount: Decimal, parts: Sequence[Part]) -> None:
    for part in parts:
        if part.amount == 0:
            raise SplitError("a part cannot be zero")
        if (part.amount < 0) != (amount < 0):
            raise SplitError("every part has the sign of the transaction")


def split(amount: Decimal, given: Sequence[Part], rest_category: UUID | None) -> list[Part]:
    """The given parts, then a last part in `rest_category` for what is left."""
    if not given:
        raise SplitError("a split needs at least two parts")
    _check(amount, given)
    rest = amount - sum((p.amount for p in given), Decimal(0))
    if rest == 0 or (rest < 0) != (amount < 0):
        raise SplitError("the rest for the last part must be of the transaction's sign")
    return [*given, Part(rest_category, rest)]


def resize(parts: Sequence[Part], amount: Decimal) -> list[Part]:
    """The parts of a transaction whose amount changes: the last part takes the difference."""
    *given, last = parts
    return split(amount, given, last.category_id)
