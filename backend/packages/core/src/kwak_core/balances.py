"""Cash account balances (F-WLT-1, invariant §8.1)."""

from collections.abc import Iterable
from datetime import date
from decimal import Decimal


def balance_on(
    opening_balance: Decimal, movements: Iterable[tuple[date, Decimal]], *, on: date
) -> Decimal:
    """Balance at the end of `on`: the opening balance plus every movement booked up to that day.

    Movements booked before the account's opening date must not exist: the opening balance
    already includes them (the import rejects them).
    """
    return opening_balance + sum((amount for when, amount in movements if when <= on), Decimal(0))
