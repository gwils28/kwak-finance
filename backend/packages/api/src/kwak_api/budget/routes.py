from datetime import date
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from kwak_core.budget import BudgetStatus, Cell, Month, Row, month_range
from kwak_core.money import require_cents
from kwak_core.plans import Period, PeriodKind
from pydantic import AfterValidator, BaseModel, Field

from kwak_api.auth.routes import CurrentSession, Db, Now
from kwak_api.models import BudgetPlan, Category
from kwak_api.services import budget as service
from kwak_api.services import categories as category_service

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


class TargetIn(BaseModel):
    amount: Cents | None
    """Monthly target in euros; null removes the target."""
    from_month: Annotated[str, Field(pattern=MONTH_PATTERN)]
    """YYYY-MM: the month whose plan gets the target."""


class TargetOut(BaseModel):
    category_id: UUID
    amount: Decimal | None
    valid_from: str
    """YYYY-MM: the first month of the plan holding the target."""


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


@router.put("/targets/{category_id}", deprecated=True)
def set_target(
    category_id: UUID, body: TargetIn, user_session: CurrentSession, db: Db, now: Now
) -> TargetOut:
    """Set the target in the plan covering `from_month` (its quarter's plan if none).

    Kept for the current budget page; use the plan endpoints instead.
    """
    household_id = user_session.user.household_id
    category = _category(db, household_id, category_id)
    month = _month(body.from_month)
    try:
        plan = service.set_target(db, household_id, category, month, body.amount, now.date())
    except service.PlanConflictError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from None
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None
    return TargetOut(
        category_id=category.id, amount=body.amount, valid_from=str(Month.of(plan.start_month))
    )


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
    band: Annotated[Decimal, Query(ge=0, le=Decimal("0.5"))] = Decimal("0.05"),
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
