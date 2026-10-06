"""TOTP enrollment and verification for a user, with the seed encrypted at rest."""

from datetime import datetime

from kwak_core.totp import generate_secret, match_totp

from kwak_api.auth.crypto import SecretBox
from kwak_api.models import User


def start_enrollment(user: User, box: SecretBox) -> bytes:
    """Give the user a new, unconfirmed seed and return it (shown once, as a QR code)."""
    secret = generate_secret()
    user.totp_secret_enc = box.encrypt(secret, user.id)
    user.totp_confirmed_at = None
    user.totp_last_counter = None
    return secret


def check_code(user: User, box: SecretBox, code: str, now: datetime) -> bool:
    """True if the code is valid and unused. Records it so it cannot be replayed."""
    if user.totp_secret_enc is None:
        return False
    secret = box.decrypt(user.totp_secret_enc, user.id)
    counter = match_totp(
        secret, code, unix_time=int(now.timestamp()), last_counter=user.totp_last_counter
    )
    if counter is None:
        return False
    user.totp_last_counter = counter
    return True
