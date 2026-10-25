from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, Date, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from kwak_api.db import Base, Timestamps, UUIDPrimaryKey
from kwak_api.models.household import User


class MemberRetirement(UUIDPrimaryKey, Timestamps, Base):
    """A member's retirement (F-RET-1), entered by the member, seen by the household. Months
    are their first day; amounts are net monthly, in today's euros."""

    __tablename__ = "member_retirement"
    __table_args__ = (
        CheckConstraint("extract(day from birth) = 1", name="birth_month"),
        CheckConstraint("extract(day from retirement) = 1", name="retirement_month"),
        CheckConstraint("extract(day from pension_month) = 1", name="pension_month_first"),
        CheckConstraint("pension_month >= retirement", name="pension_after_retirement"),
        CheckConstraint("birth < retirement", name="born_before"),
        CheckConstraint("earnings >= 0", name="earnings_positive"),
        CheckConstraint("pension >= 0", name="pension_positive"),
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("app_user.id", ondelete="CASCADE"), unique=True
    )
    birth: Mapped[date] = mapped_column(Date)
    retirement: Mapped[date] = mapped_column(Date)
    """When the member stops working."""
    earnings: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    """The net earnings that stop then, as they reach the account."""
    pension_month: Mapped[date] = mapped_column(Date)
    pension: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    """The net pension as it would reach the account."""

    user: Mapped[User] = relationship()
