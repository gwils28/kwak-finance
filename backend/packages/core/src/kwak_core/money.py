"""Money primitives. Amounts are EUR ``Decimal`` with 2 places; negative means outflow."""

from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")


def quantize(amount: Decimal) -> Decimal:
    """Round to cents, half away from zero (the convention used on French bank statements)."""
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)


def require_cents(amount: Decimal) -> Decimal:
    """Validate a user-entered amount: finite, at most 2 decimals. Never rounds silently."""
    if not amount.is_finite() or amount != quantize(amount):
        raise ValueError(f"amount must be a whole number of cents: {amount}")
    return quantize(amount)
