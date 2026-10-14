from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query
from kwak_core.audit import AuditAction, AuditKind
from pydantic import BaseModel

from kwak_api.auth.routes import CurrentSession, Db
from kwak_api.models import AuditEvent
from kwak_api.services import audit as service

router = APIRouter(prefix="/api", tags=["audit"])


class AuditEntryOut(BaseModel):
    id: UUID
    at: datetime
    action: AuditAction
    kind: AuditKind
    user_id: UUID | None
    """Who did it; null once their account is removed."""
    user_name: str | None
    ip: str | None
    """The client's address, for sign-in entries."""
    details: dict[str, str | int]
    """Frozen at the time: label, amount, date, account, file, category, count…"""

    @classmethod
    def of(cls, event: AuditEvent) -> "AuditEntryOut":
        return cls(
            id=event.id,
            at=event.at,
            action=event.action,
            kind=event.action.kind,
            user_id=event.user_id,
            user_name=event.user.display_name if event.user else None,
            ip=event.ip,
            details=event.details,
        )


class AuditPage(BaseModel):
    items: list[AuditEntryOut]
    """Newest first."""
    total: int


@router.get("/audit")
def activity_log(
    user_session: CurrentSession,
    db: Db,
    kind: AuditKind | None = None,
    user_id: Annotated[UUID | None, Query(description="Only this member's entries")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AuditPage:
    """The activity log (F-ADM-3): the owner sees the household's, a member their own;
    an entry about a private account is only shown to its owner."""
    items, total = service.entries(
        db, user_session.user, kind=kind, author=user_id, limit=limit, offset=offset
    )
    return AuditPage(items=[AuditEntryOut.of(e) for e in items], total=total)
