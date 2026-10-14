"""The budget month of a transaction (F-TX-7, F-CAT-5), in SQL for totals and in Python for
the transaction list. Both follow kwak_core.budget_month; a test checks they agree."""

from collections.abc import Mapping
from datetime import date
from uuid import UUID

from kwak_core.budget import Month
from kwak_core.budget_month import Booked, budget_month, shift_day
from sqlalchemy import ColumnElement, Date, and_, case, cast, extract, func, literal_column, select
from sqlalchemy.orm import aliased

from kwak_api.models import Category, Transaction, TransactionPart


def shift_category() -> ColumnElement[UUID | None]:
    """The category the month shift follows: the transaction's, or a split one's first part
    (F-TX-4)."""
    first_part = (
        select(TransactionPart.category_id)
        .where(TransactionPart.transaction_id == Transaction.id, TransactionPart.position == 0)
        .correlate(Transaction)
        .scalar_subquery()
    )
    return func.coalesce(Transaction.category_id, first_part)


def _shift_from() -> ColumnElement[int]:
    """The day the transaction's category shifts from: its own setting, else its parent's;
    NULL when it never shifts (no category, no setting, or 0)."""
    own = aliased(Category)
    parent = aliased(Category)
    return (
        select(func.nullif(func.coalesce(own.shift_day, parent.shift_day), literal_column("0")))
        .select_from(own)
        .outerjoin(parent, parent.id == own.parent_id)
        .where(own.id == shift_category())
        .correlate(Transaction)
        .scalar_subquery()
    )


def month_start() -> ColumnElement[date]:
    """The first day of the transaction's budget month."""
    booked = func.date_trunc("month", Transaction.booked_on)
    return case(
        (Transaction.transfer_group_id.is_not(None), cast(booked, Date)),
        (Transaction.budget_month.is_not(None), Transaction.budget_month),
        (
            extract("day", Transaction.booked_on) >= _shift_from(),
            cast(booked + literal_column("interval '1 month'"), Date),
        ),
        else_=cast(booked, Date),
    )


def in_months(first: Month, last: Month) -> ColumnElement[bool]:
    """Transactions counted in `first`..`last`. The booking-date window (one month wider on
    each side) lets Postgres use the date index before computing the budget month."""
    return and_(
        Transaction.booked_on >= first.previous().first_day(),
        Transaction.booked_on < last.next().next().first_day(),
        month_start() >= first.first_day(),
        month_start() <= last.first_day(),
    )


def month_of(transaction: Transaction, categories: Mapping[UUID, Category]) -> Month:
    category_id = transaction.category_id
    if category_id is None and transaction.parts:
        category_id = transaction.parts[0].category_id
    category = categories.get(category_id) if category_id else None
    parent = categories.get(category.parent_id) if category and category.parent_id else None
    shift = (
        shift_day(category.shift_day, parent.shift_day if parent else None) if category else None
    )
    manual = Month.of(transaction.budget_month) if transaction.budget_month else None
    item = Booked(
        transaction.booked_on, manual=manual, transfer=transaction.transfer_group_id is not None
    )
    return budget_month(item, shift_from=shift)
