from datetime import datetime
from typing import Any
from uuid import UUID

from kwak_core.audit import AuditAction
from sqlalchemy import DateTime, Enum, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from kwak_api.db import Base, UUIDPrimaryKey
from kwak_api.models.household import User


class AuditEvent(UUIDPrimaryKey, Base):
    """One entry of the activity log (F-ADM-3). Never updated: the app only adds and reads."""

    __tablename__ = "audit_event"
    __table_args__ = (Index("ix_audit_event_household_id_at", "household_id", "at"),)

    household_id: Mapped[UUID] = mapped_column(ForeignKey("household.id", ondelete="CASCADE"))
    user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("app_user.id", ondelete="SET NULL"), index=True
    )
    """Who did it."""
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    action: Mapped[AuditAction] = mapped_column(
        Enum(
            AuditAction,
            name="audit_action",
            native_enum=False,
            create_constraint=True,
            length=40,
            values_callable=lambda actions: [a.value for a in actions],
        )
    )
    # About a private wealth line or goal: only its owner sees the entry. Gone with that owner.
    private_to: Mapped[UUID | None] = mapped_column(
        ForeignKey("app_user.id", ondelete="CASCADE"), index=True
    )
    ip: Mapped[str | None] = mapped_column(String(45))
    """The client's address, for sign-in entries."""
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    """A short description frozen at the time: label, amount, file name, count…"""

    user: Mapped[User | None] = relationship(foreign_keys=[user_id])
