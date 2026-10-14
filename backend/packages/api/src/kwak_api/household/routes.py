"""Household members and invitations."""

import re
from datetime import datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from kwak_core.audit import AuditAction
from kwak_core.budget import Month
from kwak_core.invites import InviteState
from kwak_core.progress import check_warn_at
from pydantic import AfterValidator, BaseModel, Field
from sqlalchemy import select

from kwak_api.auth.routes import CurrentSession, Db, Now
from kwak_api.models import Household, Invite, Role, User, UserSession
from kwak_api.services import audit
from kwak_api.services import invites as service

router = APIRouter(prefix="/api", tags=["household"])

MONTH = re.compile(r"[0-9]{4}-[0-9]{2}")

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


class SettingsOut(BaseModel):
    warn_at: Decimal
    """The share of a monthly target from which a category is to watch (F-BUD-2)."""
    analysis_start: str | None
    """YYYY-MM: the first month analyses count (F-ADM-4); null: every month."""

    @classmethod
    def of(cls, household: Household) -> "SettingsOut":
        start = household.analysis_start
        return cls(
            warn_at=household.warn_at, analysis_start=start.strftime("%Y-%m") if start else None
        )


def _month(value: str) -> str:
    month = Month.parse(value) if MONTH.fullmatch(value) else None
    if month is None or month.year < 1900:
        raise ValueError("expected a month as YYYY-MM")
    return str(month)


def _warn_at(value: Decimal) -> Decimal:
    check_warn_at(value)
    return value.quantize(Decimal("0.01"))


class SettingsPatch(BaseModel):
    warn_at: Annotated[Decimal, Field(decimal_places=2), AfterValidator(_warn_at)] | None = None
    """From 0.50 to 1, in whole percents. Leave it out to keep it."""
    analysis_start: Annotated[str, AfterValidator(_month)] | None = None
    """YYYY-MM; null to count every month. Leave it out to keep it."""


@router.get("/household/settings")
def get_settings(user_session: CurrentSession, db: Db) -> SettingsOut:
    return SettingsOut.of(db.get_one(Household, user_session.user.household_id))


@router.patch("/household/settings")
def update_settings(
    body: SettingsPatch, user_session: OwnerSession, db: Db, now: Now
) -> SettingsOut:
    household = db.get_one(Household, user_session.user.household_id)
    if body.warn_at is not None and body.warn_at != household.warn_at:
        household.warn_at = body.warn_at
        audit.record(db, user_session.user, AuditAction.SETTINGS_CHANGED, now, warn_at=body.warn_at)
    if "analysis_start" in body.model_fields_set:
        if body.analysis_start and Month.parse(body.analysis_start) > Month.of(now.date()):
            # It would empty every analysis until the month comes.
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, "the analyses cannot start in the future"
            )
        start = Month.parse(body.analysis_start).first_day() if body.analysis_start else None
        if start != household.analysis_start:
            household.analysis_start = start
            audit.record(
                db,
                user_session.user,
                AuditAction.SETTINGS_CHANGED,
                now,
                analysis_start=body.analysis_start or "",
            )
    db.flush()
    return SettingsOut.of(household)


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
    audit.record(db, user_session.user, AuditAction.INVITE_CREATED, now, email=invite.email)
    return InviteCreated(invite=InviteOut.of(invite, now), token=token)


@router.get("/invites")
def list_invites(user_session: OwnerSession, db: Db, now: Now) -> list[InviteOut]:
    invites = service.pending_invites(db, user_session.user.household_id, now)
    return [InviteOut.of(i, now) for i in invites]


@router.delete("/invites/{invite_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_invite(invite_id: UUID, user_session: OwnerSession, db: Db, now: Now) -> None:
    email = service.revoke_invite(db, user_session.user.household_id, invite_id, now)
    if email is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no pending invitation with this id")
    audit.record(db, user_session.user, AuditAction.INVITE_REVOKED, now, email=email)


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
    audit.record(db, member, AuditAction.MEMBER_JOINED, now, email=member.email)
    return MemberOut(
        id=member.id, display_name=member.display_name, email=member.email, role=member.role
    )
