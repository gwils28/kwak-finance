from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from kwak_core.accounts import Scope
from kwak_core.budget import Month
from kwak_core.kpis import MonthFigures, savings_rate
from kwak_core.money import quantize
from kwak_core.reports import ReportPeriod, ReportRow, Section, relative_change, report_period
from pydantic import BaseModel

from kwak_api.auth.routes import CurrentSession, Db, Now
from kwak_api.budget.routes import FlowOut, flows_out
from kwak_api.models import Category
from kwak_api.services import reports as service

router = APIRouter(prefix="/api", tags=["reports"])

RATIO = Decimal("0.0001")
MAX_MONTHS = 120
YEARS = range(1900, 2201)


def _cents(value: Decimal) -> Decimal:
    return quantize(value)


def _ratio(value: Decimal | None) -> Decimal | None:
    return None if value is None else value.quantize(RATIO)


def _unprocessable(message: str) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, message)


def _month(text: str) -> Month:
    try:
        month = Month.parse(text)
    except ValueError:
        raise _unprocessable(f"invalid month {text!r}, expected YYYY-MM") from None
    if month.year not in YEARS:
        raise _unprocessable(f"invalid month {text!r}, expected YYYY-MM")
    return month


class PeriodTotals(BaseModel):
    """As the home page's KPIs (F-DSH-4), over the whole period."""

    spent: Decimal
    income: Decimal
    paid_in: Decimal
    """Transfers from accounts outside the scope; 0 for the household."""
    paid_out: Decimal
    """Transfers to accounts outside the scope; 0 for the household."""
    net: Decimal
    saved: Decimal
    """The part of `net` put in savings categories (F-CAT-4)."""
    savings_rate: Decimal | None

    @classmethod
    def of(cls, f: MonthFigures) -> "PeriodTotals":
        return cls(
            spent=_cents(f.spent),
            income=_cents(f.income),
            paid_in=_cents(f.paid_in),
            paid_out=_cents(f.paid_out),
            net=_cents(f.net),
            saved=_cents(f.saved),
            savings_rate=_ratio(savings_rate(f.inflow, f.net)),
        )


class ReportRowOut(BaseModel):
    section: Section
    category_id: UUID | None
    """Null: to categorise."""
    name: str | None
    amount: Decimal
    """Income received, spending net of refunds, savings net of withdrawals."""
    monthly_average: Decimal
    share: Decimal | None
    """Of the section's total, e.g. 0.1234."""
    previous: Decimal
    """Over the previous period of the same length."""
    change: Decimal | None
    """Against `previous`; null when it is zero."""
    children: list["ReportRowOut"]
    """The subcategories; the rest of `amount` was booked in the category itself."""

    @classmethod
    def of(
        cls,
        row: ReportRow,
        categories: dict[UUID, Category],
        months: int,
        totals: dict[Section, Decimal],
    ) -> "ReportRowOut":
        total = totals[row.section]
        category = categories.get(row.category_id) if row.category_id else None
        return cls(
            section=row.section,
            category_id=row.category_id,
            name=category.name if category else None,
            amount=_cents(row.amount),
            monthly_average=_cents(row.amount / months),
            share=_ratio(row.amount / total) if total > 0 else None,
            previous=_cents(row.previous),
            change=_ratio(relative_change(row.amount, row.previous)),
            children=[cls.of(c, categories, months, totals) for c in row.children],
        )


class SectionTotalOut(BaseModel):
    section: Section
    amount: Decimal
    monthly_average: Decimal
    previous: Decimal
    change: Decimal | None


class TotalsChange(BaseModel):
    """Against the previous period, by the size of its figure: from -500 to +200 is +1.4."""

    income: Decimal | None
    spent: Decimal | None
    net: Decimal | None
    saved: Decimal | None


class MonthTotals(BaseModel):
    month: str
    income: Decimal
    spent: Decimal
    net: Decimal


class ReportOut(BaseModel):
    start: str
    end: str
    """The last month covered: a running period stops at the current month."""
    to_date: bool
    """The period asked for runs past the current month: shown so far."""
    months: int
    previous_start: str
    previous_end: str
    totals: PeriodTotals
    previous: PeriodTotals
    changes: TotalsChange
    sections: list[SectionTotalOut]
    """Income, spending and savings: what their rows add up to."""
    rows: list[ReportRowOut]
    """Income, then spending, then savings: top-level categories, largest first."""
    monthly: list[MonthTotals]
    flows: list[FlowOut]
    """Both sides always add up to the same total."""


@router.get("/reports")
def period_report(
    user_session: CurrentSession,
    db: Db,
    now: Now,
    start: Annotated[str, Query(description="First budget month, YYYY-MM")],
    end: Annotated[str, Query(description="Last budget month, YYYY-MM, included")],
    scope: Scope = Scope.HOUSEHOLD,
) -> ReportOut:
    """Income and spending by category over a period, against the one before (F-DSH-2).

    A period running past the current month stops there and is compared with the same months
    of the period before."""
    first, last = _month(start), _month(end)
    count = (last.year - first.year) * 12 + last.month - first.month + 1
    if not 1 <= count <= MAX_MONTHS:
        raise _unprocessable(f"a report covers 1 to {MAX_MONTHS} months, from start to end")
    try:
        period: ReportPeriod = report_period(first, last, current=Month.of(now.date()))
    except ValueError as exc:
        raise _unprocessable(str(exc)) from None
    r = service.report(db, user_session.user, period, scope)
    months = period.months
    sections = {
        Section.INCOME: (r.totals.income, r.previous.income),
        Section.SPENDING: (r.totals.spent, r.previous.spent),
        Section.SAVINGS: (r.totals.saved, r.previous.saved),
    }
    totals = {section: amount for section, (amount, _) in sections.items()}
    return ReportOut(
        start=str(period.start),
        end=str(period.end),
        to_date=period.to_date,
        months=months,
        previous_start=str(period.previous_start),
        previous_end=str(period.previous_end),
        totals=PeriodTotals.of(r.totals),
        previous=PeriodTotals.of(r.previous),
        changes=TotalsChange(
            income=_ratio(relative_change(r.totals.income, r.previous.income)),
            spent=_ratio(relative_change(r.totals.spent, r.previous.spent)),
            net=_ratio(relative_change(r.totals.net, r.previous.net)),
            saved=_ratio(relative_change(r.totals.saved, r.previous.saved)),
        ),
        sections=[
            SectionTotalOut(
                section=section,
                amount=_cents(amount),
                monthly_average=_cents(amount / months),
                previous=_cents(previous),
                change=_ratio(relative_change(amount, previous)),
            )
            for section, (amount, previous) in sections.items()
        ],
        rows=[ReportRowOut.of(row, r.categories, months, totals) for row in r.rows],
        monthly=[
            MonthTotals(
                month=str(m),
                income=_cents(f.income),
                spent=_cents(f.spent),
                net=_cents(f.net),
            )
            for m, f in r.monthly
        ],
        flows=flows_out(r.flows),
    )
