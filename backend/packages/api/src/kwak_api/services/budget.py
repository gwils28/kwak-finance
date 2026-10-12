"""Budget plans and the monthly budget matrix (F-BUD-1, 2, 3, 4, 6, 7, 9)."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from kwak_core.accounts import CASH_TYPES, Scope, in_scope
from kwak_core.budget import DEFAULT_BAND, Categories, Matrix, Month, build_matrix
from kwak_core.categories import CategoryKind
from kwak_core.kpis import TransferLeg, crossing
from kwak_core.plans import (
    PaidFrom,
    Period,
    PeriodKind,
    Plan,
    check_no_overlap,
    close_early,
    editable,
    for_scope,
    new_plan,
    replacement,
)
from kwak_core.plans import target_history as plans_history
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from kwak_api.models import BudgetPlan, BudgetPlanTarget, Category, Transaction, User
from kwak_api.services.accounts import visible_accounts


class PlanConflictError(Exception):
    """The change would break a plan rule: overlap, or a plan past its first month."""


UNSET = object()
"""Marks a field left out of an update."""

FROZEN = "this plan can no longer be edited: close it early to change its targets"


def core_plan(plan: BudgetPlan) -> Plan:
    return Plan(
        Period(PeriodKind(plan.kind), plan.year, plan.number),
        {t.category_id: t.amount for t in plan.targets},
        Month.of(plan.start_month),
        Month.of(plan.end_month),
        plan.expected_income,
        plan.note,
        plan.close_reason,
        {t.category_id: t.paid_from for t in plan.targets if t.paid_from is not None},
    )


def is_editable(plan: BudgetPlan, today: date) -> bool:
    return editable(core_plan(plan), today)


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
        check_no_overlap([*(core_plan(p) for p in list_plans(db, household_id)), plan])
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
            BudgetPlanTarget(category_id=cid, amount=amount, paid_from=plan.paid_from.get(cid))
            for cid, amount in plan.targets.items()
        ],
    )
    db.add(row)
    db.flush()
    return row


def create_plan(db: Session, household_id: UUID, period: Period) -> BudgetPlan:
    """A plan over `period`, pre-filled from the latest plan (F-BUD-7)."""
    plans = list_plans(db, household_id)
    latest = core_plan(plans[-1]) if plans else None
    return _insert(db, household_id, new_plan(period, latest))


def _require_editable(plan: BudgetPlan, today: date) -> None:
    if not is_editable(plan, today):
        raise PlanConflictError(FROZEN)


def set_plan_target(
    db: Session, plan: BudgetPlan, category: Category, amount: Decimal | None, today: date
) -> None:
    """Set (or remove, with None) the category's monthly target in the plan: an objective, a
    minimum, for a savings category (F-BUD-9)."""
    if category.kind is CategoryKind.INCOME:
        raise ValueError("targets are set on expense and savings categories")
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
    closed = close_early(core_plan(plan), last_month, reason)
    plan.end_month = closed.end.first_day()
    plan.close_reason = reason
    db.flush()
    return _insert(db, plan.household_id, replacement(closed))


def delete_plan(db: Session, plan: BudgetPlan, today: date) -> None:
    _require_editable(plan, today)
    db.delete(plan)
    db.flush()


def set_paid_from(plan: BudgetPlan, category: Category, paid_from: PaidFrom | None) -> None:
    """Who pays a target's category. Allowed on a frozen plan: no envelope changes."""
    target = next((t for t in plan.targets if t.category_id == category.id), None)
    if target is None:
        raise ValueError("set a target for this category first")
    target.paid_from = paid_from


def target_history(
    db: Session, household_id: UUID, scope: Scope = Scope.HOUSEHOLD
) -> dict[UUID, list[tuple[Month, Decimal | None]]]:
    return plans_history([for_scope(core_plan(p), scope) for p in list_plans(db, household_id)])


def scoped_accounts(db: Session, viewer: User, scope: Scope) -> list[UUID]:
    """Cash accounts in scope: the ones whose transactions make up spending and income."""
    return [
        a.id
        for a in visible_accounts(db, viewer, include_closed=True)
        if a.type in CASH_TYPES
        and in_scope(scope, owner_id=a.owner_id, visibility=a.visibility, viewer_id=viewer.id)
    ]


def transfer_legs(
    db: Session, accounts: list[UUID], months: list[Month]
) -> list[tuple[TransferLeg, date]]:
    """Every leg of the transfers touching `accounts` within `months`, other legs included."""
    groups = (
        select(Transaction.transfer_group_id)
        .where(
            Transaction.account_id.in_(accounts),
            Transaction.transfer_group_id.is_not(None),
            Transaction.booked_on >= months[0].first_day(),
            Transaction.booked_on < months[-1].next().first_day(),
        )
        .scalar_subquery()
    )
    rows = db.execute(
        select(
            Transaction.transfer_group_id,
            Transaction.account_id,
            Transaction.amount,
            Transaction.booked_on,
        ).where(Transaction.transfer_group_id.in_(groups))
    ).all()
    return [
        (TransferLeg(group, account, amount), booked_on)
        for group, account, amount, booked_on in rows
        if group is not None
    ]


def crossing_by_month(
    db: Session, accounts: list[UUID], months: list[Month]
) -> dict[Month, tuple[Decimal, Decimal]]:
    """(paid in, paid out) of `accounts` per month by transfers with any other account."""
    legs = transfer_legs(db, accounts, months)
    # A transfer belongs to the month of its leg in scope; its other leg comes along.
    by_month: dict[Month, set[UUID]] = defaultdict(set)
    scope = set(accounts)
    for leg, booked_on in legs:
        if leg.account_id in scope:
            by_month[Month.of(booked_on)].add(leg.group_id)
    return {
        m: crossing([leg for leg, _ in legs if leg.group_id in groups_of_month], scope)
        for m, groups_of_month in by_month.items()
        if m in months
    }


@dataclass
class Spending:
    expense: list[Category]
    savings: list[Category]
    amounts: dict[tuple[UUID | None, Month], Decimal]
    """Per category (None: to categorise) and month: what an expense category spent, net of
    refunds, and what a savings category received, net of withdrawals."""

    def matrix_categories(self) -> tuple[Categories, Categories]:
        return (
            [(c.id, c.parent_id, c.name) for c in self.expense],
            [(c.id, c.parent_id, c.name) for c in self.savings],
        )


def spending(db: Session, viewer: User, months: list[Month], scope: Scope) -> Spending:
    accounts = scoped_accounts(db, viewer, scope)
    categories = list(
        db.scalars(
            select(Category).where(
                Category.household_id == viewer.household_id,
                Category.kind != CategoryKind.INCOME,
            )
        )
    )
    expense = [c for c in categories if c.kind is CategoryKind.EXPENSE]
    savings = [c for c in categories if c.kind is CategoryKind.SAVINGS]
    counted = {c.id for c in categories}
    month_start = func.date_trunc("month", Transaction.booked_on)
    # Categorised: outflows minus refunds (or withdrawals, for savings). Uncategorised: outflows
    # only (an inflow may be income).
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
    result: dict[tuple[UUID | None, Month], Decimal] = {}
    for category_id, start, total in rows:
        if category_id is None or category_id in counted:
            result[(category_id, Month.of(start))] = Decimal(total)
    return Spending(expense, savings, result)


def matrix(
    db: Session,
    viewer: User,
    months: list[Month],
    *,
    scope: Scope = Scope.HOUSEHOLD,
    band: Decimal = DEFAULT_BAND,
) -> Matrix:
    spent = spending(db, viewer, months, scope)
    expense, savings = spent.matrix_categories()
    return build_matrix(
        expense,
        target_history(db, viewer.household_id, scope),
        spent.amounts,
        months,
        band,
        savings=savings,
    )
