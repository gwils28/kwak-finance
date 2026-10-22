"""Reports on the spending lines (F-DSH-2, F-DSH-5): any period of whole months against the one
before, by category, month by month, and where the money went.

Spent and saved are positive amounts here; ratios have four decimals (0.1 = 10 %).
"""

import enum
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query
from kwak_core.budget import Month
from kwak_core.categories import CategoryKind
from kwak_core.money import quantize
from kwak_core.reports import relative_change, report_period
from kwak_core.spending_report import FlowKind, Side, period_lines
from pydantic import BaseModel

from kwak_api.auth.routes import CurrentSession, Db, Now
from kwak_api.services import spending_budget
from kwak_api.services import spending_report as service
from kwak_api.spending.budget import SpendingChangesOut, SpendingFiguresOut
from kwak_api.spending.routes import MonthText, _month, _unprocessable

router = APIRouter(prefix="/api/spending", tags=["spending"])

RATIO = Decimal("0.0001")
MAX_MONTHS = 120
ZERO = Decimal(0)


def _ratio(value: Decimal | None) -> Decimal | None:
    return None if value is None else value.quantize(RATIO)


class ReportSection(enum.StrEnum):
    SPENDING = "spending"
    SAVINGS = "savings"


SECTION_OF = {
    CategoryKind.EXPENSE: ReportSection.SPENDING,
    CategoryKind.SAVINGS: ReportSection.SAVINGS,
}


class SpendingReportRowOut(BaseModel):
    section: ReportSection
    category_id: UUID
    name: str
    amount: Decimal
    monthly_average: Decimal
    share: Decimal | None
    """Of the section's total."""
    previous: Decimal
    change: Decimal | None
    """Against `previous`; None when it is zero or the period is not compared."""


class SpendingReportSectionOut(BaseModel):
    section: ReportSection
    amount: Decimal
    monthly_average: Decimal
    previous: Decimal
    change: Decimal | None


class SpendingReportCategoryOut(BaseModel):
    category_id: UUID
    name: str
    spent: Decimal


class SpendingReportMonthOut(BaseModel):
    month: str
    income: Decimal
    spent: Decimal
    saved: Decimal
    rest: Decimal
    by_category: list[SpendingReportCategoryOut]
    """The expense categories that spent that month."""


class SpendingFlowOut(BaseModel):
    kind: FlowKind
    side: Side
    """"in": where the money came from; "out": where it went."""
    amount: Decimal
    category_id: UUID | None
    name: str | None
    """The category's name, for spending flows."""
    over: bool
    """Spending over its category's targets for the period."""


class SpendingReportOut(BaseModel):
    start: str
    end: str
    """The last month covered: a running period stops at the current month."""
    to_date: bool
    """The period asked for runs past the current month: shown so far."""
    first_month: str | None
    """The first month with a line or an income: a period starts no earlier."""
    months: int
    previous_start: str
    previous_end: str
    compared: bool
    """False when the previous period reaches before the first month: nothing is compared."""
    totals: SpendingFiguresOut
    previous: SpendingFiguresOut
    changes: SpendingChangesOut
    sections: list[SpendingReportSectionOut]
    rows: list[SpendingReportRowOut]
    """Spending, then savings, largest first."""
    monthly: list[SpendingReportMonthOut]
    flows: list[SpendingFlowOut]
    """Both sides always add up to the same total."""


def _change(current: Decimal, previous: Decimal, compared: bool) -> Decimal | None:
    return _ratio(relative_change(current, previous)) if compared else None


@router.get("/report")
def spending_report(
    user_session: CurrentSession,
    db: Db,
    now: Now,
    start: Annotated[MonthText, Query(description="First month, YYYY-MM")],
    end: Annotated[MonthText, Query(description="Last month, YYYY-MM, included")],
) -> SpendingReportOut:
    """Spending and savings by category over a period, against the one before (F-DSH-2).

    A period running past the current month stops there and is compared with the same months
    of the period before; months before the first line or income are left out."""
    household_id = user_session.user.household_id
    first, last = _month(start), _month(end)
    count = (last.year - first.year) * 12 + last.month - first.month + 1
    if not 1 <= count <= MAX_MONTHS:
        raise _unprocessable(f"a report covers 1 to {MAX_MONTHS} months, from start to end")
    since = spending_budget.first_month(db, household_id)
    # A period over before any data is simply empty.
    if since is not None and last < since:
        since = None
    try:
        period = report_period(first, last, current=Month.of(now.date()), since=since)
    except ValueError as exc:
        raise _unprocessable(str(exc)) from None

    r = service.report(db, household_id, period)
    months = Decimal(period.months)
    compared = period.compared
    names = {cid: c.name for cid, c in r.categories.items()}
    sections = {
        ReportSection.SPENDING: (r.totals.spent, r.previous.spent),
        ReportSection.SAVINGS: (r.totals.saved, r.previous.saved),
    }
    rows = []
    for kind, section in SECTION_OF.items():
        ids = {cid for cid, c in r.categories.items() if c.kind is kind}
        total = sections[section][0]
        for cid, amount, previous in period_lines(
            {c: a for c, a in r.current.items() if c in ids},
            {c: a for c, a in r.before.items() if c in ids},
        ):
            rows.append(
                SpendingReportRowOut(
                    section=section,
                    category_id=cid,
                    name=names[cid],
                    amount=quantize(amount),
                    monthly_average=quantize(amount / months),
                    share=_ratio(amount / total) if total > 0 else None,
                    previous=quantize(previous),
                    change=_change(amount, previous, compared),
                )
            )
    expense = {cid for cid, c in r.categories.items() if c.kind is CategoryKind.EXPENSE}
    return SpendingReportOut(
        start=str(period.start),
        end=str(period.end),
        to_date=period.to_date,
        first_month=str(since) if since else None,
        months=period.months,
        previous_start=str(period.previous_start),
        previous_end=str(period.previous_end),
        compared=compared,
        totals=SpendingFiguresOut.of(r.totals),
        previous=SpendingFiguresOut.of(r.previous),
        changes=SpendingChangesOut.between(r.totals, r.previous)
        if compared
        else SpendingChangesOut(income=None, spent=None, saved=None, rest=None),
        sections=[
            SpendingReportSectionOut(
                section=section,
                amount=quantize(amount),
                monthly_average=quantize(amount / months),
                previous=quantize(previous),
                change=_change(amount, previous, compared),
            )
            for section, (amount, previous) in sections.items()
        ],
        rows=rows,
        monthly=[
            SpendingReportMonthOut(
                month=str(m),
                income=quantize(f.income),
                spent=quantize(f.spent),
                saved=quantize(f.saved),
                rest=quantize(f.rest),
                by_category=sorted(
                    (
                        SpendingReportCategoryOut(
                            category_id=cid, name=names[cid], spent=quantize(amount)
                        )
                        for (cid, month), amount in r.by_month.items()
                        if month == m and cid in expense and amount
                    ),
                    key=lambda c: (-c.spent, c.name),
                ),
            )
            for m, f in r.monthly
        ],
        flows=[
            SpendingFlowOut(
                kind=f.kind,
                side=f.side,
                amount=quantize(f.amount),
                category_id=f.category_id,
                name=names.get(f.category_id) if f.category_id else None,
                over=f.over,
            )
            for f in r.flows
        ],
    )
