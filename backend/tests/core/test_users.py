import pytest
from hypothesis import given
from hypothesis import strategies as st
from kwak_core.users import check_password_policy, normalize_email


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


@pytest.mark.parametrize("password", ["", "short", "x" * 11, "x" * 257])
def test_password_policy_rejects_too_short_or_too_long(password: str) -> None:
    with pytest.raises(ValueError, match="password"):
        check_password_policy(password)


@given(st.text(min_size=12, max_size=256))
def test_password_policy_accepts_12_to_256_characters(password: str) -> None:
    check_password_policy(password)
