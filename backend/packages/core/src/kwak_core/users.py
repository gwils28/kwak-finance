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
