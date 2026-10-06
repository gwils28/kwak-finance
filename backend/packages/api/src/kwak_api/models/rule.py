from decimal import Decimal
from uuid import UUID

from sqlalchemy import ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from kwak_api.db import Base, Timestamps, UUIDPrimaryKey
from kwak_api.models.category import Category


class CategorizationRule(UUIDPrimaryKey, Timestamps, Base):
    """Conditions that set a category (F-CAT-2); see kwak_core.rules for the matching."""

    __tablename__ = "categorization_rule"

    household_id: Mapped[UUID] = mapped_column(ForeignKey("household.id"), index=True)
    category_id: Mapped[UUID] = mapped_column(
        ForeignKey("category.id", ondelete="CASCADE"), index=True
    )
    priority: Mapped[int] = mapped_column(Integer)
    label_contains: Mapped[str | None] = mapped_column(String(100))
    amount_min: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    amount_max: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    account_id: Mapped[UUID | None] = mapped_column(ForeignKey("account.id", ondelete="CASCADE"))

    category: Mapped[Category] = relationship()
