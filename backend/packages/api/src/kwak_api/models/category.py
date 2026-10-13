from uuid import UUID

from kwak_core.categories import CategoryKind
from sqlalchemy import CheckConstraint, Enum, ForeignKey, Index, SmallInteger, String, text
from sqlalchemy.orm import Mapped, mapped_column

from kwak_api.db import Base, Timestamps, UUIDPrimaryKey


class Category(UUIDPrimaryKey, Timestamps, Base):
    """Two levels: top-level categories (parent_id NULL) and their subcategories."""

    __tablename__ = "category"
    __table_args__ = (
        # Unique among siblings, any case. NULLs are distinct in a unique index, hence coalesce.
        Index(
            "uq_category_household_parent_name",
            "household_id",
            text("coalesce(parent_id, '00000000-0000-0000-0000-000000000000'::uuid)"),
            text("lower(name)"),
            unique=True,
        ),
        CheckConstraint("shift_day BETWEEN 0 AND 31", name="shift_day_range"),
    )

    household_id: Mapped[UUID] = mapped_column(ForeignKey("household.id"), index=True)
    parent_id: Mapped[UUID | None] = mapped_column(ForeignKey("category.id"), index=True)
    name: Mapped[str] = mapped_column(String(60))
    kind: Mapped[CategoryKind] = mapped_column(
        Enum(
            CategoryKind,
            name="category_kind",
            native_enum=False,
            create_constraint=True,
            length=20,
            values_callable=lambda kinds: [k.value for k in kinds],
        )
    )
    # F-CAT-5: transactions booked on or after this day count for the next month. NULL: no
    # setting of its own (a subcategory follows its parent's); 0: never shifted.
    shift_day: Mapped[int | None] = mapped_column(SmallInteger)
    # F-CAT-6: an expense paid once in the month, never judged against the month's pace. NULL:
    # no setting of its own (a subcategory follows its parent's).
    one_off: Mapped[bool | None]
