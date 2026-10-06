"""One-time recovery codes, used instead of a TOTP code when the authenticator is lost.

Each code is 80 random bits, so a plain SHA-256 is enough to store it: unlike a
password, it cannot be guessed from its hash.
"""

import base64
import hashlib
import os
import re

RECOVERY_CODE_COUNT = 10
_CODE_BYTES = 10  # 80 bits, exactly 16 base32 characters
_CANONICAL = re.compile(r"^[a-z2-7]{16}$")


def generate_recovery_codes() -> list[str]:
    """Codes as shown to the user: `abcd-efgh-ijkl-mnop`."""
    codes = []
    for _ in range(RECOVERY_CODE_COUNT):
        raw = base64.b32encode(os.urandom(_CODE_BYTES)).decode().lower()
        codes.append("-".join(raw[i : i + 4] for i in range(0, 16, 4)))
    return codes


def normalize_recovery_code(typed: str) -> str | None:
    """Canonical form (16 characters, no dashes) of what the user typed, or None."""
    code = re.sub(r"[\s-]", "", typed).lower()
    return code if _CANONICAL.match(code) else None


def hash_recovery_code(canonical: str) -> str:
    return hashlib.sha256(canonical.encode()).hexdigest()
