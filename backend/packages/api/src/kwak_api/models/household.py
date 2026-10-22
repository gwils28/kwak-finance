import enum
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from kwak_core.users import Language
from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    LargeBinary,
    Numeric,
    String,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from kwak_api.db import Base, Timestamps, UUIDPrimaryKey


class Household(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "household"
    __table_args__ = (
        CheckConstraint("warn_at BETWEEN 0.5 AND 1", name="warn_at_range"),
        CheckConstraint("extract(day from wealth_start) = 1", name="wealth_start_month"),
        CheckConstraint("precaution_share BETWEEN 0.5 AND 1", name="precaution_share_range"),
        CheckConstraint("goal_capacity >= 0", name="goal_capacity_positive"),
    )

    name: Mapped[str] = mapped_column(String(100))
    # F-BUD-2: the share of a monthly target from which a category is to watch.
    warn_at: Mapped[Decimal] = mapped_column(Numeric(3, 2), server_default=text("0.80"))
    # F-WLT-5: the first month the wealth matrix shows by default; NULL: no limit.
    wealth_start: Mapped[date | None] = mapped_column(Date)
    # F-GOAL-6: the share of the capacity kept for the precaution while it falls short.
    precaution_share: Mapped[Decimal] = mapped_column(Numeric(3, 2), server_default=text("0.70"))
    # F-GOAL-6: the monthly capacity set by hand; NULL: the average income minus spending.
    goal_capacity: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))

    users: Mapped[list["User"]] = relationship(back_populates="household")


class Role(enum.StrEnum):
    OWNER = "owner"
    MEMBER = "member"


class User(UUIDPrimaryKey, Timestamps, Base):
    # "user" is a reserved word in Postgres.
    __tablename__ = "app_user"
    __table_args__ = (
        CheckConstraint("email = lower(btrim(email))", name="email_normalized"),
        # Exactly one owner is enforced by the service layer; the DB forbids two.
        Index(
            "uq_app_user_household_owner",
            "household_id",
            unique=True,
            postgresql_where=text("role = 'owner'"),
        ),
    )

    household_id: Mapped[UUID] = mapped_column(ForeignKey("household.id"), index=True)
    email: Mapped[str] = mapped_column(String(320), unique=True)
    display_name: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(
        Enum(
            Role,
            name="role",
            native_enum=False,
            create_constraint=True,
            length=20,
            values_callable=lambda roles: [r.value for r in roles],
        )
    )
    is_active: Mapped[bool] = mapped_column(server_default=text("true"))
    # NULL until the user picks one: the interface then follows the browser.
    language: Mapped[Language | None] = mapped_column(
        Enum(
            Language,
            name="language",
            native_enum=False,
            create_constraint=True,
            length=5,
            values_callable=lambda langs: [lang.value for lang in langs],
        )
    )
    # TOTP seed sealed with kwak_api.auth.crypto.SecretBox, bound to the user id.
    totp_secret_enc: Mapped[bytes | None] = mapped_column(LargeBinary)
    # Null while the user has not proven they can produce codes from the seed.
    totp_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Time step of the last accepted code, so a code cannot be used twice.
    totp_last_counter: Mapped[int | None] = mapped_column(BigInteger)

    household: Mapped[Household] = relationship(back_populates="users")
