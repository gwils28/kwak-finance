from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from kwak_api.db import Base, Timestamps, UUIDPrimaryKey
from kwak_api.models.account import Account


class ImportBatch(UUIDPrimaryKey, Base):
    """One imported file (F-TX-6). Rolling it back deletes its transactions and keeps this row."""

    __tablename__ = "import_batch"
    __table_args__ = (
        # The same file is imported at most once per account, unless that import was rolled back.
        Index(
            "uq_import_batch_account_file",
            "account_id",
            "file_sha256",
            unique=True,
            postgresql_where=text("rolled_back_at IS NULL AND imported_count > 0"),
        ),
    )

    account_id: Mapped[UUID] = mapped_column(ForeignKey("account.id"), index=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("app_user.id"))
    format_key: Mapped[str] = mapped_column(String(50))
    file_name: Mapped[str] = mapped_column(String(255))
    file_sha256: Mapped[str] = mapped_column(String(64))
    imported_count: Mapped[int] = mapped_column(Integer)
    duplicate_count: Mapped[int] = mapped_column(Integer)
    skipped_count: Mapped[int] = mapped_column(Integer)
    """Rows dated before the account's opening date."""
    error_count: Mapped[int] = mapped_column(Integer)
    period_start: Mapped[date | None] = mapped_column(Date)
    period_end: Mapped[date | None] = mapped_column(Date)
    bank_balance: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    bank_balance_on: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    rolled_back_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    account: Mapped[Account] = relationship()


class Transaction(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "transaction"
    __table_args__ = (
        # An imported row is stored once per account (invariant §8.4). Manual entries have none.
        Index("uq_transaction_account_fingerprint", "account_id", "fingerprint", unique=True),
        Index("ix_transaction_account_booked_on", "account_id", "booked_on"),
    )

    account_id: Mapped[UUID] = mapped_column(ForeignKey("account.id"))
    booked_on: Mapped[date] = mapped_column(Date)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    """Negative = outflow."""
    label_raw: Mapped[str] = mapped_column(Text)
    label_norm: Mapped[str] = mapped_column(Text)
    fingerprint: Mapped[str | None] = mapped_column(String(64))
    import_batch_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("import_batch.id", ondelete="SET NULL"), index=True
    )
    # NULL = "to categorise" (F-BUD-5). Deleting a category uncategorises its transactions.
    category_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("category.id", ondelete="SET NULL"), index=True
    )
