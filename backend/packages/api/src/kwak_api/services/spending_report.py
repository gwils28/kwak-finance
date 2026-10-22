"""Reports on the spending lines over a period of months (F-DSH-2, F-DSH-5).

Every figure comes from the same queries as the month and the matrix (services.spending_budget),
so a report never disagrees with them (invariants §8.10, §8.18).
"""

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from kwak_core.budget import Month, month_range
from kwak_core.categories import CategoryKind
from kwak_core.reports import ReportPeriod
from kwak_core.spending import MonthFigures
from kwak_core.spending_report import Flow, overspent, report_flows
from sqlalchemy.orm import Session

from kwak_api.models import SpendingCategory
from kwak_api.services import spending
from kwak_api.services import spending_budget as budget

ZERO = Decimal(0)


@dataclass
class SpendingReport:
    period: ReportPeriod
    categories: dict[UUID, SpendingCategory]
    monthly: list[tuple[Month, MonthFigures]]
    by_month: dict[tuple[UUID, Month], Decimal]
    """Each category's amount in each month of the period."""
    totals: MonthFigures
    previous: MonthFigures
    current: dict[UUID, Decimal]
    """Each category's amount over the period."""
    before: dict[UUID, Decimal]
    """Over the previous period, empty when it is not compared."""
    flows: list[Flow]


def _categorised(amounts: budget.Spending) -> dict[tuple[UUID, Month], Decimal]:
    """Every line has a category (a split line's parts theirs): the None key never holds any."""
    return {(c, m): a for (c, m), a in amounts.items() if c is not None}


def _by_category(amounts: dict[tuple[UUID, Month], Decimal]) -> dict[UUID, Decimal]:
    out: dict[UUID, Decimal] = defaultdict(Decimal)
    for (category, _), amount in amounts.items():
        out[category] += amount
    return dict(out)


def report(db: Session, household_id: UUID, period: ReportPeriod) -> SpendingReport:
    categories = {c.id: c for c in spending.categories(db, household_id)}
    kinds = {cid: c.kind for cid, c in categories.items()}
    months = month_range(period.start, period.end)
    previous_months = (
        month_range(period.previous_start, period.previous_end) if period.compared else []
    )
    figures = budget.figures_by_month(db, household_id, previous_months + months, kinds)
    by_month = _categorised(budget.spending_by_month(db, household_id, period.start, period.end))
    before = (
        _categorised(
            budget.spending_by_month(db, household_id, period.previous_start, period.previous_end)
        )
        if period.compared
        else {}
    )
    monthly = [(m, figures[m]) for m in months]
    totals = sum((f for _, f in monthly), MonthFigures.zero())
    current = _by_category(by_month)
    spent = {c: a for c, a in current.items() if kinds.get(c) is CategoryKind.EXPENSE}
    over = overspent(by_month, budget.targets(db, household_id), months)
    return SpendingReport(
        period=period,
        categories=categories,
        monthly=monthly,
        by_month=by_month,
        totals=totals,
        previous=sum((figures[m] for m in previous_months), MonthFigures.zero()),
        current=current,
        before=_by_category(before),
        flows=report_flows(income=totals.income, spent=spent, saved=totals.saved, over=over),
    )
