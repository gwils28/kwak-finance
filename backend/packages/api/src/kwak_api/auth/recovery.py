from datetime import datetime

from kwak_core.recovery import generate_recovery_codes, hash_recovery_code, normalize_recovery_code
from sqlalchemy import delete, update
from sqlalchemy.orm import Session

from kwak_api.models import RecoveryCode, User


def issue_recovery_codes(db: Session, user: User) -> list[str]:
    """Replace all the user's codes and return the new ones (shown once)."""
    codes = generate_recovery_codes()
    db.execute(delete(RecoveryCode).where(RecoveryCode.user_id == user.id))
    db.add_all(
        RecoveryCode(
            user_id=user.id, code_hash=hash_recovery_code(normalize_recovery_code(c) or "")
        )
        for c in codes
    )
    db.flush()
    return codes


def use_recovery_code(db: Session, user: User, typed: str, now: datetime) -> bool:
    """Spend an unused code. A single UPDATE, so two concurrent uses cannot both succeed."""
    canonical = normalize_recovery_code(typed)
    if canonical is None:
        return False
    spent = db.execute(
        update(RecoveryCode)
        .where(
            RecoveryCode.user_id == user.id,
            RecoveryCode.code_hash == hash_recovery_code(canonical),
            RecoveryCode.used_at.is_(None),
        )
        .values(used_at=now)
        .returning(RecoveryCode.id)
    ).first()
    return spent is not None
