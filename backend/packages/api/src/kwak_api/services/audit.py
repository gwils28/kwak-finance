"""The activity log (F-ADM-3): entries are added in the same database transaction as the
action, so an action that fails leaves none."""

from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from kwak_core.accounts import Visibility
from kwak_core.audit import AuditAction, AuditKind
from sqlalchemy import ColumnElement, func, or_, select, true
from sqlalchemy.orm import Session, joinedload

from kwak_api.models import Account, AuditEvent, Role, User

type Detail = str | int | None


def record(
    db: Session,
    user: User,
    action: AuditAction,
    now: datetime,
    *,
    accounts: Sequence[Account | None] = (),
    ip: str | None = None,
    **details: Detail | Decimal,
) -> None:
    """Add an entry by `user` about `accounts` (the first one's name is kept). An entry about
    a private account, even as the other side of a transfer, is only shown to its owner."""
    kept: dict[str, Any] = {
        k: str(v) if isinstance(v, Decimal) else v for k, v in details.items() if v is not None
    }
    involved = [a for a in accounts if a is not None]
    if involved:
        kept["account"] = involved[0].name
    private = next((a for a in involved if a.visibility is Visibility.PRIVATE), None)
    db.add(
        AuditEvent(
            household_id=user.household_id,
            user_id=user.id,
            at=now,
            action=action,
            private_to=private.owner_id if private else None,
            ip=ip,
            details=kept,
        )
    )


def _visible(viewer: User) -> ColumnElement[bool]:
    """The SQL form of kwak_core.audit.can_see."""
    return (
        (AuditEvent.household_id == viewer.household_id)
        & or_(AuditEvent.private_to.is_(None), AuditEvent.private_to == viewer.id)
        & (true() if viewer.role is Role.OWNER else AuditEvent.user_id == viewer.id)
    )


def entries(
    db: Session,
    viewer: User,
    *,
    kind: AuditKind | None = None,
    author: UUID | None = None,
    limit: int,
    offset: int,
) -> tuple[list[AuditEvent], int]:
    """The entries `viewer` may see, newest first, and how many there are."""
    query = select(AuditEvent).where(_visible(viewer))
    if kind is not None:
        query = query.where(AuditEvent.action.in_([a for a in AuditAction if a.kind is kind]))
    if author is not None:
        query = query.where(AuditEvent.user_id == author)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    page = db.scalars(
        query.options(joinedload(AuditEvent.user))
        .order_by(AuditEvent.at.desc(), AuditEvent.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(page), total
