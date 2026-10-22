from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st
from kwak_core.money import quantize, require_cents


def test_quantize_rounds_half_up_to_cents() -> None:
    assert quantize(Decimal("0.005")) == Decimal("0.01")
    assert quantize(Decimal("-0.005")) == Decimal("-0.01")
    assert quantize(Decimal("2.344")) == Decimal("2.34")


cents = st.integers(min_value=-(10**12), max_value=10**12)


@given(cents)
def test_quantize_is_idempotent_on_cents(value: int) -> None:
    amount = Decimal(value).scaleb(-2)
    assert quantize(amount) == amount
    assert quantize(quantize(amount)) == quantize(amount)


@pytest.mark.parametrize("raw", ["0", "12.3", "-1234.56", "1e3"])
def test_require_cents_accepts_at_most_two_decimals(raw: str) -> None:
    assert require_cents(Decimal(raw)) == quantize(Decimal(raw))


@pytest.mark.parametrize("raw", ["12.345", "0.001", "NaN", "Infinity"])
def test_require_cents_rejects_sub_cent_or_non_finite_amounts(raw: str) -> None:
    with pytest.raises(ValueError, match="cents"):
        require_cents(Decimal(raw))
