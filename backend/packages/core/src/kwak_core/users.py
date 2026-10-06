"""User identity rules."""


def normalize_email(value: str) -> str:
    """Canonical form used for storage and login lookup: trimmed and lowercased.

    Only rejects obvious garbage; deliverability is checked by the invite flow.
    """
    email = value.strip().lower()
    local, at, domain = email.rpartition("@")
    if not at or not local or not domain or any(c.isspace() for c in email):
        raise ValueError(f"invalid email address: {value!r}")
    return email


PASSWORD_MIN_LENGTH = 12
# Bounds argon2 work on hostile input.
PASSWORD_MAX_LENGTH = 256


def check_password_policy(password: str) -> None:
    """Length is the only rule (NIST SP 800-63B): no composition rules."""
    if len(password) < PASSWORD_MIN_LENGTH:
        raise ValueError(f"password must be at least {PASSWORD_MIN_LENGTH} characters")
    if len(password) > PASSWORD_MAX_LENGTH:
        raise ValueError(f"password must be at most {PASSWORD_MAX_LENGTH} characters")
