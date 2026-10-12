"""Budget plan review and its steering dashboards (F-BUD-8, F-DSH-6)."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from kwak_core.accounts import AccountType, Scope
from kwak_core.budget import DEFAULT_BAND, Month
from kwak_core.categories import CategoryKind
from kwak_core.flows import Flow as MoneyFlow
from kwak_core.flows import money_flows, saved
from kwak_core.kpis import Flow, month_figures
from kwak_core.plans import (
    ComparisonRow,
    CumulativePoint,
    Review,
    compare,
    cumulative,
    for_scope,
    review_plan,
)
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from kwak_api.models import BudgetPlan, Category, Transaction, User
from kwak_api.services.accounts import visible_accounts
from kwak_api.services.budget import (
    core_plan,
    crossing_by_month,
    list_plans,
    scoped_accounts,
    spending,
    transfer_legs,
)


def _categories(db: Session, household_id: UUID) -> dict[UUID, Category]:
    return {
        c.id: c for c in db.scalars(select(Category).where(Category.household_id == household_id))
    }


def _income(db: Session, viewer: User, months: list[Month], scope: Scope) -> dict[Month, Decimal]:
    """Income per month, by the home page's rules (F-DSH-4)."""
    kinds = {cid: c.kind for cid, c in _categories(db, viewer.household_id).items()}
    start_of = func.date_trunc("month", Transaction.booked_on)
    # One labelled expression in SELECT and GROUP BY (see services.dashboard).
    outflow = (Transaction.amount < 0).label("outflow")
    rows = db.execute(
        select(start_of, Transaction.category_id, outflow, func.sum(Transaction.amount))
        .where(
            Transaction.account_id.in_(scoped_accounts(db, viewer, scope)),
            Transaction.transfer_group_id.is_(None),
            Transaction.booked_on >= months[0].first_day(),
            Transaction.booked_on < months[-1].next().first_day(),
        )
        .group_by(start_of, Transaction.category_id, outflow)
    )
    flows: dict[Month, list[Flow]] = defaultdict(list)
    for start, category_id, _outflow, total in rows:
        flows[Month.of(start)].append(Flow(category_id, Decimal(total)))
    return {m: month_figures(f, kinds).income for m, f in flows.items()}


def review(
    db: Session,
    viewer: User,
    plan: BudgetPlan,
    today: date,
    *,
    scope: Scope = Scope.HOUSEHOLD,
    band: Decimal = DEFAULT_BAND,
) -> Review:
    core = for_scope(core_plan(plan), scope)
    spent = spending(db, viewer, core.months, scope)
    expense, savings = spent.matrix_categories()
    accounts = scoped_accounts(db, viewer, scope)
    return review_plan(
        core,
        expense,
        spent.amounts,
        _income(db, viewer, core.months, scope),
        today,
        band,
        paid=crossing_by_month(db, accounts, core.months) if accounts else None,
        savings=savings,
    )


def cumulative_chart(
    db: Session,
    viewer: User,
    plan: BudgetPlan,
    today: date,
    *,
    category: Category | None = None,
    scope: Scope = Scope.HOUSEHOLD,
) -> tuple[Decimal, list[CumulativePoint]]:
    """The envelope and the day-by-day points, in total or for one expense category."""
    if category is not None and category.kind is not CategoryKind.EXPENSE:
        raise ValueError("the cumulative chart is for an expense category")
    result = review(db, viewer, plan, today, scope=scope)
    row = (
        result.total
        if category is None
        else next(r for r in result.rows if r.category_id == category.id)
    )
    categories = _categories(db, viewer.household_id)
    counted = (
        None
        if category is None
        else {category.id} | {cid for cid, c in categories.items() if c.parent_id == category.id}
    )
    core = result.plan
    daily: dict[date, Decimal] = defaultdict(Decimal)
    for booked_on, category_id, amount in db.execute(
        select(Transaction.booked_on, Transaction.category_id, Transaction.amount).where(
            Transaction.account_id.in_(scoped_accounts(db, viewer, scope)),
            Transaction.transfer_group_id.is_(None),
            Transaction.booked_on >= core.start.first_day(),
            Transaction.booked_on < core.end.next().first_day(),
        )
    ):
        kind = categories[category_id].kind if category_id else None
        if counted is not None:
            if category_id in counted:
                daily[booked_on] -= amount  # net of refunds, as the matrix
        elif kind is CategoryKind.EXPENSE:
            daily[booked_on] -= amount
        elif kind is None and amount < 0:
            daily[booked_on] -= amount  # to categorise: outflows only
    envelope = row.envelope or Decimal(0)
    return envelope, cumulative(core, daily, envelope, today)


def previous_plan(db: Session, plan: BudgetPlan) -> BudgetPlan | None:
    """The latest plan before this one."""
    earlier = [p for p in list_plans(db, plan.household_id) if p.start_month < plan.start_month]
    return earlier[-1] if earlier else None


def comparison(
    db: Session,
    viewer: User,
    a: BudgetPlan,
    b: BudgetPlan,
    today: date,
    *,
    scope: Scope = Scope.HOUSEHOLD,
) -> list[ComparisonRow]:
    """Plan b's rows next to plan a's, on monthly figures."""
    return compare(
        review(db, viewer, a, today, scope=scope), review(db, viewer, b, today, scope=scope)
    )


@dataclass
class PlanFlows:
    flows: list[MoneyFlow]
    categories: dict[UUID, Category]


def flows(db: Session, viewer: User, plan: BudgetPlan, *, scope: Scope) -> PlanFlows:
    """Where the plan's money came from and went (F-DSH-2), by the review's rules."""
    months = core_plan(plan).months
    categories = _categories(db, viewer.household_id)
    in_scope = set(scoped_accounts(db, viewer, scope))
    visible = [a for a in visible_accounts(db, viewer, include_closed=True) if a.id in in_scope]
    accounts = [a.id for a in visible]
    income: dict[UUID, Decimal] = defaultdict(Decimal)
    spent: dict[UUID, Decimal] = defaultdict(Decimal)
    uncategorised_in = uncategorised_out = in_categories = Decimal(0)
    outflow = (Transaction.amount < 0).label("outflow")
    rows = db.execute(
        select(Transaction.category_id, outflow, func.sum(Transaction.amount))
        .where(
            Transaction.account_id.in_(accounts),
            Transaction.transfer_group_id.is_(None),
            Transaction.booked_on >= months[0].first_day(),
            Transaction.booked_on < months[-1].next().first_day(),
        )
        .group_by(Transaction.category_id, outflow)
    )
    for category_id, is_outflow, total in rows:
        amount = Decimal(total)
        if category_id is None:
            if is_outflow:
                uncategorised_out -= amount
            else:
                uncategorised_in += amount
        elif categories[category_id].kind is CategoryKind.EXPENSE:
            spent[category_id] -= amount
        elif categories[category_id].kind is CategoryKind.SAVINGS:
            in_categories -= amount  # saved like a transfer to a savings account (F-CAT-4)
        else:
            income[category_id] += amount
    crossed = crossing_by_month(db, accounts, months)
    legs = [leg for leg, _ in transfer_legs(db, accounts, months)]
    savings = {a.id for a in visible if a.type is AccountType.SAVINGS}
    return PlanFlows(
        money_flows(
            income=income,
            spending=spent,
            uncategorised_in=uncategorised_in,
            uncategorised_out=uncategorised_out,
            paid_in=sum((p[0] for p in crossed.values()), Decimal(0)),
            paid_out=sum((p[1] for p in crossed.values()), Decimal(0)),
            saved=saved(legs, in_scope, savings=savings) + in_categories,
        ),
        categories,
    )
