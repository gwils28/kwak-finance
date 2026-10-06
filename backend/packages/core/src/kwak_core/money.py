"""Money primitives. Amounts are EUR ``Decimal`` with 2 places; negative means outflow."""

import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Literal

CENT = Decimal("0.01")

DecimalSeparator = Literal[",", "."]

# Characters banks use as thousands separators or decoration around amounts.
_NOISE = re.compile(r"[\s\u00a0\u202f'\u20ac]|EUR", re.IGNORECASE)


def quantize(amount: Decimal) -> Decimal:
    """Round to cents, half away from zero (the convention used on French bank statements)."""
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)


def parse_amount(raw: str, *, decimal_separator: DecimalSeparator) -> Decimal:
    """Parse a bank-export amount string into a quantized ``Decimal``.

    The decimal separator comes from the import profile: it cannot be guessed reliably
    (``1.234`` is ambiguous).
    """
    text = _NOISE.sub("", raw)
    negative = text.startswith("(") and text.endswith(")")
    if negative:
        text = text[1:-1]
    thousands = "." if decimal_separator == "," else ","
    t, d = re.escape(thousands), re.escape(decimal_separator)
    if not re.fullmatch(rf"[+-]?(\d+|\d{{1,3}}({t}\d{{3}})+)({d}\d+)?", text):
        raise ValueError(f"Unparseable amount: {raw!r}")
    text = text.replace(thousands, "").replace(decimal_separator, ".")
    try:
        value = Decimal(text)
    except InvalidOperation as exc:  # pragma: no cover - guarded by the regex
        raise ValueError(f"Unparseable amount: {raw!r}") from exc
    return quantize(-value if negative else value)


def require_cents(amount: Decimal) -> Decimal:
    """Validate a user-entered amount: finite, at most 2 decimals. Never rounds silently."""
    if not amount.is_finite() or amount != quantize(amount):
        raise ValueError(f"amount must be a whole number of cents: {amount}")
    return quantize(amount)
