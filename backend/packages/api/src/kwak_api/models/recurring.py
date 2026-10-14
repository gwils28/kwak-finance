from datetime import date
from decimal import Decimal
from uuid import UUID

from kwak_core.recurring import Frequency
from sqlalchemy import (
    CheckConstraint,
    Date,
    Enum,
    ForeignKey,
    Numeric,
    SmallInteger,
    String,
    UniqueConstraint,
    false,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from kwak_api.db import Base, Timestamps, UUIDPrimaryKey
from kwak_api.models.account import Account


class RecurringItem(UUIDPrimaryKey, Timestamps, Base):
    """An expected transaction (F-REC-1); see kwak_core.recurring for its occurrences."""

    __tablename__ = "recurring_item"
    __table_args__ = (
        CheckConstraint("day BETWEEN 0 AND 31", name="day_range"),
        CheckConstraint("end_on IS NULL OR end_on >= start_on", name="start_before_end"),
        CheckConstraint(
            "destination_id IS NULL OR destination_id <> account_id", name="transfer_accounts"
        ),
        CheckConstraint(
            "destination_id IS NULL OR category_id IS NULL", name="transfer_no_category"
        ),
    )

    household_id: Mapped[UUID] = mapped_column(ForeignKey("household.id"), index=True)
    account_id: Mapped[UUID] = mapped_column(
        ForeignKey("account.id", ondelete="CASCADE"), index=True
    )
    category_id: Mapped[UUID | None] = mapped_column(ForeignKey("category.id", ondelete="SET NULL"))
    destination_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("account.id", ondelete="CASCADE"), index=True
    )
    """Set for a transfer item (F-TX-9): the account its amount is paid into."""
    label: Mapped[str] = mapped_column(String(100))
    """Matched in the transactions' labels as a rule's (F-CAT-2); empty for a transfer item."""
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    frequency: Mapped[Frequency] = mapped_column(
        Enum(
            Frequency,
            name="recurring_frequency",
            native_enum=False,
            create_constraint=True,
            length=10,
            values_callable=lambda kinds: [k.value for k in kinds],
        )
    )
    day: Mapped[int] = mapped_column(SmallInteger)
    """0 (Monday) to 6 for a weekly item, else the day of the month."""
    start_on: Mapped[date] = mapped_column(Date)
    end_on: Mapped[date | None] = mapped_column(Date)
    estimated: Mapped[bool] = mapped_column(server_default=false())
    paused: Mapped[bool] = mapped_column(server_default=false())

    account: Mapped[Account] = relationship(foreign_keys=[account_id])
    destination: Mapped[Account | None] = relationship(foreign_keys=[destination_id])


class RecurringSkip(UUIDPrimaryKey, Base):
    """An occurrence the user skipped (F-REC-3): it is no longer expected."""

    __tablename__ = "recurring_skip"
    __table_args__ = (UniqueConstraint("item_id", "due_on"),)

    item_id: Mapped[UUID] = mapped_column(ForeignKey("recurring_item.id", ondelete="CASCADE"))
    due_on: Mapped[date] = mapped_column(Date)


class DismissedSuggestion(UUIDPrimaryKey, Base):
    """A detected series the user dismissed (F-REC-2), not suggested again."""

    __tablename__ = "dismissed_suggestion"
    __table_args__ = (UniqueConstraint("account_id", "label"),)

    account_id: Mapped[UUID] = mapped_column(ForeignKey("account.id", ondelete="CASCADE"))
    label: Mapped[str] = mapped_column(String(200))
    """The series' folded label."""
