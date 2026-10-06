import re

import pytest
from hypothesis import given
from hypothesis import strategies as st
from kwak_core.recovery import (
    RECOVERY_CODE_COUNT,
    generate_recovery_codes,
    hash_recovery_code,
    normalize_recovery_code,
)

FORMAT = re.compile(r"^[a-z2-7]{4}(-[a-z2-7]{4}){3}$")


def test_codes_are_grouped_base32_and_distinct() -> None:
    codes = generate_recovery_codes()
    assert len(codes) == RECOVERY_CODE_COUNT == 10
    assert all(FORMAT.match(c) for c in codes)
    assert len(set(codes)) == len(codes)


@given(st.sampled_from([" ", "-", "  ", ""]), st.booleans())
def test_normalize_tolerates_spacing_dashes_and_case(sep: str, upper: bool) -> None:
    code = generate_recovery_codes()[0]
    typed = sep.join(code.split("-"))
    typed = typed.upper() if upper else typed
    assert normalize_recovery_code(f" {typed} ") == code.replace("-", "")


@pytest.mark.parametrize(
    "typed", ["", "abcd-efgh-ijkl", "abcd-efgh-ijkl-mnop-q", "abcd-efgh-ijkl-mno1"]
)
def test_normalize_rejects_malformed_codes(typed: str) -> None:
    assert normalize_recovery_code(typed) is None


def test_hash_is_stable_and_hides_the_code() -> None:
    code = normalize_recovery_code(generate_recovery_codes()[0])
    assert code is not None
    assert hash_recovery_code(code) == hash_recovery_code(code)
    assert code not in hash_recovery_code(code)
    assert len(hash_recovery_code(code)) == 64
