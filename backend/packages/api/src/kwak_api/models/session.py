from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from kwak_api.db import Base, UUIDPrimaryKey
from kwak_api.models.household import User


class UserSession(UUIDPrimaryKey, Base):
    """A login session. Only the SHA-256 of the cookie token is stored."""

    __tablename__ = "user_session"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("app_user.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    csrf_token: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Set once the second factor is checked; until then only the TOTP endpoints accept it.
    mfa_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # F-ADM-5: the demo's owner, while the session is in the demo; reset or gone, it leaves.
    acting_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("app_user.id", ondelete="SET NULL"), index=True
    )

    account: Mapped[User] = relationship(foreign_keys=[user_id])
    """Who signed in: whose password, second factor, recovery codes and language these are."""
    acting_user: Mapped[User | None] = relationship(foreign_keys=[acting_user_id])

    @property
    def user(self) -> User:
        """Whom the session acts as: the demo's owner in the demo, otherwise the account."""
        return self.acting_user or self.account

    @property
    def viewer_id(self) -> UUID:
        """The id of `user`, without loading it."""
        return self.acting_user_id or self.user_id
