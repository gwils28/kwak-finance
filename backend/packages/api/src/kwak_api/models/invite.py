from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from kwak_api.db import Base, UUIDPrimaryKey
from kwak_api.models.household import Household


class Invite(UUIDPrimaryKey, Base):
    """A single-use link to join the household. Only the SHA-256 of the token is stored."""

    __tablename__ = "invite"

    household_id: Mapped[UUID] = mapped_column(ForeignKey("household.id"), index=True)
    created_by_id: Mapped[UUID] = mapped_column(ForeignKey("app_user.id", ondelete="CASCADE"))
    # The account created from this invite gets this email: a leaked link cannot pick another.
    email: Mapped[str] = mapped_column(String(320), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    household: Mapped[Household] = relationship()
