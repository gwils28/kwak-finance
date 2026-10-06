from urllib.parse import parse_qs, urlsplit

import pytest
from hypothesis import given
from hypothesis import strategies as st
from kwak_core.totp import STEP, generate_secret, hotp, match_totp, provisioning_uri

RFC_SECRET = b"12345678901234567890"


# RFC 6238 appendix B, SHA-1 column.
@pytest.mark.parametrize(
    ("unix_time", "code"),
    [
        (59, "94287082"),
        (1111111109, "07081804"),
        (1111111111, "14050471"),
        (1234567890, "89005924"),
        (2000000000, "69279037"),
        (20000000000, "65353130"),
    ],
)
def test_rfc6238_vectors(unix_time: int, code: str) -> None:
    assert hotp(RFC_SECRET, unix_time // STEP, digits=8) == code


def test_rfc4226_vectors() -> None:
    expected = ["755224", "287082", "359152", "969429", "338314"]
    assert [hotp(RFC_SECRET, c) for c in range(5)] == expected


def test_match_accepts_one_step_of_clock_drift_each_way() -> None:
    now = 1_700_000_000
    counter = now // STEP
    for drift in (-1, 0, 1):
        code = hotp(RFC_SECRET, counter + drift)
        assert match_totp(RFC_SECRET, code, unix_time=now, last_counter=None) == counter + drift
    assert (
        match_totp(RFC_SECRET, hotp(RFC_SECRET, counter + 2), unix_time=now, last_counter=None)
        is None
    )


def test_match_rejects_a_replayed_or_older_code() -> None:
    now = 1_700_000_000
    counter = now // STEP
    code = hotp(RFC_SECRET, counter)
    assert match_totp(RFC_SECRET, code, unix_time=now, last_counter=counter) is None
    assert match_totp(RFC_SECRET, code, unix_time=now, last_counter=counter - 1) == counter


@pytest.mark.parametrize("code", ["", "12345", "1234567", "abcdef", " 123456"])
def test_match_rejects_malformed_codes(code: str) -> None:
    assert match_totp(RFC_SECRET, code, unix_time=1_700_000_000, last_counter=None) is None


@given(st.binary(min_size=20, max_size=20), st.integers(min_value=0, max_value=2**40))
def test_codes_are_six_digits(secret: bytes, counter: int) -> None:
    code = hotp(secret, counter)
    assert len(code) == 6
    assert code.isdigit()


def test_generate_secret_is_160_random_bits() -> None:
    a, b = generate_secret(), generate_secret()
    assert len(a) == 20
    assert a != b


def test_provisioning_uri_follows_the_key_uri_format() -> None:
    uri = provisioning_uri(RFC_SECRET, account="owner@example.com", issuer="Kwak Finance")
    parts = urlsplit(uri)
    assert (parts.scheme, parts.netloc) == ("otpauth", "totp")
    assert parts.path == "/Kwak%20Finance:owner%40example.com"
    query = parse_qs(parts.query)
    assert query["secret"] == ["GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"]
    assert query["issuer"] == ["Kwak Finance"]
