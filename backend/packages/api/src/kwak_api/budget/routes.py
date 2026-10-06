from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from kwak_core.budget import BudgetStatus, Cell, Month, Row, month_range
from kwak_core.money import require_cents
from pydantic import AfterValidator, BaseModel, Field

from kwak_api.auth.routes import CurrentSession, Db, Now
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
    """YYYY-MM: the first month the target applies to. Earlier months keep their target."""


class TargetOut(BaseModel):
    category_id: UUID
    amount: Decimal | None
    valid_from: str
    """YYYY-MM."""


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
    cells: list[CellOut]

    @classmethod
    def of(cls, row: Row) -> "RowOut":
        return cls(
            category_id=row.category_id,
            name=row.name,
            parent_id=row.parent_id,
            level=row.level,
            target=row.target,
            cells=[CellOut.of(c) for c in row.cells],
        )


class BudgetMatrix(BaseModel):
    months: list[str]
    band: Decimal
    rows: list[RowOut]
    """Expense categories: each parent (with its subcategories' total) then its subcategories."""
    uncategorised: RowOut
    total: RowOut


@router.put("/targets/{category_id}")
def set_target(
    category_id: UUID, body: TargetIn, user_session: CurrentSession, db: Db
) -> TargetOut:
    household_id = user_session.user.household_id
    category = category_service.find(db, household_id, category_id)
    if category is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "category not found")
    month = _month(body.from_month)
    try:
        target = service.set_target(db, household_id, category, month, body.amount)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None
    return TargetOut(category_id=category.id, amount=target.amount, valid_from=str(month))


@router.get("/targets")
def list_targets(
    user_session: CurrentSession,
    db: Db,
    now: Now,
    month: Annotated[
        str | None, Query(pattern=MONTH_PATTERN, description="Default: this month")
    ] = None,
) -> list[TargetOut]:
    """Targets in force in `month`, with the month each one started."""
    when = _month(month) if month else Month.of(now.date())
    return [
        TargetOut(category_id=cid, amount=amount, valid_from=str(since))
        for cid, amount, since in service.current_targets(db, user_session.user.household_id, when)
    ]


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
