import enum
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from kwak_core.users import Language
from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    LargeBinary,
    Numeric,
    SmallInteger,
    String,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from kwak_api.db import Base, Timestamps, UUIDPrimaryKey


class Household(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "household"
    __table_args__ = (
        CheckConstraint("warn_at BETWEEN 0.5 AND 1", name="warn_at_range"),
        CheckConstraint("extract(day from wealth_start) = 1", name="wealth_start_month"),
        CheckConstraint("precaution_share BETWEEN 0.5 AND 1", name="precaution_share_range"),
        CheckConstraint("goal_capacity >= 0", name="goal_capacity_positive"),
        CheckConstraint("inflation BETWEEN -0.05 AND 0.2", name="inflation_range"),
        CheckConstraint("retirement_share BETWEEN 0.5 AND 1.5", name="retirement_share_range"),
        CheckConstraint("retirement_spending >= 0", name="retirement_spending_positive"),
        CheckConstraint(
            "retirement_share IS NULL OR retirement_spending IS NULL",
            name="retirement_share_or_amount",
        ),
        CheckConstraint(
            "pension_indexation BETWEEN -0.02 AND 0.01", name="pension_indexation_range"
        ),
        CheckConstraint("horizon_age BETWEEN 85 AND 105", name="horizon_age_range"),
        CheckConstraint(
            "projection_savings IN ('declared', 'measured')", name="projection_savings_known"
        ),
        # F-ADM-5: one demo household at most.
        Index("uq_household_demo", "is_demo", unique=True, postgresql_where=text("is_demo")),
    )

    name: Mapped[str] = mapped_column(String(100))
    # F-ADM-5: the demo's fictitious household, which the real one never sees.
    is_demo: Mapped[bool] = mapped_column(default=False, server_default=text("false"))
    # F-BUD-2: the share of a monthly target from which a category is to watch.
    warn_at: Mapped[Decimal] = mapped_column(Numeric(3, 2), server_default=text("0.80"))
    # F-WLT-5: the first month the wealth matrix shows by default; NULL: no limit.
    wealth_start: Mapped[date | None] = mapped_column(Date)
    # F-GOAL-6: the share of the capacity kept for the precaution while it falls short.
    precaution_share: Mapped[Decimal] = mapped_column(Numeric(3, 2), server_default=text("0.70"))
    # F-GOAL-6: the monthly capacity set by hand; NULL: the average income minus spending.
    goal_capacity: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    # F-SIM-1: the yearly inflation the projection assumes; NULL: the default (2 %).
    inflation: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    # F-RET-2: the retirement spending, a share of today's spending outside the loans or an
    # amount; the pensions' indexation against inflation; the youngest member's age at the
    # horizon. NULL: the defaults (80 %, -0.3 %, 95).
    retirement_share: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    retirement_spending: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    pension_indexation: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    horizon_age: Mapped[int | None] = mapped_column(SmallInteger)
    # F-SIM-3: where the simulator's monthly savings come from, `declared` (the contributions
    # alone) or `measured` (the goals' capacity); NULL: declared once a contribution exists.
    projection_savings: Mapped[str | None] = mapped_column(String(10))

    users: Mapped[list["User"]] = relationship(back_populates="household")


class Role(enum.StrEnum):
    OWNER = "owner"
    MEMBER = "member"


class User(UUIDPrimaryKey, Timestamps, Base):
    # "user" is a reserved word in Postgres.
    __tablename__ = "app_user"
    __table_args__ = (
        CheckConstraint("email = lower(btrim(email))", name="email_normalized"),
        # Exactly one owner is enforced by the service layer; the DB forbids two.
        Index(
            "uq_app_user_household_owner",
            "household_id",
            unique=True,
            postgresql_where=text("role = 'owner'"),
        ),
    )

    household_id: Mapped[UUID] = mapped_column(ForeignKey("household.id"), index=True)
    email: Mapped[str] = mapped_column(String(320), unique=True)
    display_name: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(
        Enum(
            Role,
            name="role",
            native_enum=False,
            create_constraint=True,
            length=20,
            values_callable=lambda roles: [r.value for r in roles],
        )
    )
    is_active: Mapped[bool] = mapped_column(server_default=text("true"))
    # NULL until the user picks one: the interface then follows the browser.
    language: Mapped[Language | None] = mapped_column(
        Enum(
            Language,
            name="language",
            native_enum=False,
            create_constraint=True,
            length=5,
            values_callable=lambda langs: [lang.value for lang in langs],
        )
    )
    # TOTP seed sealed with kwak_api.auth.crypto.SecretBox, bound to the user id.
    totp_secret_enc: Mapped[bytes | None] = mapped_column(LargeBinary)
    # Null while the user has not proven they can produce codes from the seed.
    totp_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Time step of the last accepted code, so a code cannot be used twice.
    totp_last_counter: Mapped[int | None] = mapped_column(BigInteger)

    household: Mapped[Household] = relationship(back_populates="users")
