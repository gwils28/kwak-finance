"""The spending since v1.0 (§4.2 to 4.6): lines entered by hand, monthly income, fixed expenses."""

from datetime import date
from decimal import Decimal
from uuid import UUID

from kwak_core.categories import CategoryKind
from kwak_core.fixed import FixedFrequency
from sqlalchemy import (
    CheckConstraint,
    Date,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from kwak_api.db import Base, Timestamps, UUIDPrimaryKey
from kwak_api.models.household import User


def _string_enum(
    enum_type: type[CategoryKind] | type[FixedFrequency], name: str, *, check: bool = True
) -> Enum:
    """VARCHAR + CHECK (not a native enum), so adding a value is a plain migration."""
    return Enum(
        enum_type,
        name=name,
        native_enum=False,
        create_constraint=check,
        length=20,
        values_callable=lambda members: [m.value for m in members],
    )


class SpendingCategory(UUIDPrimaryKey, Timestamps, Base):
    """One level (F-CAT-1): an expense or a savings category."""

    __tablename__ = "spending_category"
    __table_args__ = (
        Index(
            "uq_spending_category_household_name",
            "household_id",
            text("lower(name)"),
            unique=True,
        ),
        CheckConstraint("kind IN ('expense', 'savings')", name="spending_kind"),
    )

    household_id: Mapped[UUID] = mapped_column(ForeignKey("household.id"), index=True)
    name: Mapped[str] = mapped_column(String(60))
    kind: Mapped[CategoryKind] = mapped_column(
        _string_enum(CategoryKind, "category_kind", check=False)
    )
    """Expense or savings only: the table's own CHECK (income has no lines since v1.0)."""
    one_off: Mapped[bool] = mapped_column(server_default=text("false"))
    """F-CAT-6: paid once in the month, never judged against the month's pace."""
    position: Mapped[int] = mapped_column(Integer)


class FixedExpense(UUIDPrimaryKey, Timestamps, Base):
    """F-FIX-1: an expense coming back every month, quarter or year, to confirm."""

    __tablename__ = "fixed_expense"
    __table_args__ = (
        CheckConstraint("amount <> 0", name="amount_not_zero"),
        CheckConstraint("day BETWEEN 1 AND 31", name="day_range"),
        CheckConstraint("extract(day FROM first_month) = 1", name="first_month_start"),
        CheckConstraint(
            "last_month IS NULL"
            " OR (extract(day FROM last_month) = 1 AND last_month >= first_month)",
            name="last_month_after_first",
        ),
    )

    household_id: Mapped[UUID] = mapped_column(ForeignKey("household.id"), index=True)
    label: Mapped[str] = mapped_column(String(100))
    category_id: Mapped[UUID] = mapped_column(ForeignKey("spending_category.id"), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    """Signed as a line: negative is spent or put aside."""
    frequency: Mapped[FixedFrequency] = mapped_column(_string_enum(FixedFrequency, "frequency"))
    day: Mapped[int] = mapped_column(SmallInteger)
    first_month: Mapped[date] = mapped_column(Date)
    """The first day of the month of its first occurrence."""
    last_month: Mapped[date | None] = mapped_column(Date)
    paused: Mapped[bool] = mapped_column(server_default=text("false"))

    category: Mapped[SpendingCategory] = relationship()
    skips: Mapped[list["FixedSkip"]] = relationship(
        cascade="all, delete-orphan", passive_deletes=True
    )


class FixedSkip(UUIDPrimaryKey, Base):
    """F-FIX-2: an occurrence skipped for a month."""

    __tablename__ = "fixed_skip"
    __table_args__ = (UniqueConstraint("fixed_expense_id", "month"),)

    fixed_expense_id: Mapped[UUID] = mapped_column(
        ForeignKey("fixed_expense.id", ondelete="CASCADE")
    )
    month: Mapped[date] = mapped_column(Date)


class SpendingLine(UUIDPrimaryKey, Timestamps, Base):
    """F-LIN-1: one expense or savings line; `created_at` is when it was entered (F-ENT-4)."""

    __tablename__ = "spending_line"
    __table_args__ = (
        CheckConstraint("amount <> 0", name="amount_not_zero"),
        Index("ix_spending_line_household_day", "household_id", "day"),
    )

    household_id: Mapped[UUID] = mapped_column(ForeignKey("household.id"))
    day: Mapped[date] = mapped_column(Date)
    label: Mapped[str] = mapped_column(String(100))
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    """Negative is spent or put aside, positive taken back from savings."""
    category_id: Mapped[UUID | None] = mapped_column(ForeignKey("spending_category.id"), index=True)
    """None when the line is split (F-LIN-4): its parts hold the categories."""
    fixed_expense_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("fixed_expense.id", ondelete="SET NULL"), index=True
    )
    """The fixed expense it was confirmed from (F-FIX-2)."""
    entered_by_id: Mapped[UUID] = mapped_column(ForeignKey("app_user.id"))

    entered_by: Mapped[User] = relationship()
    parts: Mapped[list["SpendingLinePart"]] = relationship(
        order_by="SpendingLinePart.position",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class SpendingLinePart(UUIDPrimaryKey, Base):
    """F-LIN-4: a part of a split line; the parts add up to the line."""

    __tablename__ = "spending_line_part"
    __table_args__ = (
        UniqueConstraint("line_id", "position"),
        CheckConstraint("amount <> 0", name="amount_not_zero"),
    )

    line_id: Mapped[UUID] = mapped_column(ForeignKey("spending_line.id", ondelete="CASCADE"))
    position: Mapped[int] = mapped_column(SmallInteger)
    category_id: Mapped[UUID] = mapped_column(ForeignKey("spending_category.id"), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))


class MonthlyIncome(UUIDPrimaryKey, Timestamps, Base):
    """F-INC-1: the household's income entered for a month."""

    __tablename__ = "monthly_income"
    __table_args__ = (
        UniqueConstraint("household_id", "month"),
        CheckConstraint("amount >= 0", name="amount_not_negative"),
        CheckConstraint("extract(day FROM month) = 1", name="month_start"),
    )

    household_id: Mapped[UUID] = mapped_column(ForeignKey("household.id"))
    month: Mapped[date] = mapped_column(Date)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))


class SpendingTarget(UUIDPrimaryKey, Timestamps, Base):
    """F-BUD-1, 9: a category's monthly target (an objective for savings) from a month on.

    A NULL amount: no target from that month.
    """

    __tablename__ = "spending_target"
    __table_args__ = (
        UniqueConstraint("category_id", "from_month"),
        CheckConstraint("amount IS NULL OR amount >= 0", name="amount_not_negative"),
        CheckConstraint("extract(day FROM from_month) = 1", name="from_month_start"),
    )

    category_id: Mapped[UUID] = mapped_column(
        ForeignKey("spending_category.id", ondelete="CASCADE")
    )
    from_month: Mapped[date] = mapped_column(Date)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
