"""Time-based one-time passwords (RFC 4226 HOTP, RFC 6238 TOTP), HMAC-SHA1, 30 s steps.

SHA-1 and 6 digits are what every authenticator app supports.
"""

import base64
import hashlib
import hmac
import os
from urllib.parse import quote, urlencode

STEP = 30
DIGITS = 6
SECRET_BYTES = 20
# Accept codes from one step before or after now, for clock drift.
DRIFT_STEPS = 1


def generate_secret() -> bytes:
    return os.urandom(SECRET_BYTES)


def hotp(secret: bytes, counter: int, digits: int = DIGITS) -> str:
    digest = hmac.digest(secret, counter.to_bytes(8), hashlib.sha1)
    offset = digest[-1] & 0x0F
    value = int.from_bytes(digest[offset : offset + 4]) & 0x7FFFFFFF
    return str(value % 10**digits).zfill(digits)


def match_totp(secret: bytes, code: str, *, unix_time: int, last_counter: int | None) -> int | None:
    """Return the time step the code belongs to, or None.

    A code is rejected if its step is not after `last_counter`, the step of the last
    accepted code, so a code cannot be replayed.
    """
    if len(code) != DIGITS or not code.isascii() or not code.isdigit():
        return None
    now = unix_time // STEP
    for counter in range(now - DRIFT_STEPS, now + DRIFT_STEPS + 1):
        if last_counter is not None and counter <= last_counter:
            continue
        if hmac.compare_digest(hotp(secret, counter), code):
            return counter
    return None


def provisioning_uri(secret: bytes, *, account: str, issuer: str) -> str:
    """Key URI for authenticator apps (shown as a QR code)."""
    label = quote(f"{issuer}:{account}", safe=":")
    query = urlencode(
        {"secret": base64.b32encode(secret).decode().rstrip("="), "issuer": issuer},
        quote_via=quote,
    )
    return f"otpauth://totp/{label}?{query}"
