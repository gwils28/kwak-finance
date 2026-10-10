from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from kwak_api.db import Base, Timestamps, UUIDPrimaryKey


class BudgetPlan(UUIDPrimaryKey, Timestamps, Base):
    """Monthly targets for a calendar period, from `start_month` to `end_month` (F-BUD-7).

    A plan closed early ends before its period; its replacement starts after the period's first
    month. Plans of a household never overlap (checked by the service, invariant 8).
    """

    __tablename__ = "budget_plan"
    __table_args__ = (
        CheckConstraint("kind IN ('year', 'semester', 'quarter')", name="kind"),
        CheckConstraint(
            "extract(day from start_month) = 1 AND extract(day from end_month) = 1",
            name="months_first_day",
        ),
        CheckConstraint("start_month <= end_month", name="start_before_end"),
        CheckConstraint(
            "expected_income IS NULL OR expected_income >= 0", name="income_not_negative"
        ),
    )

    household_id: Mapped[UUID] = mapped_column(ForeignKey("household.id"), index=True)
    kind: Mapped[str] = mapped_column(String(10))
    year: Mapped[int] = mapped_column(SmallInteger)
    number: Mapped[int] = mapped_column(SmallInteger)
    """1 for a year, 1-2 for a semester, 1-4 for a quarter."""
    start_month: Mapped[date] = mapped_column(Date)
    """First day of the plan's first month."""
    end_month: Mapped[date] = mapped_column(Date)
    """First day of the plan's last month."""
    expected_income: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    """Expected monthly income."""
    note: Mapped[str | None] = mapped_column(Text)
    close_reason: Mapped[str | None] = mapped_column(Text)
    targets: Mapped[list["BudgetPlanTarget"]] = relationship(
        cascade="all, delete-orphan", passive_deletes=True, lazy="selectin"
    )


class BudgetPlanTarget(UUIDPrimaryKey, Timestamps, Base):
    """A category's monthly target within a plan."""

    __tablename__ = "budget_plan_target"
    __table_args__ = (
        UniqueConstraint("plan_id", "category_id"),
        CheckConstraint("amount >= 0", name="amount_not_negative"),
    )

    plan_id: Mapped[UUID] = mapped_column(ForeignKey("budget_plan.id", ondelete="CASCADE"))
    category_id: Mapped[UUID] = mapped_column(ForeignKey("category.id", ondelete="CASCADE"))
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
