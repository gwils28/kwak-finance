"""The wealth projection's assumptions (spec §4.11 F-SIM-1, 3): a household setting any member
can change, kept until changed; and the simulator's runs (F-SIM-5), in `run`."""

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
    Contribution,
    DebtTerms,
    ProjectionError,
    SavingsSource,
    assumption_of,
    check_assumption,
    check_contributions,
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
from kwak_api.projection import run as simulator
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
    contribution: Decimal | None
    """What the household invests in it each month (F-SIM-3); null for none."""
    contribution_indexed: bool
    """The contribution follows the inflation; else a fixed amount."""


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
    savings_source: SavingsSource | None
    """Where the simulator's savings come from, as saved; null: declared once a contribution
    exists, else measured (F-SIM-3)."""


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
        contribution=category.monthly_contribution,
        contribution_indexed=category.contribution_indexed,
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
        savings_source=(
            None
            if household.projection_savings is None
            else SavingsSource(household.projection_savings)
        ),
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


# F-SIM-3: the monthly contributions


class ContributionIn(BaseModel):
    category_id: UUID
    amount: Amount
    """A month, in cents, from €1 to €100,000."""
    indexed: bool = True
    """Follows the inflation; else a fixed amount in current euros."""
    ret: Share | None = None
    """The category's expected return changed with it (its volatility kept); null: unchanged."""


class ContributionsIn(BaseModel):
    contributions: list[ContributionIn] = Field(max_length=50)
    """The whole list: it replaces the saved one."""
    savings_source: SavingsSource | None = None
    """Where the savings come from; left out, the saved choice is kept; null: the default."""


@router.put("/contributions")
def set_contributions(
    body: ContributionsIn, user_session: CurrentSession, db: Db, now: Now
) -> AssumptionsOut:
    viewer = user_session.user
    chosen = [(_asset_category(db, viewer, c.category_id), c) for c in body.contributions]
    try:
        check_contributions(
            [Contribution(c.category_id, c.amount, c.indexed) for c in body.contributions]
        )
        for category, c in chosen:
            if c.ret is not None:
                check_assumption(Assumption(c.ret, projection.assumption(category).volatility))
    except ProjectionError as error:
        raise _unprocessable(error) from None
    wanted = {category.id: c for category, c in chosen}
    for category in wealth_service.categories(db, viewer.household_id):
        item = wanted.get(category.id)
        category.monthly_contribution = None if item is None else item.amount
        category.contribution_indexed = True if item is None else item.indexed
        if item is not None and item.ret is not None:
            kept = projection.assumption(category).volatility
            category.expected_return, category.volatility = item.ret, kept
    source_given = "savings_source" in body.model_fields_set
    if source_given:
        household = db.get_one(Household, viewer.household_id)
        household.projection_savings = (
            None if body.savings_source is None else body.savings_source.value
        )
        audit.record(
            db,
            viewer,
            AuditAction.SETTINGS_CHANGED,
            now,
            savings_source=body.savings_source or "",
        )
    audit.record(
        db,
        viewer,
        AuditAction.SETTINGS_CHANGED,
        now,
        contributions=", ".join(
            f"{category.name} {c.amount}"
            + ("" if c.indexed else " fixed")
            + ("" if c.ret is None else f" at {_step(c.ret)}")
            for category, c in chosen
        ),
    )
    db.flush()
    return _assumptions(db, viewer, now)


# F-SIM-5: the simulator


@router.post("/run")
def run_projection(
    body: simulator.RunIn, user_session: CurrentSession, db: Db, now: Now
) -> simulator.RunOut:
    """The settings being typed, run through the engine: nothing is saved."""
    viewer = user_session.user
    b = projection.basis(db, viewer, body.scope, now.date(), contributions=True)
    if b is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no wealth line in this scope")
    try:
        return simulator.run(db, viewer, b, body)
    except (simulator.RunError, ProjectionError) as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from None
