"""Budget plan review and its steering dashboards (F-BUD-8, F-DSH-6)."""

from collections import defaultdict
from datetime import date
from decimal import Decimal
from uuid import UUID

from kwak_core.budget import DEFAULT_BAND, Month
from kwak_core.categories import CategoryKind
from kwak_core.kpis import Flow, month_figures
from kwak_core.plans import ComparisonRow, CumulativePoint, Review, compare, cumulative, review_plan
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from kwak_api.models import BudgetPlan, Category, Transaction, User
from kwak_api.services.budget import Scope, core_plan, list_plans, scoped_accounts, spending


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
    core = core_plan(plan)
    expense, spent = spending(db, viewer, core.months, scope)
    return review_plan(
        core,
        [(c.id, c.parent_id, c.name) for c in expense],
        spent,
        _income(db, viewer, core.months, scope),
        today,
        band,
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
