from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, Date, ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from kwak_api.db import Base, Timestamps, UUIDPrimaryKey


class BudgetTarget(UUIDPrimaryKey, Timestamps, Base):
    """A monthly target in force from `valid_from` until the category's next target (F-BUD-1)."""

    __tablename__ = "budget_target"
    __table_args__ = (
        UniqueConstraint("category_id", "valid_from"),
        CheckConstraint("extract(day from valid_from) = 1", name="valid_from_first_of_month"),
        CheckConstraint("amount IS NULL OR amount >= 0", name="amount_not_negative"),
    )

    household_id: Mapped[UUID] = mapped_column(ForeignKey("household.id"), index=True)
    category_id: Mapped[UUID] = mapped_column(ForeignKey("category.id", ondelete="CASCADE"))
    valid_from: Mapped[date] = mapped_column(Date)
    """First day of the month the target starts."""
    amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    """NULL removes the target from that month on."""
