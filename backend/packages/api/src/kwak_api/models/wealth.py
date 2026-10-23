from datetime import date
from decimal import Decimal
from uuid import UUID

from kwak_core.visibility import Visibility
from kwak_core.wealth import WealthKind
from sqlalchemy import (
    CheckConstraint,
    Date,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from kwak_api.db import Base, Timestamps, UUIDPrimaryKey
from kwak_api.models.household import User


def _string_enum(enum_type: type[WealthKind] | type[Visibility], name: str) -> Enum:
    """VARCHAR + CHECK (not a native enum), so adding a value is a plain migration."""
    return Enum(
        enum_type,
        name=name,
        native_enum=False,
        create_constraint=True,
        length=20,
        values_callable=lambda members: [m.value for m in members],
    )


class WealthCategory(UUIDPrimaryKey, Timestamps, Base):
    """A category of the wealth matrix (F-WLT-1): its lines are the holdings."""

    __tablename__ = "wealth_category"
    __table_args__ = (
        Index(
            "uq_wealth_category_household_name", "household_id", text("lower(name)"), unique=True
        ),
    )

    household_id: Mapped[UUID] = mapped_column(ForeignKey("household.id"), index=True)
    name: Mapped[str] = mapped_column(String(60))
    kind: Mapped[WealthKind] = mapped_column(_string_enum(WealthKind, "wealth_kind"))
    colour: Mapped[str] = mapped_column(String(20))
    """The key of its `wealth-<key>` colour token."""
    preset: Mapped[str | None] = mapped_column(String(20))
    """Which default category it is (its default colour key), whatever its name and colour
    become: the projection's defaults follow it (F-SIM-1). None for a category added later."""
    position: Mapped[int] = mapped_column(Integer)
    """Its row in the matrix, from the top."""


class WealthLine(UUIDPrimaryKey, Timestamps, Base):
    """A holding entered by hand (F-WLT-2), a bank account's included (F-WLT-4)."""

    __tablename__ = "wealth_line"
    __table_args__ = (
        CheckConstraint("extract(day from closed_from) = 1", name="closed_from_month"),
    )

    household_id: Mapped[UUID] = mapped_column(ForeignKey("household.id"), index=True)
    category_id: Mapped[UUID] = mapped_column(ForeignKey("wealth_category.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("app_user.id"), index=True)
    visibility: Mapped[Visibility] = mapped_column(_string_enum(Visibility, "visibility"))
    closed_from: Mapped[date | None] = mapped_column(Date)
    """The first month (its first day) the line no longer holds anything."""

    category: Mapped[WealthCategory] = relationship()
    owner: Mapped[User] = relationship()


class WealthValue(UUIDPrimaryKey, Base):
    """A line's value for one calendar month (F-WLT-3)."""

    __tablename__ = "wealth_value"
    __table_args__ = (
        UniqueConstraint("line_id", "month"),
        CheckConstraint("extract(day from month) = 1", name="month_first_day"),
        CheckConstraint("amount >= 0", name="amount_positive"),
    )

    line_id: Mapped[UUID] = mapped_column(ForeignKey("wealth_line.id", ondelete="CASCADE"))
    month: Mapped[date] = mapped_column(Date)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
