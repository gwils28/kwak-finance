"""Time-ordered identifiers (UUIDv7, RFC 9562). Python 3.13 has no `uuid.uuid7`."""

import os
import time
from uuid import UUID

_RAND_BYTES = 10


def uuid7(*, unix_ms: int | None = None, rand: bytes | None = None) -> UUID:
    """Return a UUIDv7: 48-bit Unix milliseconds, then 74 random bits.

    `unix_ms` and `rand` exist so tests can pin the inputs.
    """
    if unix_ms is None:
        unix_ms = time.time_ns() // 1_000_000
    if rand is None:
        rand = os.urandom(_RAND_BYTES)
    if not 0 <= unix_ms < 2**48:
        raise ValueError(f"unix_ms out of range: {unix_ms}")
    if len(rand) != _RAND_BYTES:
        raise ValueError(f"rand must be {_RAND_BYTES} bytes")

    bits = int.from_bytes(rand)
    rand_a = bits >> 68  # 12 bits
    rand_b = bits & (2**62 - 1)  # 62 bits
    value = (unix_ms << 80) | (0x7 << 76) | (rand_a << 64) | (0b10 << 62) | rand_b
    return UUID(int=value)
