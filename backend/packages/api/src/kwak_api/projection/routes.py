"""The wealth projection's assumptions (spec §4.11 F-SIM-1): a household setting any member
can change, kept until changed. The projection page itself is a Dash page (kwak_api.dash)."""

from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from kwak_core.audit import AuditAction
from kwak_core.budget import Month
from kwak_core.money import quantize, require_cents
from kwak_core.projection import (
    DEFAULT_INFLATION,
    STEP,
    Assumption,
    DebtTerms,
    ProjectionError,
    assumption_of,
    check_assumption,
    check_debt_terms,
    check_inflation,
    debt_grows,
    median_growth,
)
from kwak_core.visibility import Visibility
from kwak_core.wealth import WealthKind
from pydantic import AfterValidator, BaseModel, Field

from kwak_api.auth.routes import CurrentSession, Db, Now
from kwak_api.models import Household, User, WealthCategory, WealthLine
from kwak_api.services import audit, projection
from kwak_api.services import wealth as wealth_service

router = APIRouter(prefix="/api/projection", tags=["projection"])

NO_CATEGORY = HTTPException(status.HTTP_404_NOT_FOUND, "no such wealth category")
NO_LINE = HTTPException(status.HTTP_404_NOT_FOUND, "no such wealth line")
RATE = Decimal("0.0001")

# Wide enough for NUMERIC, narrow enough for kwak_core to judge.
Share = Annotated[Decimal, Field(gt=-10, lt=10)]
Amount = Annotated[Decimal, Field(lt=Decimal("1e12")), AfterValidator(require_cents)]


def _unprocessable(error: ProjectionError) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error))


def _step(value: Decimal) -> Decimal:
    return value.quantize(STEP)


class CategoryAssumptionOut(BaseModel):
    id: UUID
    name: str
    colour: str
    preset: str | None
    ret: Decimal
    """The expected annual return, the arithmetic mean, a share."""
    volatility: Decimal
    """The standard deviation of the yearly return, a share."""
    default_ret: Decimal
    default_volatility: Decimal
    median_growth: Decimal
    """The median path's annual growth, below the mean return when there is volatility."""
    own: bool
    """Set by the household rather than the default."""


class DebtOut(BaseModel):
    id: UUID
    name: str
    owner_name: str
    visibility: Visibility
    owed: Decimal | None
    """This month, carried forward; null before its first value."""
    payment: Decimal | None
    """A month, borrower insurance excluded; null: not set, the debt stays as owed."""
    rate: Decimal
    """The annual nominal rate, not the APR, a share."""
    insurance: Decimal
    """The borrower insurance a month: it repays nothing."""
    grows: bool
    """The payment is at or below the month's interest: the debt grows."""


class AssumptionsOut(BaseModel):
    inflation: Decimal
    default_inflation: Decimal
    categories: list[CategoryAssumptionOut]
    """The asset categories, in the matrix's order."""
    debts: list[DebtOut]
    """The open debt lines the viewer sees."""


def _category_out(category: WealthCategory) -> CategoryAssumptionOut:
    a = projection.assumption(category)
    default = assumption_of(category.preset)
    return CategoryAssumptionOut(
        id=category.id,
        name=category.name,
        colour=category.colour,
        preset=category.preset,
        ret=_step(a.ret),
        volatility=_step(a.volatility),
        default_ret=_step(default.ret),
        default_volatility=_step(default.volatility),
        median_growth=_step(median_growth(a)),
        own=category.expected_return is not None,
    )


def _debt_out(line: WealthLine, owed: Decimal | None) -> DebtOut:
    terms = projection.debt_terms(line)
    return DebtOut(
        id=line.id,
        name=line.name,
        owner_name=line.owner.display_name,
        visibility=line.visibility,
        owed=None if owed is None else quantize(owed),
        payment=None if terms.payment is None else quantize(terms.payment),
        rate=terms.rate.quantize(RATE),
        insurance=quantize(terms.insurance),
        grows=owed is not None and debt_grows(owed, terms),
    )


def _assumptions(db: Db, viewer: User, now: Now) -> AssumptionsOut:
    household = db.get_one(Household, viewer.household_id)
    month = Month.of(now.date())
    return AssumptionsOut(
        inflation=_step(projection.inflation(household)),
        default_inflation=_step(DEFAULT_INFLATION),
        categories=[
            _category_out(c)
            for c in wealth_service.categories(db, viewer.household_id)
            if c.kind is WealthKind.ASSET
        ],
        debts=[_debt_out(line, owed) for line, owed in projection.debts(db, viewer, month)],
    )


@router.get("/assumptions")
def get_assumptions(user_session: CurrentSession, db: Db, now: Now) -> AssumptionsOut:
    return _assumptions(db, user_session.user, now)


class InflationIn(BaseModel):
    inflation: Share | None
    """A share, to 0.1 %, from -5 % to 20 %; null for the default."""


@router.put("/inflation")
def set_inflation(
    body: InflationIn, user_session: CurrentSession, db: Db, now: Now
) -> AssumptionsOut:
    if body.inflation is not None:
        try:
            check_inflation(body.inflation)
        except ProjectionError as error:
            raise _unprocessable(error) from None
    household = db.get_one(Household, user_session.user.household_id)
    if body.inflation != household.inflation:
        household.inflation = body.inflation
        audit.record(
            db,
            user_session.user,
            AuditAction.SETTINGS_CHANGED,
            now,
            inflation="" if body.inflation is None else _step(body.inflation),
        )
        db.flush()
    return _assumptions(db, user_session.user, now)


def _asset_category(db: Db, viewer: User, category_id: UUID) -> WealthCategory:
    category = wealth_service.find_category(db, viewer.household_id, category_id)
    if category is None:
        raise NO_CATEGORY
    if category.kind is not WealthKind.ASSET:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "a debt is repaid by line, it has no return"
        )
    return category


class CategoryAssumptionIn(BaseModel):
    ret: Share
    """The expected annual return, a share, to 0.1 %: above -100 %, at most +100 %."""
    volatility: Share
    """A share, to 0.1 %, from 0 to 200 %."""


def _set_category(
    db: Db, viewer: User, now: Now, category: WealthCategory, a: Assumption | None
) -> None:
    category.expected_return = None if a is None else a.ret
    category.volatility = None if a is None else a.volatility
    shown = a or assumption_of(category.preset)
    audit.record(
        db,
        viewer,
        AuditAction.SETTINGS_CHANGED,
        now,
        category=category.name,
        ret=_step(shown.ret),
        volatility=_step(shown.volatility),
    )
    db.flush()


@router.put("/categories/{category_id}")
def set_category_assumption(
    category_id: UUID,
    body: CategoryAssumptionIn,
    user_session: CurrentSession,
    db: Db,
    now: Now,
) -> AssumptionsOut:
    category = _asset_category(db, user_session.user, category_id)
    a = Assumption(body.ret, body.volatility)
    try:
        check_assumption(a)
    except ProjectionError as error:
        raise _unprocessable(error) from None
    _set_category(db, user_session.user, now, category, a)
    return _assumptions(db, user_session.user, now)


@router.delete("/categories/{category_id}")
def restore_category_assumption(
    category_id: UUID, user_session: CurrentSession, db: Db, now: Now
) -> AssumptionsOut:
    """Back to the default of its preset."""
    category = _asset_category(db, user_session.user, category_id)
    _set_category(db, user_session.user, now, category, None)
    return _assumptions(db, user_session.user, now)


class DebtTermsIn(BaseModel):
    payment: Amount | None
    """A month, borrower insurance excluded, in cents; null: not set."""
    rate: Share = Decimal(0)
    """The annual nominal rate (not the APR), a share, to 0.01 %, from 0 to 100 %."""
    insurance: Amount = Decimal(0)
    """The borrower insurance a month, in cents."""


@router.put("/debts/{line_id}")
def set_debt_terms(
    line_id: UUID, body: DebtTermsIn, user_session: CurrentSession, db: Db, now: Now
) -> AssumptionsOut:
    line = wealth_service.find_line(db, user_session.user, line_id)
    if line is None:
        raise NO_LINE
    if line.category.kind is not WealthKind.DEBT:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "not a debt line")
    terms = DebtTerms(body.payment, body.rate, body.insurance)
    try:
        check_debt_terms(terms)
    except ProjectionError as error:
        raise _unprocessable(error) from None
    line.debt_payment, line.debt_rate, line.debt_insurance = (
        terms.payment,
        terms.rate,
        terms.insurance,
    )
    audit.record(
        db,
        user_session.user,
        AuditAction.SETTINGS_CHANGED,
        now,
        private_to=line.owner_id if line.visibility is Visibility.PRIVATE else None,
        debt=line.name,
        payment="" if terms.payment is None else terms.payment,
        rate=terms.rate,
        insurance=terms.insurance,
    )
    db.flush()
    return _assumptions(db, user_session.user, now)
