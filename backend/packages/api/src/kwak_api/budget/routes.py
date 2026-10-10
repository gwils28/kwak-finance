from datetime import date
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from kwak_core.budget import BudgetStatus, Cell, Month, Row, month_range
from kwak_core.money import require_cents
from kwak_core.plans import ComparisonRow, CumulativePoint, Period, PeriodKind, Review, ReviewRow
from pydantic import AfterValidator, BaseModel, Field

from kwak_api.auth.routes import CurrentSession, Db, Now
from kwak_api.models import BudgetPlan, Category
from kwak_api.services import budget as service
from kwak_api.services import categories as category_service
from kwak_api.services import plan_review

router = APIRouter(prefix="/api/budget", tags=["budget"])

Cents = Annotated[Decimal, AfterValidator(require_cents)]
MONTH_PATTERN = r"^\d{4}-\d{2}$"
MAX_MONTHS = 36


def _month(text: str) -> Month:
    try:
        return Month.parse(text)
    except ValueError:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, f"invalid month {text!r}, expected YYYY-MM"
        ) from None


class CellOut(BaseModel):
    month: str
    spent: Decimal
    """Outflows minus refunds (outflows only for "to categorise")."""
    target: Decimal | None
    gap: Decimal | None
    """spent - target."""
    gap_ratio: Decimal | None
    """gap / target, rounded to 4 decimals: 0.0667 = 6.67 % over."""
    status: BudgetStatus

    @classmethod
    def of(cls, cell: Cell) -> "CellOut":
        return cls(
            month=str(cell.month),
            spent=cell.spent.quantize(Decimal("0.01")),
            target=cell.target,
            gap=None if cell.gap is None else cell.gap.quantize(Decimal("0.01")),
            gap_ratio=None
            if cell.gap_ratio is None
            else cell.gap_ratio.quantize(Decimal("0.0001")),
            status=cell.status,
        )


class RowOut(BaseModel):
    category_id: UUID | None
    name: str
    parent_id: UUID | None
    level: int
    target: Decimal | None
    """Target in force in the last month shown."""
    target_from_children: bool
    """True when `target` is the subcategories' sum rather than a target set on this category."""
    cells: list[CellOut]

    @classmethod
    def of(cls, row: Row) -> "RowOut":
        return cls(
            category_id=row.category_id,
            name=row.name,
            parent_id=row.parent_id,
            level=row.level,
            target=row.target,
            target_from_children=row.target_from_children,
            cells=[CellOut.of(c) for c in row.cells],
        )


class BudgetMatrix(BaseModel):
    months: list[str]
    band: Decimal
    rows: list[RowOut]
    """Expense categories: each parent (with its subcategories' total) then its subcategories."""
    uncategorised: RowOut
    total: RowOut


def _category(db: Db, household_id: UUID, category_id: UUID) -> Category:
    category = category_service.find(db, household_id, category_id)
    if category is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "category not found")
    return category


def _plan(db: Db, household_id: UUID, plan_id: UUID) -> BudgetPlan:
    plan = service.find_plan(db, household_id, plan_id)
    if plan is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "budget plan not found")
    return plan


class PlanIn(BaseModel):
    period: str
    """"2027" (year), "2027-S1" (semester) or "2027-Q3" (quarter)."""


class PlanTargetIn(BaseModel):
    amount: Cents | None
    """Monthly target in euros; null removes the category from the plan."""


class PlanPatch(BaseModel):
    note: Annotated[str, Field(max_length=500)] | None = None
    expected_income: Cents | None = None
    """Expected monthly income; editable as long as the targets are."""


class CloseIn(BaseModel):
    last_month: Annotated[str, Field(pattern=MONTH_PATTERN)]
    """YYYY-MM: the plan's last month; a replacement plan covers the rest of its period."""
    reason: Annotated[str, Field(max_length=500)] | None = None


class PlanTargetOut(BaseModel):
    category_id: UUID
    amount: Decimal


class PlanOut(BaseModel):
    id: UUID
    period: str
    kind: PeriodKind
    start: str
    """YYYY-MM, first month."""
    end: str
    """YYYY-MM, last month."""
    targets: list[PlanTargetOut]
    """Monthly targets."""
    expected_income: Decimal | None
    note: str | None
    closed_early: bool
    close_reason: str | None
    editable: bool
    """Targets and expected income can change until the end of the first month."""

    @classmethod
    def of(cls, plan: BudgetPlan, today: date) -> "PlanOut":
        period = Period(PeriodKind(plan.kind), plan.year, plan.number)
        return cls(
            id=plan.id,
            period=str(period),
            kind=period.kind,
            start=str(Month.of(plan.start_month)),
            end=str(Month.of(plan.end_month)),
            targets=[
                PlanTargetOut(category_id=t.category_id, amount=t.amount)
                for t in sorted(plan.targets, key=lambda t: str(t.category_id))
            ],
            expected_income=plan.expected_income,
            note=plan.note,
            closed_early=Month.of(plan.end_month) < period.end,
            close_reason=plan.close_reason,
            editable=service.is_editable(plan, today),
        )


@router.get("/plans")
def list_plans(user_session: CurrentSession, db: Db, now: Now) -> list[PlanOut]:
    """Every budget plan, in calendar order (F-BUD-7)."""
    plans = service.list_plans(db, user_session.user.household_id)
    return [PlanOut.of(p, now.date()) for p in plans]


@router.post("/plans", status_code=status.HTTP_201_CREATED)
def create_plan(body: PlanIn, user_session: CurrentSession, db: Db, now: Now) -> PlanOut:
    """A plan over a calendar period, pre-filled with the latest plan's targets."""
    try:
        period = Period.parse(body.period)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None
    try:
        plan = service.create_plan(db, user_session.user.household_id, period)
    except service.PlanConflictError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from None
    return PlanOut.of(plan, now.date())


@router.put("/plans/{plan_id}/targets/{category_id}")
def set_plan_target(
    plan_id: UUID,
    category_id: UUID,
    body: PlanTargetIn,
    user_session: CurrentSession,
    db: Db,
    now: Now,
) -> PlanOut:
    household_id = user_session.user.household_id
    plan = _plan(db, household_id, plan_id)
    category = _category(db, household_id, category_id)
    try:
        service.set_plan_target(db, plan, category, body.amount, now.date())
    except service.PlanConflictError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from None
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None
    return PlanOut.of(plan, now.date())


@router.patch("/plans/{plan_id}")
def update_plan(
    plan_id: UUID, body: PlanPatch, user_session: CurrentSession, db: Db, now: Now
) -> PlanOut:
    plan = _plan(db, user_session.user.household_id, plan_id)
    try:
        service.update_plan(db, plan, now.date(), **body.model_dump(exclude_unset=True))
    except service.PlanConflictError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from None
    return PlanOut.of(plan, now.date())


@router.post("/plans/{plan_id}/close")
def close_plan(
    plan_id: UUID, body: CloseIn, user_session: CurrentSession, db: Db, now: Now
) -> PlanOut:
    """Close the plan early after `last_month`; returns the replacement plan for the rest."""
    plan = _plan(db, user_session.user.household_id, plan_id)
    try:
        rest = service.close_plan(db, plan, _month(body.last_month), body.reason)
    except service.PlanConflictError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from None
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None
    return PlanOut.of(rest, now.date())


@router.delete("/plans/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_plan(plan_id: UUID, user_session: CurrentSession, db: Db, now: Now) -> None:
    """Only while the plan is editable: afterwards, close it early instead."""
    plan = _plan(db, user_session.user.household_id, plan_id)
    try:
        service.delete_plan(db, plan, now.date())
    except service.PlanConflictError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from None


CENTS = Decimal("0.01")
RATIO = Decimal("0.0001")


def _cents(value: Decimal | None) -> Decimal | None:
    return None if value is None else value.quantize(CENTS)


def _ratio(value: Decimal | None) -> Decimal | None:
    return None if value is None else value.quantize(RATIO)


Band = Annotated[Decimal, Query(ge=0, le=Decimal("0.5"))]


class ReviewRowOut(BaseModel):
    category_id: UUID | None
    name: str
    parent_id: UUID | None
    level: int
    monthly_target: Decimal | None
    envelope: Decimal | None
    """Monthly target x the plan's months."""
    spent: Decimal
    gap: Decimal | None
    """spent - envelope."""
    gap_ratio: Decimal | None
    """gap / envelope, rounded to 4 decimals."""
    pace: Decimal | None
    """The envelope prorated to the time elapsed; the envelope once the plan is over."""
    status: BudgetStatus
    """The projection compared with the envelope, with the band: the spending once over."""
    projection: Decimal | None
    """Spending projected at the end of the plan: completed months as spent, the others at the
    larger of their spending and the expected one (the target, or the completed months' average
    if higher)."""
    drift: Decimal | None
    """projection - envelope."""
    projected_gap_ratio: Decimal | None
    """drift / envelope, rounded to 4 decimals: the gap the status is judged on."""
    drifting: bool
    """Projected above the envelope while the plan runs."""
    months_over: int
    months_on: int
    months_under: int
    """Completed months over / on / under the monthly target."""
    target_from_children: bool

    @classmethod
    def of(cls, row: ReviewRow) -> "ReviewRowOut":
        return cls(
            category_id=row.category_id,
            name=row.name,
            parent_id=row.parent_id,
            level=row.level,
            monthly_target=row.monthly_target,
            envelope=_cents(row.envelope),
            spent=row.spent.quantize(CENTS),
            gap=_cents(row.gap),
            gap_ratio=_ratio(row.gap_ratio),
            pace=_cents(row.pace),
            status=row.status,
            projection=_cents(row.projection),
            drift=_cents(row.drift),
            projected_gap_ratio=_ratio(row.projected_gap_ratio),
            drifting=row.drifting,
            months_over=row.months_over,
            months_on=row.months_on,
            months_under=row.months_under,
            target_from_children=row.target_from_children,
        )


class ReviewOut(BaseModel):
    plan: PlanOut
    elapsed: Decimal
    """Share of the plan's time elapsed, 0 to 1, rounded to 4 decimals."""
    finished: bool
    band: Decimal
    rows: list[ReviewRowOut]
    """Expense categories: each parent (with its subcategories' total) then its subcategories."""
    total: ReviewRowOut
    uncategorised: Decimal
    """Outflows left to categorise in the plan's months, counted in the total."""
    provisional: bool
    """Spending left to categorise may still change the result."""
    income: Decimal
    savings: Decimal
    """income - total spent."""
    savings_rate: Decimal | None
    planned_savings: Decimal | None
    """Expected income x months - total envelope, when the plan has an expected income."""
    drifting: list[UUID | None]
    """Drifting categories (ids of `rows`), the largest projected overrun first."""

    @classmethod
    def of(cls, review: Review, plan: BudgetPlan, today: date, band: Decimal) -> "ReviewOut":
        return cls(
            plan=PlanOut.of(plan, today),
            elapsed=review.elapsed.quantize(RATIO),
            finished=review.finished,
            band=band,
            rows=[ReviewRowOut.of(r) for r in review.rows],
            total=ReviewRowOut.of(review.total),
            uncategorised=review.uncategorised.quantize(CENTS),
            provisional=review.provisional,
            income=review.income.quantize(CENTS),
            savings=review.savings.quantize(CENTS),
            savings_rate=_ratio(review.savings_rate),
            planned_savings=_cents(review.planned_savings),
            drifting=[r.category_id for r in review.drifting_rows],
        )


@router.get("/plans/{plan_id}/review")
def review_plan(
    plan_id: UUID,
    user_session: CurrentSession,
    db: Db,
    now: Now,
    scope: service.Scope = service.Scope.HOUSEHOLD,
    band: Band = Decimal("0.05"),
) -> ReviewOut:
    """Where the plan stands: during the plan against the pace, after it the final result."""
    plan = _plan(db, user_session.user.household_id, plan_id)
    result = plan_review.review(db, user_session.user, plan, now.date(), scope=scope, band=band)
    return ReviewOut.of(result, plan, now.date(), band)


class CumulativePointOut(BaseModel):
    day: date
    spent: Decimal | None
    """Spending from the plan's first day to this one; null after today."""
    envelope: Decimal
    """The envelope prorated to this day."""

    @classmethod
    def of(cls, point: CumulativePoint) -> "CumulativePointOut":
        return cls(day=point.day, spent=_cents(point.spent), envelope=point.envelope)


class CumulativeOut(BaseModel):
    envelope: Decimal
    """0 when the category (or the plan) has no target."""
    points: list[CumulativePointOut]
    """One per day of the plan."""


@router.get("/plans/{plan_id}/cumulative")
def plan_cumulative(
    plan_id: UUID,
    user_session: CurrentSession,
    db: Db,
    now: Now,
    category_id: Annotated[
        UUID | None, Query(description="An expense category; default: every category")
    ] = None,
    scope: service.Scope = service.Scope.HOUSEHOLD,
) -> CumulativeOut:
    """Cumulative spending day by day against the envelope line (F-DSH-6)."""
    household_id = user_session.user.household_id
    plan = _plan(db, household_id, plan_id)
    category = None if category_id is None else _category(db, household_id, category_id)
    try:
        envelope, points = plan_review.cumulative_chart(
            db, user_session.user, plan, now.date(), category=category, scope=scope
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None
    return CumulativeOut(
        envelope=envelope.quantize(CENTS), points=[CumulativePointOut.of(p) for p in points]
    )


class ComparisonRowOut(BaseModel):
    category_id: UUID | None
    name: str
    parent_id: UUID | None
    level: int
    target_a: Decimal | None
    target_b: Decimal | None
    average_a: Decimal | None
    """Monthly average spent in plan a: its projection's while it runs."""
    average_b: Decimal | None
    change: Decimal | None
    """average_b - average_a."""
    change_ratio: Decimal | None
    """change / average_a, rounded to 4 decimals."""

    @classmethod
    def of(cls, row: ComparisonRow) -> "ComparisonRowOut":
        return cls(
            category_id=row.category_id,
            name=row.name,
            parent_id=row.parent_id,
            level=row.level,
            target_a=row.target_a,
            target_b=row.target_b,
            average_a=_cents(row.average_a),
            average_b=_cents(row.average_b),
            change=_cents(row.change),
            change_ratio=_ratio(row.change_ratio),
        )


class ComparisonOut(BaseModel):
    a: PlanOut
    """The reference plan."""
    b: PlanOut
    rows: list[ComparisonRowOut]
    """Plan b's categories, then the total."""


@router.get("/plans/{plan_id}/comparison")
def plan_comparison(
    plan_id: UUID,
    user_session: CurrentSession,
    db: Db,
    now: Now,
    against: Annotated[
        UUID | None, Query(description="The reference plan; default: the previous plan")
    ] = None,
    scope: service.Scope = service.Scope.HOUSEHOLD,
) -> ComparisonOut:
    """Two plans side by side on monthly figures, so plans of different lengths compare."""
    household_id = user_session.user.household_id
    b = _plan(db, household_id, plan_id)
    a = _plan(db, household_id, against) if against else plan_review.previous_plan(db, b)
    if a is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no earlier budget plan to compare with")
    rows = plan_review.comparison(db, user_session.user, a, b, now.date(), scope=scope)
    return ComparisonOut(
        a=PlanOut.of(a, now.date()),
        b=PlanOut.of(b, now.date()),
        rows=[ComparisonRowOut.of(r) for r in rows],
    )


@router.get("/matrix")
def budget_matrix(
    user_session: CurrentSession,
    db: Db,
    now: Now,
    start: Annotated[
        str | None, Query(description="YYYY-MM; default: 11 months before end")
    ] = None,
    end: Annotated[str | None, Query(description="YYYY-MM; default: this month")] = None,
    scope: service.Scope = service.Scope.HOUSEHOLD,
    band: Band = Decimal("0.05"),
) -> BudgetMatrix:
    """Spending per expense category and month against the targets (F-BUD-6)."""
    last = _month(end) if end else Month.of(now.date())
    first = _month(start) if start else _back(last, 11)
    months = month_range(first, last)
    if not months:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "start is after end")
    if len(months) > MAX_MONTHS:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, f"at most {MAX_MONTHS} months at a time"
        )
    result = service.matrix(db, user_session.user, months, scope=scope, band=band)
    return BudgetMatrix(
        months=[str(m) for m in result.months],
        band=band,
        rows=[RowOut.of(r) for r in result.rows],
        uncategorised=RowOut.of(result.uncategorised),
        total=RowOut.of(result.total),
    )


def _back(month: Month, count: int) -> Month:
    index = month.year * 12 + month.month - 1 - count
    return Month(index // 12, index % 12 + 1)
