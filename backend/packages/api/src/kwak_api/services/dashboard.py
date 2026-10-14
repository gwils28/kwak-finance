"""Spending KPIs and chart series for the home page (F-DSH-4, 5)."""

from collections import defaultdict
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from uuid import UUID

from kwak_core.accounts import Scope
from kwak_core.budget import Month, month_range
from kwak_core.budget_month import budget_day
from kwak_core.categories import CategoryKind
from kwak_core.kpis import (
    Flow,
    MonthFigures,
    TopCategory,
    cumulative_by_day,
    month_figures,
    top_categories,
)
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from kwak_api.models import Category, Transaction, User
from kwak_api.services import budget_month, lines
from kwak_api.services.budget import crossing_by_month, matrix, scoped_accounts

HISTORY_MONTHS = 12


@dataclass
class MonthSummary:
    month: Month
    figures: MonthFigures
    by_category: list[TopCategory]
    """Every top-level expense category with spending, largest first."""


@dataclass
class Dashboard:
    month: Month
    current: MonthFigures
    previous: MonthFigures
    average_spent: Decimal
    """Average spending of the months with transactions among the 12 before `month`."""
    top: list[TopCategory]
    to_categorise_count: int
    to_categorise_spent: Decimal
    monthly: list[MonthSummary]
    """The 12 months ending with `month`."""
    cumulative: list[tuple[date, Decimal]]
    budget_target: Decimal | None
    names: dict[UUID, str]


def _back(month: Month, count: int) -> Month:
    index = month.year * 12 + month.month - 1 - count
    return Month(index // 12, index % 12 + 1)


def _spent(category_id: UUID | None, amount: Decimal, kinds: dict[UUID, CategoryKind]) -> Decimal:
    """What one transaction adds to spending (refunds subtract)."""
    kind = kinds.get(category_id) if category_id else None
    if kind is CategoryKind.EXPENSE or (kind is None and amount < 0):
        return -amount
    return Decimal(0)


def flows_by_month(
    db: Session, accounts: list[UUID], first: Month, last: Month
) -> defaultdict[Month, list[Flow]]:
    """Per budget month, the transactions of `accounts` (transfers excluded) summed by
    category and sign: what the KPIs are computed from."""
    start_of = budget_month.month_start().label("month")
    # One labelled expression in SELECT and GROUP BY: written twice, each copy gets its own
    # bound parameter and Postgres sees two different expressions.
    outflow = (Transaction.amount < 0).label("outflow")
    category = lines.category().label("category_id")
    rows = db.execute(
        lines.with_parts(select(start_of, category, outflow, func.sum(lines.amount())))
        .where(
            Transaction.account_id.in_(accounts),
            Transaction.transfer_group_id.is_(None),
            budget_month.in_months(first, last),
        )
        .group_by(start_of, category, outflow)
    )
    flows: defaultdict[Month, list[Flow]] = defaultdict(list)
    for start, category_id, _outflow, total in rows:
        flows[Month.of(start)].append(Flow(category_id, Decimal(total)))
    return flows


def dashboard(db: Session, viewer: User, month: Month, scope: Scope) -> Dashboard:
    accounts = scoped_accounts(db, viewer, scope)
    categories = list(
        db.scalars(select(Category).where(Category.household_id == viewer.household_id))
    )
    kinds = {c.id: c.kind for c in categories}
    parents = {c.id: c.parent_id for c in categories if c.parent_id}
    names = {c.id: c.name for c in categories}

    first = _back(month, HISTORY_MONTHS)  # one more month for the 12-month average
    months = month_range(first, month)
    flows = flows_by_month(db, accounts, first, month)

    crossed = crossing_by_month(db, accounts, months) if accounts else {}

    def summary(m: Month) -> MonthSummary:
        paid_in, paid_out = crossed.get(m, (Decimal(0), Decimal(0)))
        figures = replace(month_figures(flows[m], kinds), paid_in=paid_in, paid_out=paid_out)
        spending: dict[UUID, Decimal] = defaultdict(Decimal)
        for f in flows[m]:
            if f.category_id and kinds.get(f.category_id) is CategoryKind.EXPENSE:
                spending[f.category_id] -= f.amount
        by_category = top_categories(spending, parents, total=figures.spent, limit=len(names) + 1)
        return MonthSummary(m, figures, by_category)

    summaries = {m: summary(m) for m in months}
    # Months before the household's first transaction are not months of zero spending.
    history = [summaries[m].figures.spent for m in months[:-1] if flows[m]]

    daily: dict[date, Decimal] = defaultdict(Decimal)
    uncategorised: set[UUID] = set()
    uncategorised_spent = Decimal(0)
    for transaction_id, booked_on, category_id, amount in db.execute(
        lines.with_parts(
            select(Transaction.id, Transaction.booked_on, lines.category(), lines.amount())
        ).where(
            Transaction.account_id.in_(accounts),
            Transaction.transfer_group_id.is_(None),
            budget_month.in_months(month, month),
        )
    ):
        # A transaction counted in this month from another one sits at its edge (F-TX-7).
        daily[budget_day(booked_on, month)] += _spent(category_id, amount, kinds)
        if category_id is None:
            # A split transaction counts once, however many of its parts are uncategorised.
            uncategorised.add(transaction_id)
            uncategorised_spent += -amount if amount < 0 else Decimal(0)

    current = summaries[month]
    return Dashboard(
        month=month,
        current=current.figures,
        previous=summaries[months[-2]].figures,
        average_spent=sum(history, Decimal(0)) / len(history) if history else Decimal(0),
        top=current.by_category[:5],
        to_categorise_count=len(uncategorised),
        to_categorise_spent=uncategorised_spent,
        monthly=[summaries[m] for m in months[1:]],
        cumulative=cumulative_by_day(month.year, month.month, daily),
        budget_target=matrix(db, viewer, [month], scope=scope).total.cells[0].target,
        names=names,
    )
