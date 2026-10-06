from datetime import date
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from kwak_core.budget import Month
from kwak_core.kpis import TopCategory, change, savings_rate
from pydantic import BaseModel

from kwak_api.auth.routes import CurrentSession, Db, Now
from kwak_api.services import dashboard as service
from kwak_api.services.budget import Scope

router = APIRouter(prefix="/api", tags=["dashboard"])

CENT = Decimal("0.01")
RATIO = Decimal("0.0001")


def _cents(value: Decimal) -> Decimal:
    return value.quantize(CENT)


def _ratio(value: Decimal | None) -> Decimal | None:
    return None if value is None else value.quantize(RATIO)


class Kpis(BaseModel):
    spent: Decimal
    income: Decimal
    net: Decimal
    """income - spent: the sum of the month's transactions, transfers excluded."""
    savings_rate: Decimal | None
    """net / income, e.g. 0.3564; null without income."""
    previous_spent: Decimal
    average_spent: Decimal
    """Average monthly spending over the previous 12 months that have transactions."""
    spent_change_vs_previous: Decimal | None
    spent_change_vs_average: Decimal | None


class CategorySpending(BaseModel):
    category_id: UUID
    name: str
    spent: Decimal
    share: Decimal | None
    """Of the month's spending."""


class ToCategorise(BaseModel):
    count: int
    spent: Decimal


class MonthPoint(BaseModel):
    month: str
    spent: Decimal
    income: Decimal
    by_category: list[CategorySpending]
    """Top-level expense categories, largest first."""


class DayPoint(BaseModel):
    day: date
    spent: Decimal
    """Spending from the 1st to this day included."""


class DashboardOut(BaseModel):
    month: str
    kpis: Kpis
    top_categories: list[CategorySpending]
    to_categorise: ToCategorise
    monthly: list[MonthPoint]
    cumulative: list[DayPoint]
    budget_target: Decimal | None
    """The month's total target (sum of the category targets), for the cumulative chart."""


def _categories(top: list[TopCategory], names: dict[UUID, str]) -> list[CategorySpending]:
    return [
        CategorySpending(
            category_id=t.category_id,
            name=names.get(t.category_id, ""),
            spent=_cents(t.spent),
            share=_ratio(t.share),
        )
        for t in top
    ]


@router.get("/dashboard")
def dashboard(
    user_session: CurrentSession,
    db: Db,
    now: Now,
    month: Annotated[str | None, Query(description="YYYY-MM; default: this month")] = None,
    scope: Scope = Scope.HOUSEHOLD,
) -> DashboardOut:
    """Spending KPIs and chart series (F-DSH-4, 5)."""
    try:
        when = Month.parse(month) if month else Month.of(now.date())
    except ValueError:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, f"invalid month {month!r}, expected YYYY-MM"
        ) from None
    d = service.dashboard(db, user_session.user, when, scope)
    current = d.current
    return DashboardOut(
        month=str(when),
        kpis=Kpis(
            spent=_cents(current.spent),
            income=_cents(current.income),
            net=_cents(current.net),
            savings_rate=_ratio(savings_rate(current.income, current.net)),
            previous_spent=_cents(d.previous.spent),
            average_spent=_cents(d.average_spent),
            spent_change_vs_previous=_ratio(change(current.spent, d.previous.spent)),
            spent_change_vs_average=_ratio(change(current.spent, d.average_spent)),
        ),
        top_categories=_categories(d.top, d.names),
        to_categorise=ToCategorise(
            count=d.to_categorise_count, spent=_cents(d.to_categorise_spent)
        ),
        monthly=[
            MonthPoint(
                month=str(m.month),
                spent=_cents(m.figures.spent),
                income=_cents(m.figures.income),
                by_category=_categories(m.by_category, d.names),
            )
            for m in d.monthly
        ],
        cumulative=[DayPoint(day=day, spent=_cents(total)) for day, total in d.cumulative],
        budget_target=d.budget_target,
    )
