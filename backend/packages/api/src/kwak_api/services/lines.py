"""Transactions as category lines, for every figure by category (F-TX-4, invariant §8.2).

A transaction counts once in its category; a split one counts once per part, each in the part's
category for the part's amount. Join a query with `with_parts`, then read `category()` and
`amount()` instead of the transaction's own columns.
"""

from decimal import Decimal
from uuid import UUID

from sqlalchemy import ColumnElement, Select, func

from kwak_api.models import Transaction, TransactionPart


def with_parts[*Ts](query: Select[*Ts]) -> Select[*Ts]:
    return query.select_from(Transaction).outerjoin(
        TransactionPart, TransactionPart.transaction_id == Transaction.id
    )


def category() -> ColumnElement[UUID | None]:
    """The part's category, or the transaction's when it is not split (a split transaction
    has none of its own)."""
    return func.coalesce(TransactionPart.category_id, Transaction.category_id)


def amount() -> ColumnElement[Decimal]:
    return func.coalesce(TransactionPart.amount, Transaction.amount)
