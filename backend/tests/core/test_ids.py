from uuid import UUID

from hypothesis import given
from hypothesis import strategies as st
from kwak_core.ids import uuid7

MAX_MS = 2**48 - 1
timestamps = st.integers(min_value=0, max_value=MAX_MS)
rand_bytes = st.binary(min_size=10, max_size=10)


@given(timestamps, rand_bytes)
def test_uuid7_sets_version_and_rfc_variant(unix_ms: int, rand: bytes) -> None:
    value = uuid7(unix_ms=unix_ms, rand=rand)
    assert value.version == 7
    assert value.variant == "specified in RFC 4122"


@given(timestamps, rand_bytes)
def test_uuid7_embeds_the_timestamp_in_the_first_48_bits(unix_ms: int, rand: bytes) -> None:
    assert uuid7(unix_ms=unix_ms, rand=rand).int >> 80 == unix_ms


@given(timestamps, timestamps, rand_bytes, rand_bytes)
def test_uuid7_sorts_by_timestamp(t1: int, t2: int, r1: bytes, r2: bytes) -> None:
    if t1 < t2:
        assert uuid7(unix_ms=t1, rand=r1) < uuid7(unix_ms=t2, rand=r2)


def test_uuid7_defaults_to_now_and_random_bits() -> None:
    a, b = uuid7(), uuid7()
    assert isinstance(a, UUID)
    assert a != b
    assert a.version == 7
