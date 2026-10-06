from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from kwak_api.db import Base, UUIDPrimaryKey


class RecoveryCode(UUIDPrimaryKey, Base):
    """A one-time TOTP replacement. Only the SHA-256 of the code is stored."""

    __tablename__ = "recovery_code"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("app_user.id", ondelete="CASCADE"), index=True)
    code_hash: Mapped[str] = mapped_column(String(64), unique=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
