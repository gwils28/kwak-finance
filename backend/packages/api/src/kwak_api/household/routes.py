"""Household members and invitations."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from kwak_core.invites import InviteState
from pydantic import BaseModel
from sqlalchemy import select

from kwak_api.auth.routes import CurrentSession, Db, Now
from kwak_api.models import Invite, Role, User, UserSession
from kwak_api.services import invites as service

router = APIRouter(prefix="/api", tags=["household"])

INVALID_LINK = HTTPException(status.HTTP_404_NOT_FOUND, "this invitation is invalid or has expired")


def owner_session(user_session: CurrentSession) -> UserSession:
    if user_session.user.role is not Role.OWNER:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "only the household owner can do this")
    return user_session


OwnerSession = Annotated[UserSession, Depends(owner_session)]


class MemberOut(BaseModel):
    id: UUID
    display_name: str
    email: str
    role: Role


class InviteCreate(BaseModel):
    email: str


class InviteOut(BaseModel):
    id: UUID
    email: str
    state: InviteState
    created_at: datetime
    expires_at: datetime

    @classmethod
    def of(cls, invite: Invite, now: datetime) -> "InviteOut":
        return cls(
            id=invite.id,
            email=invite.email,
            state=service.state_of(invite, now),
            created_at=invite.created_at,
            expires_at=invite.expires_at,
        )


class InviteCreated(BaseModel):
    invite: InviteOut
    token: str
    """Shown once: the SPA builds the link /invite/<token> from it."""


class InvitePreview(BaseModel):
    email: str
    household_name: str
    expires_at: datetime


class InviteAccept(BaseModel):
    display_name: str
    password: str


@router.get("/household/members")
def list_members(user_session: CurrentSession, db: Db) -> list[MemberOut]:
    members = db.scalars(
        select(User)
        .where(User.household_id == user_session.user.household_id, User.is_active)
        .order_by(User.display_name)
    )
    return [
        MemberOut(id=m.id, display_name=m.display_name, email=m.email, role=m.role) for m in members
    ]


@router.post("/invites", status_code=status.HTTP_201_CREATED)
def create_invite(
    body: InviteCreate, user_session: OwnerSession, db: Db, now: Now
) -> InviteCreated:
    try:
        token, invite = service.create_invite(db, user_session.user, body.email, now)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None
    except service.EmailTakenError:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "an account already uses this email"
        ) from None
    return InviteCreated(invite=InviteOut.of(invite, now), token=token)


@router.get("/invites")
def list_invites(user_session: OwnerSession, db: Db, now: Now) -> list[InviteOut]:
    invites = service.pending_invites(db, user_session.user.household_id, now)
    return [InviteOut.of(i, now) for i in invites]


@router.delete("/invites/{invite_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_invite(invite_id: UUID, user_session: OwnerSession, db: Db, now: Now) -> None:
    if not service.revoke_invite(db, user_session.user.household_id, invite_id, now):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no pending invitation with this id")


@router.get("/invites/accept/{token}")
def preview_invite(token: str, db: Db, now: Now) -> InvitePreview:
    """Public: what the invitee sees before choosing a password."""
    invite = service.find_pending(db, token, now)
    if invite is None:
        raise INVALID_LINK
    return InvitePreview(
        email=invite.email, household_name=invite.household.name, expires_at=invite.expires_at
    )


@router.post("/invites/accept/{token}", status_code=status.HTTP_201_CREATED)
def accept_invite(token: str, body: InviteAccept, db: Db, now: Now) -> MemberOut:
    """Public: create the member account. The new member signs in and sets up TOTP next."""
    try:
        member = service.accept_invite(
            db, token, display_name=body.display_name, password=body.password, now=now
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None
    except service.EmailTakenError:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "an account already uses this email"
        ) from None
    if member is None:
        raise INVALID_LINK
    return MemberOut(
        id=member.id, display_name=member.display_name, email=member.email, role=member.role
    )
