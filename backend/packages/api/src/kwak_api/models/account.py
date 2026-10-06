from datetime import date
from decimal import Decimal
from uuid import UUID

from kwak_core.accounts import AccountType, Visibility
from sqlalchemy import CheckConstraint, Date, Enum, ForeignKey, Index, Numeric, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from kwak_api.db import Base, Timestamps, UUIDPrimaryKey
from kwak_api.models.household import User


def _string_enum(enum_type: type[AccountType] | type[Visibility], name: str) -> Enum:
    """VARCHAR + CHECK (not a native enum), so adding a value is a plain migration."""
    return Enum(
        enum_type,
        name=name,
        native_enum=False,
        create_constraint=True,
        length=20,
        values_callable=lambda members: [m.value for m in members],
    )


class Institution(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "institution"
    __table_args__ = (
        # "Société Générale" and " société générale" are the same bank.
        Index("uq_institution_household_name", "household_id", text("lower(name)"), unique=True),
    )

    household_id: Mapped[UUID] = mapped_column(ForeignKey("household.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))


class Account(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "account"
    __table_args__ = (
        Index("uq_account_institution_name", "institution_id", text("lower(name)"), unique=True),
        CheckConstraint(
            "closed_on IS NULL OR closed_on >= opening_date", name="closed_after_opening"
        ),
    )

    household_id: Mapped[UUID] = mapped_column(ForeignKey("household.id"), index=True)
    institution_id: Mapped[UUID] = mapped_column(ForeignKey("institution.id"), index=True)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("app_user.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    type: Mapped[AccountType] = mapped_column(_string_enum(AccountType, "account_type"))
    visibility: Mapped[Visibility] = mapped_column(_string_enum(Visibility, "visibility"))
    # Balance on opening_date, before any imported or entered transaction.
    opening_balance: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    opening_date: Mapped[date] = mapped_column(Date)
    # Closed accounts stay in history but leave current views (F-ACC-3).
    closed_on: Mapped[date | None] = mapped_column(Date)

    institution: Mapped[Institution] = relationship()
    owner: Mapped[User] = relationship()
