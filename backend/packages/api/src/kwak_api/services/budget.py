"""Budget targets and the monthly budget matrix (F-BUD-1, 2, 3, 4, 6)."""

import enum
from collections import defaultdict
from decimal import Decimal
from uuid import UUID

from kwak_core.accounts import CASH_TYPES
from kwak_core.budget import DEFAULT_BAND, Matrix, Month, build_matrix, target_for
from kwak_core.categories import CategoryKind
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from kwak_api.models import BudgetTarget, Category, Transaction, User
from kwak_api.services.accounts import visible_accounts


class Scope(enum.StrEnum):
    HOUSEHOLD = "household"
    """Every account the viewer can see."""
    MINE = "mine"
    """Only the viewer's own accounts."""


def set_target(
    db: Session, household_id: UUID, category: Category, month: Month, amount: Decimal | None
) -> BudgetTarget:
    """Set (or remove, with None) the category's target from `month` on."""
    if category.kind is not CategoryKind.EXPENSE:
        raise ValueError("targets are set on expense categories")
    if amount is not None and amount < 0:
        raise ValueError("a target cannot be negative")
    target = db.scalar(
        select(BudgetTarget).where(
            BudgetTarget.category_id == category.id, BudgetTarget.valid_from == month.first_day()
        )
    )
    if target is None:
        target = BudgetTarget(
            household_id=household_id, category_id=category.id, valid_from=month.first_day()
        )
        db.add(target)
    target.amount = amount
    db.flush()
    return target


def target_history(
    db: Session, household_id: UUID
) -> dict[UUID, list[tuple[Month, Decimal | None]]]:
    history: dict[UUID, list[tuple[Month, Decimal | None]]] = defaultdict(list)
    for t in db.scalars(select(BudgetTarget).where(BudgetTarget.household_id == household_id)):
        history[t.category_id].append((Month.of(t.valid_from), t.amount))
    return history


def current_targets(
    db: Session, household_id: UUID, month: Month
) -> list[tuple[UUID, Decimal, Month]]:
    """(category, amount, since) of every target in force in `month`."""
    current = []
    for category_id, history in target_history(db, household_id).items():
        amount = target_for(history, month)
        if amount is not None:
            since = max(start for start, _ in history if start <= month)
            current.append((category_id, amount, since))
    return current


def matrix(
    db: Session,
    viewer: User,
    months: list[Month],
    *,
    scope: Scope = Scope.HOUSEHOLD,
    band: Decimal = DEFAULT_BAND,
) -> Matrix:
    accounts = [
        a.id
        for a in visible_accounts(db, viewer, include_closed=True)
        if a.type in CASH_TYPES and (scope is Scope.HOUSEHOLD or a.owner_id == viewer.id)
    ]
    expense = list(
        db.scalars(
            select(Category).where(
                Category.household_id == viewer.household_id,
                Category.kind == CategoryKind.EXPENSE,
            )
        )
    )
    expense_ids = {c.id for c in expense}
    month_start = func.date_trunc("month", Transaction.booked_on)
    # Categorised: outflows minus refunds. Uncategorised: outflows only (an inflow may be income).
    spent = func.sum(
        case(
            (
                Transaction.category_id.is_(None),
                case((Transaction.amount < 0, -Transaction.amount), else_=0),
            ),
            else_=-Transaction.amount,
        )
    )
    rows = db.execute(
        select(Transaction.category_id, month_start, spent)
        .where(
            Transaction.account_id.in_(accounts),
            Transaction.transfer_group_id.is_(None),  # transfers are not spending (§8.3)
            Transaction.booked_on >= months[0].first_day(),
            Transaction.booked_on < months[-1].next().first_day(),
        )
        .group_by(Transaction.category_id, month_start)
    )
    spending: dict[tuple[UUID | None, Month], Decimal] = {}
    for category_id, start, total in rows:
        if category_id is None or category_id in expense_ids:
            spending[(category_id, Month.of(start))] = Decimal(total)
    return build_matrix(
        [(c.id, c.parent_id, c.name) for c in expense],
        target_history(db, viewer.household_id),
        spending,
        months,
        band,
    )
