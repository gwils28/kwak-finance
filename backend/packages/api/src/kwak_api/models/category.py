from uuid import UUID

from kwak_core.categories import CategoryKind
from sqlalchemy import Enum, ForeignKey, Index, String, text
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
