"""Reports over a period of budget months (F-DSH-2), by the home page's rules."""

from dataclasses import dataclass, replace
from decimal import Decimal
from uuid import UUID

from kwak_core.accounts import Scope
from kwak_core.budget import Month, month_range
from kwak_core.kpis import Flow, MonthFigures, month_figures
from kwak_core.reports import (
    ReportPeriod,
    ReportRow,
    by_category,
    report_rows,
    total_figures,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from kwak_api.models import Category, User
from kwak_api.services.budget import crossing_by_month, scoped_accounts
from kwak_api.services.dashboard import flows_by_month
from kwak_api.services.plan_review import PlanFlows, period_flows


@dataclass
class Report:
    period: ReportPeriod
    monthly: list[tuple[Month, MonthFigures]]
    totals: MonthFigures
    previous: MonthFigures
    rows: list[ReportRow]
    flows: PlanFlows
    categories: dict[UUID, Category]


def report(db: Session, viewer: User, period: ReportPeriod, scope: Scope) -> Report:
    accounts = scoped_accounts(db, viewer, scope)
    categories = {
        c.id: c
        for c in db.scalars(select(Category).where(Category.household_id == viewer.household_id))
    }
    kinds = {cid: c.kind for cid, c in categories.items()}
    parents = {cid: c.parent_id for cid, c in categories.items() if c.parent_id}
    months = month_range(period.start, period.end)
    previous_months = month_range(period.previous_start, period.previous_end)
    flows = flows_by_month(db, accounts, period.previous_start, period.end)
    crossed = crossing_by_month(db, accounts, previous_months + months) if accounts else {}

    def figures(m: Month) -> MonthFigures:
        paid_in, paid_out = crossed.get(m, (Decimal(0), Decimal(0)))
        return replace(month_figures(flows[m], kinds), paid_in=paid_in, paid_out=paid_out)

    def lines(period: list[Month]) -> list[Flow]:
        return [f for m in period for f in flows[m]]

    monthly = [(m, figures(m)) for m in months]
    return Report(
        period=period,
        monthly=monthly,
        totals=total_figures(f for _, f in monthly),
        previous=total_figures(figures(m) for m in previous_months),
        rows=report_rows(
            by_category(lines(months), kinds), by_category(lines(previous_months), kinds), parents
        ),
        flows=period_flows(db, viewer, months, scope=scope),
        categories=categories,
    )
