"""Household invitations: the owner creates a single-use link, the invitee sets a password."""

import secrets
from datetime import datetime
from uuid import UUID

from kwak_core.invites import INVITE_LIFETIME, InviteState, invite_state
from kwak_core.users import check_password_policy, normalize_email
from sqlalchemy import exists, select, update
from sqlalchemy.orm import Session

from kwak_api.auth.passwords import hash_password
from kwak_api.auth.sessions import hash_token
from kwak_api.models import Invite, Role, User


class EmailTakenError(Exception):
    """An account already uses this email."""


def _email_taken(db: Session, email: str) -> bool:
    return bool(db.scalar(select(exists().where(User.email == email))))


def state_of(invite: Invite, now: datetime) -> InviteState:
    return invite_state(
        now=now,
        expires_at=invite.expires_at,
        accepted_at=invite.accepted_at,
        revoked_at=invite.revoked_at,
    )


def create_invite(db: Session, owner: User, email: str, now: datetime) -> tuple[str, Invite]:
    """Return the link token (never stored) and the invite. Replaces a pending one for the email."""
    email = normalize_email(email)
    if _email_taken(db, email):
        raise EmailTakenError(email)
    db.execute(
        update(Invite)
        .where(
            Invite.household_id == owner.household_id,
            Invite.email == email,
            Invite.accepted_at.is_(None),
            Invite.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    token = secrets.token_urlsafe(32)
    invite = Invite(
        household_id=owner.household_id,
        created_by_id=owner.id,
        email=email,
        token_hash=hash_token(token),
        created_at=now,
        expires_at=now + INVITE_LIFETIME,
    )
    db.add(invite)
    db.flush()
    return token, invite


def find_pending(db: Session, token: str, now: datetime) -> Invite | None:
    invite = db.scalar(select(Invite).where(Invite.token_hash == hash_token(token)))
    if invite is None or state_of(invite, now) is not InviteState.PENDING:
        return None
    return invite


def accept_invite(
    db: Session, token: str, *, display_name: str, password: str, now: datetime
) -> User | None:
    """Create the member account, or return None if the link is not usable.

    Input is checked before the invite is spent, so a rejected password keeps the link valid.
    The invite is spent by a single UPDATE: two concurrent acceptances cannot both succeed.
    """
    check_password_policy(password)
    display_name = display_name.strip()
    if not display_name:
        raise ValueError("display name is required")
    spent = db.execute(
        update(Invite)
        .where(
            Invite.token_hash == hash_token(token),
            Invite.accepted_at.is_(None),
            Invite.revoked_at.is_(None),
            Invite.expires_at > now,
        )
        .values(accepted_at=now)
        .returning(Invite.household_id, Invite.email)
    ).first()
    if spent is None:
        return None
    household_id, email = spent
    if _email_taken(db, email):
        raise EmailTakenError(email)
    member = User(
        household_id=household_id,
        email=email,
        display_name=display_name,
        password_hash=hash_password(password),
        role=Role.MEMBER,
    )
    db.add(member)
    db.flush()
    return member


def pending_invites(db: Session, household_id: UUID, now: datetime) -> list[Invite]:
    invites = db.scalars(
        select(Invite).where(Invite.household_id == household_id).order_by(Invite.created_at)
    )
    return [i for i in invites if state_of(i, now) is InviteState.PENDING]


def revoke_invite(db: Session, household_id: UUID, invite_id: UUID, now: datetime) -> bool:
    revoked = db.execute(
        update(Invite)
        .where(
            Invite.id == invite_id,
            Invite.household_id == household_id,
            Invite.accepted_at.is_(None),
            Invite.revoked_at.is_(None),
        )
        .values(revoked_at=now)
        .returning(Invite.id)
    ).first()
    return revoked is not None
