"""Budget plans and the monthly budget matrix (F-BUD-1, 2, 3, 4, 6, 7)."""

import enum
from datetime import date
from decimal import Decimal
from uuid import UUID

from kwak_core.accounts import CASH_TYPES
from kwak_core.budget import DEFAULT_BAND, Matrix, Month, build_matrix
from kwak_core.categories import CategoryKind
from kwak_core.plans import (
    Period,
    PeriodKind,
    Plan,
    check_no_overlap,
    close_early,
    editable,
    new_plan,
    replacement,
)
from kwak_core.plans import target_history as plans_history
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from kwak_api.models import BudgetPlan, BudgetPlanTarget, Category, Transaction, User
from kwak_api.services.accounts import visible_accounts


class Scope(enum.StrEnum):
    HOUSEHOLD = "household"
    """Every account the viewer can see."""
    MINE = "mine"
    """Only the viewer's own accounts."""


class PlanConflictError(Exception):
    """The change would break a plan rule: overlap, or a plan past its first month."""


UNSET = object()
"""Marks a field left out of an update."""

FROZEN = "this plan can no longer be edited: close it early to change its targets"


def _core(plan: BudgetPlan) -> Plan:
    return Plan(
        Period(PeriodKind(plan.kind), plan.year, plan.number),
        {t.category_id: t.amount for t in plan.targets},
        Month.of(plan.start_month),
        Month.of(plan.end_month),
        plan.expected_income,
        plan.note,
        plan.close_reason,
    )


def is_editable(plan: BudgetPlan, today: date) -> bool:
    return editable(_core(plan), today)


def list_plans(db: Session, household_id: UUID) -> list[BudgetPlan]:
    return list(
        db.scalars(
            select(BudgetPlan)
            .where(BudgetPlan.household_id == household_id)
            .order_by(BudgetPlan.start_month)
        )
    )


def find_plan(db: Session, household_id: UUID, plan_id: UUID) -> BudgetPlan | None:
    plan = db.get(BudgetPlan, plan_id)
    return plan if plan is not None and plan.household_id == household_id else None


def _insert(db: Session, household_id: UUID, plan: Plan) -> BudgetPlan:
    try:
        check_no_overlap([*(_core(p) for p in list_plans(db, household_id)), plan])
    except ValueError as exc:
        raise PlanConflictError(str(exc)) from None
    row = BudgetPlan(
        household_id=household_id,
        kind=plan.period.kind.value,
        year=plan.period.year,
        number=plan.period.index,
        start_month=plan.start.first_day(),
        end_month=plan.end.first_day(),
        expected_income=plan.expected_income,
        note=plan.note,
        targets=[
            BudgetPlanTarget(category_id=cid, amount=amount) for cid, amount in plan.targets.items()
        ],
    )
    db.add(row)
    db.flush()
    return row


def create_plan(db: Session, household_id: UUID, period: Period) -> BudgetPlan:
    """A plan over `period`, pre-filled from the latest plan (F-BUD-7)."""
    plans = list_plans(db, household_id)
    latest = _core(plans[-1]) if plans else None
    return _insert(db, household_id, new_plan(period, latest))


def _require_editable(plan: BudgetPlan, today: date) -> None:
    if not is_editable(plan, today):
        raise PlanConflictError(FROZEN)


def set_plan_target(
    db: Session, plan: BudgetPlan, category: Category, amount: Decimal | None, today: date
) -> None:
    """Set (or remove, with None) the category's monthly target in the plan."""
    if category.kind is not CategoryKind.EXPENSE:
        raise ValueError("targets are set on expense categories")
    if amount is not None and amount < 0:
        raise ValueError("a target cannot be negative")
    _require_editable(plan, today)
    existing = next((t for t in plan.targets if t.category_id == category.id), None)
    if amount is None:
        if existing is not None:
            plan.targets.remove(existing)
    elif existing is None:
        plan.targets.append(BudgetPlanTarget(category_id=category.id, amount=amount))
    else:
        existing.amount = amount
    db.flush()


def update_plan(
    db: Session,
    plan: BudgetPlan,
    today: date,
    *,
    note: str | object | None = UNSET,
    expected_income: Decimal | object | None = UNSET,
) -> None:
    """The note changes any time; the expected income only while the plan is editable."""
    if isinstance(expected_income, Decimal) or expected_income is None:
        _require_editable(plan, today)
        plan.expected_income = expected_income
    if isinstance(note, str) or note is None:
        plan.note = note
    db.flush()


def close_plan(db: Session, plan: BudgetPlan, last_month: Month, reason: str | None) -> BudgetPlan:
    """Close the plan after `last_month` and return the replacement plan for the rest."""
    closed = close_early(_core(plan), last_month, reason)
    plan.end_month = closed.end.first_day()
    plan.close_reason = reason
    db.flush()
    return _insert(db, plan.household_id, replacement(closed))


def delete_plan(db: Session, plan: BudgetPlan, today: date) -> None:
    _require_editable(plan, today)
    db.delete(plan)
    db.flush()


def set_target(
    db: Session,
    household_id: UUID,
    category: Category,
    month: Month,
    amount: Decimal | None,
    today: date,
) -> BudgetPlan:
    """Set the target in the plan covering `month`, creating its quarter's plan if needed.

    Kept for the budget page's target editor until it manages plans itself.
    """
    plan = next(
        (
            p
            for p in list_plans(db, household_id)
            if p.start_month <= month.first_day() <= p.end_month
        ),
        None,
    ) or create_plan(db, household_id, Period.containing(PeriodKind.QUARTER, month))
    set_plan_target(db, plan, category, amount, today)
    return plan


def target_history(
    db: Session, household_id: UUID
) -> dict[UUID, list[tuple[Month, Decimal | None]]]:
    return plans_history([_core(p) for p in list_plans(db, household_id)])


def scoped_accounts(db: Session, viewer: User, scope: Scope) -> list[UUID]:
    """Cash accounts in scope: the ones whose transactions make up spending and income."""
    return [
        a.id
        for a in visible_accounts(db, viewer, include_closed=True)
        if a.type in CASH_TYPES and (scope is Scope.HOUSEHOLD or a.owner_id == viewer.id)
    ]


def matrix(
    db: Session,
    viewer: User,
    months: list[Month],
    *,
    scope: Scope = Scope.HOUSEHOLD,
    band: Decimal = DEFAULT_BAND,
) -> Matrix:
    accounts = scoped_accounts(db, viewer, scope)
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
