import enum
from datetime import date
from decimal import Decimal
from uuid import UUID

from kwak_core.accounts import Visibility
from sqlalchemy import (
    CheckConstraint,
    Date,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from kwak_api.db import Base, Timestamps, UUIDPrimaryKey
from kwak_api.models.household import User
from kwak_api.models.wealth import WealthLine


class ClosedAs(enum.StrEnum):
    ARCHIVED = "archived"
    """Done with: kept for the record."""
    CANCELLED = "cancelled"
    """No longer wanted."""


def _string_enum(enum_type: type[enum.StrEnum], name: str) -> Enum:
    """VARCHAR + CHECK (not a native enum), so adding a value is a plain migration."""
    return Enum(
        enum_type,
        name=name,
        native_enum=False,
        create_constraint=True,
        length=20,
        values_callable=lambda members: [m.value for m in members],
    )


class Goal(UUIDPrimaryKey, Timestamps, Base):
    """An amount to gather by a date; its tier of the pyramid follows the deadline (F-GOAL-1)."""

    __tablename__ = "goal"
    __table_args__ = (
        CheckConstraint("target > 0", name="target_positive"),
        CheckConstraint("deadline IS NOT NULL OR permanent", name="deadline_needed"),
        CheckConstraint("permanent OR NOT precaution", name="precaution_permanent"),
        CheckConstraint("extract(day from start) = 1", name="start_month"),
        CheckConstraint("extract(day from deadline) = 1", name="deadline_month"),
        CheckConstraint("extract(day from closed_from) = 1", name="closed_from_month"),
        CheckConstraint("(closed_from IS NULL) = (closed_as IS NULL)", name="closed_as_given"),
    )

    household_id: Mapped[UUID] = mapped_column(ForeignKey("household.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    precaution: Mapped[bool] = mapped_column(default=False, server_default=text("false"))
    """The emergency fund, filled first (F-GOAL-6): a short-term goal."""
    permanent: Mapped[bool] = mapped_column(default=False, server_default=text("false"))
    """Kept in view once reached; any other goal archives itself then (F-GOAL-8)."""
    target: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    start: Mapped[date] = mapped_column(Date)
    """The first month tracked (its first day)."""
    deadline: Mapped[date | None] = mapped_column(Date)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("app_user.id"), index=True)
    visibility: Mapped[Visibility] = mapped_column(_string_enum(Visibility, "visibility"))
    closed_from: Mapped[date | None] = mapped_column(Date)
    """The first month the goal is closed: it leaves the pyramid and frees its lines."""
    closed_as: Mapped[ClosedAs | None] = mapped_column(_string_enum(ClosedAs, "goal_closed_as"))

    owner: Mapped[User] = relationship()
    fundings: Mapped[list["GoalFunding"]] = relationship(
        back_populates="goal", cascade="all, delete-orphan", order_by="GoalFunding.id"
    )


class GoalFunding(UUIDPrimaryKey, Base):
    """A goal's envelope on a wealth line: an opening amount and a share of its rises (F-GOAL-3)."""

    __tablename__ = "goal_funding"
    __table_args__ = (
        UniqueConstraint("goal_id", "line_id"),
        CheckConstraint("share BETWEEN 1 AND 100", name="share_range"),
        CheckConstraint("opening >= 0", name="opening_positive"),
    )

    goal_id: Mapped[UUID] = mapped_column(ForeignKey("goal.id", ondelete="CASCADE"))
    line_id: Mapped[UUID] = mapped_column(
        ForeignKey("wealth_line.id", ondelete="CASCADE"), index=True
    )
    share: Mapped[int] = mapped_column(Integer)
    """Of the line's rises, in %."""
    opening: Mapped[Decimal] = mapped_column(Numeric(14, 2), server_default=text("0"))
    """Taken from the line's free part in the goal's start month."""

    goal: Mapped[Goal] = relationship(back_populates="fundings")
    line: Mapped[WealthLine] = relationship()
