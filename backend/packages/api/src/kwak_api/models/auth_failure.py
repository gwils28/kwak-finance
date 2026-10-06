from datetime import datetime

from sqlalchemy import DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from kwak_api.db import Base, UUIDPrimaryKey


class AuthFailure(UUIDPrimaryKey, Base):
    """A failed login or TOTP attempt, counted by kwak_api.auth.throttle."""

    __tablename__ = "auth_failure"
    __table_args__ = (Index("ix_auth_failure_subject_occurred_at", "subject", "occurred_at"),)

    # What is being limited: "password:<email>", "ip:<address>" or "totp:<user id>".
    subject: Mapped[str] = mapped_column(String(400))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
