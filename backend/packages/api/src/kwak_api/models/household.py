import enum
from uuid import UUID

from sqlalchemy import CheckConstraint, Enum, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from kwak_api.db import Base, Timestamps, UUIDPrimaryKey


class Household(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "household"

    name: Mapped[str] = mapped_column(String(100))

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

    household: Mapped[Household] = relationship(back_populates="users")
