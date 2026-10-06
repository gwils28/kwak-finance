import pytest
from hypothesis import given
from hypothesis import strategies as st
from kwak_core.users import normalize_email


def test_normalize_email_strips_and_lowercases() -> None:
    assert normalize_email("  Alice.Doe@Example.COM \n") == "alice.doe@example.com"


@given(st.emails())
def test_normalize_email_is_idempotent(email: str) -> None:
    once = normalize_email(email)
    assert normalize_email(once) == once


@pytest.mark.parametrize("value", ["", "   ", "no-at-sign", "@example.com", "alice@"])
def test_normalize_email_rejects_malformed_addresses(value: str) -> None:
    with pytest.raises(ValueError, match="email"):
        normalize_email(value)
