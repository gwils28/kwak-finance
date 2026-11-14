import enum
from datetime import date
from decimal import Decimal
from uuid import UUID

from kwak_core.goals import AidSource, ProType
from kwak_core.visibility import Visibility
from sqlalchemy import (
    CheckConstraint,
    Date,
    Enum,
    ForeignKey,
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
from kwak_api.models.wealth import WealthLine


class NextCycle(enum.StrEnum):
    """What became of a goal to renew's next cycle (F-GOAL-11)."""

    STARTED = "started"
    """Once over its life, even if that cycle is deleted later (invariant §8.52)."""
    DECLINED = "declined"
    """Archived with no next cycle asked for; reopening it forgets the choice."""


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
        CheckConstraint("deadline IS NOT NULL OR permanent OR pleasure", name="deadline_needed"),
        CheckConstraint("permanent OR NOT precaution", name="precaution_permanent"),
        CheckConstraint("precaution OR fill_first", name="fill_first_precaution"),
        CheckConstraint(
            "NOT pleasure OR (deadline IS NULL AND NOT permanent AND NOT precaution)",
            name="pleasure_alone",
        ),
        CheckConstraint("extract(day from start) = 1", name="start_month"),
        CheckConstraint("extract(day from deadline) = 1", name="deadline_month"),
        CheckConstraint("extract(day from closed_from) = 1", name="closed_from_month"),
        CheckConstraint("(closed_from IS NULL) = (closed_as IS NULL)", name="closed_as_given"),
        CheckConstraint(
            "pro_type IS NULL OR (deadline IS NOT NULL AND NOT permanent AND NOT precaution"
            " AND NOT pleasure)",
            name="professional_alone",
        ),
        CheckConstraint(
            "(pro_type IS NULL) = (cost IS NULL) AND (cost IS NULL OR cost >= target)",
            name="cost_professional",
        ),
        CheckConstraint(
            "renew_years IS NULL OR (pro_type = 'equipment' AND renew_years BETWEEN 1 AND 10)",
            name="renew_equipment",
        ),
    )

    household_id: Mapped[UUID] = mapped_column(ForeignKey("household.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    precaution: Mapped[bool] = mapped_column(default=False, server_default=text("false"))
    """In the foundation (F-GOAL-1), always permanent; filled first when `fill_first`."""
    permanent: Mapped[bool] = mapped_column(default=False, server_default=text("false"))
    """Kept in view once reached; any other goal archives itself then (F-GOAL-8)."""
    pleasure: Mapped[bool] = mapped_column(default=False, server_default=text("false"))
    """In the capstone, without a deadline, unlocked by the rest of the pyramid (F-GOAL-10)."""
    fill_first: Mapped[bool] = mapped_column(default=True, server_default=text("true"))
    """A precaution goal filled before the others (F-GOAL-1); unticked, it keeps to the
    foundation only. Always true for another goal."""
    target: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    start: Mapped[date] = mapped_column(Date)
    """The first month tracked (its first day)."""
    deadline: Mapped[date | None] = mapped_column(Date)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("app_user.id"), index=True)
    visibility: Mapped[Visibility] = mapped_column(_string_enum(Visibility, "visibility"))
    closed_from: Mapped[date | None] = mapped_column(Date)
    """The first month the goal is closed: it leaves the pyramid and frees its lines."""
    closed_as: Mapped[ClosedAs | None] = mapped_column(_string_enum(ClosedAs, "goal_closed_as"))
    pro_type: Mapped[ProType | None] = mapped_column(_string_enum(ProType, "goal_pro_type"))
    """Set for a professional goal, in its tier (F-GOAL-11)."""
    cost: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    """A professional goal's cost: its target plus what others pay."""
    renew_years: Mapped[int | None] = mapped_column(SmallInteger)
    """Equipment renewed every so many years: archiving it starts its next cycle."""
    renewed_from: Mapped[UUID | None] = mapped_column(
        ForeignKey("goal.id", ondelete="SET NULL"), unique=True
    )
    """The cycle this one renews: each has one next cycle at most (invariant §8.52)."""
    next_cycle: Mapped[NextCycle | None] = mapped_column(_string_enum(NextCycle, "goal_next_cycle"))
    """Set once its next cycle has started or was declined: none is started (again)."""

    owner: Mapped[User] = relationship()
    fundings: Mapped[list["GoalFunding"]] = relationship(
        back_populates="goal", cascade="all, delete-orphan", order_by="GoalFunding.id"
    )
    adjustments: Mapped[list["GoalAdjustment"]] = relationship(
        cascade="all, delete-orphan", order_by="GoalAdjustment.month"
    )
    aids: Mapped[list["GoalAid"]] = relationship(
        cascade="all, delete-orphan", order_by="GoalAid.id"
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


class GoalAid(UUIDPrimaryKey, Base):
    """An amount of a professional goal's cost paid by others (F-GOAL-11)."""

    __tablename__ = "goal_aid"
    __table_args__ = (CheckConstraint("amount > 0", name="amount_positive"),)

    goal_id: Mapped[UUID] = mapped_column(ForeignKey("goal.id", ondelete="CASCADE"), index=True)
    source: Mapped[AidSource] = mapped_column(_string_enum(AidSource, "goal_aid_source"))
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    received: Mapped[bool] = mapped_column(default=False, server_default=text("false"))
    """Paid to the household rather than directly to the seller or the training body."""


class GoalAdjustment(UUIDPrimaryKey, Base):
    """What a goal's envelope on a line holds from a month, set by hand (F-GOAL-3). Kept by goal
    and line, so it outlives a change of the goal's fundings."""

    __tablename__ = "goal_adjustment"
    __table_args__ = (
        UniqueConstraint("goal_id", "line_id", "month"),
        CheckConstraint("amount >= 0", name="amount_positive"),
        CheckConstraint("extract(day from month) = 1", name="month_first_day"),
    )

    goal_id: Mapped[UUID] = mapped_column(ForeignKey("goal.id", ondelete="CASCADE"))
    line_id: Mapped[UUID] = mapped_column(
        ForeignKey("wealth_line.id", ondelete="CASCADE"), index=True
    )
    month: Mapped[date] = mapped_column(Date)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))


class GoalNoticeDismissal(UUIDPrimaryKey, Base):
    """A member's choice on a point to look at (spec §4.12, F-ANA-8): snoozed until a month, or
    dismissed as it stood, until it worsens. Each member's own."""

    __tablename__ = "goal_notice_dismissal"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "rule", "goal_id", "line_id", postgresql_nulls_not_distinct=True
        ),
        CheckConstraint("(until IS NULL) <> (severity IS NULL)", name="snoozed_or_dismissed"),
        CheckConstraint("extract(day from until) = 1", name="until_month"),
    )

    user_id: Mapped[UUID] = mapped_column(ForeignKey("app_user.id", ondelete="CASCADE"))
    rule: Mapped[str] = mapped_column(String(30))
    goal_id: Mapped[UUID | None] = mapped_column(ForeignKey("goal.id", ondelete="CASCADE"))
    line_id: Mapped[UUID | None] = mapped_column(ForeignKey("wealth_line.id", ondelete="CASCADE"))
    until: Mapped[date | None] = mapped_column(Date)
    """Snoozed: hidden while the reference month is before this one."""
    severity: Mapped[str | None] = mapped_column(String(10))
    """Dismissed: the point's severity then, and its main amount below."""
    amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
