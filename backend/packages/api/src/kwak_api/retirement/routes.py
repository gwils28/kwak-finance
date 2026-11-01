"""Retirement (spec §4.13 F-RET-1, 2): each member enters their own, any member changes the
household's settings; the page's figures come from `run` (F-RET-4)."""

import re
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from kwak_core import retirement as core
from kwak_core.audit import AuditAction
from kwak_core.budget import Month
from kwak_core.goals import months_between
from kwak_core.money import require_cents
from kwak_core.projection import ProjectionError
from pydantic import AfterValidator, BaseModel, Field

from kwak_api.auth.routes import CurrentSession, Db, Now
from kwak_api.models import Household, MemberRetirement, User
from kwak_api.retirement import run as figures
from kwak_api.services import audit
from kwak_api.services import retirement as service

router = APIRouter(prefix="/api/retirement", tags=["retirement"])

MONTH = re.compile(r"[0-9]{4}-(0[1-9]|1[0-2])")
SHARE = Decimal("0.01")
RATE = Decimal("0.001")


def _month(text: str) -> str:
    if not MONTH.fullmatch(text):
        raise ValueError("expected a month as YYYY-MM")
    return text


MonthText = Annotated[str, AfterValidator(_month)]
Amount = Annotated[Decimal, Field(ge=0, lt=Decimal("1e12")), AfterValidator(require_cents)]


def _parse(text: str) -> Month:
    month = Month.parse(text)
    if month is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "expected a month as YYYY-MM")
    return month


class RetirementMemberOut(BaseModel):
    user_id: UUID
    display_name: str
    me: bool
    birth: str | None
    """YYYY-MM; null until the member enters their retirement."""
    retirement: str | None
    """YYYY-MM: when the member stops working."""
    earnings: Decimal | None
    """The net monthly earnings that stop then, today's euros."""
    pension_month: str | None
    pension: Decimal | None
    """The net monthly pension as it would reach the account, today's euros."""
    age_at_retirement: int | None
    age_at_pension: int | None

    @classmethod
    def of(cls, user: User, row: MemberRetirement | None, viewer: User) -> "RetirementMemberOut":
        member = service.as_member(row) if row is not None else None
        birth = member.birth if member is not None else None
        return cls(
            user_id=user.id,
            display_name=user.display_name,
            me=user.id == viewer.id,
            birth=str(birth) if birth else None,
            retirement=str(member.retirement) if member else None,
            earnings=member.earnings if member else None,
            pension_month=str(member.pension_month) if member else None,
            pension=member.pension if member else None,
            age_at_retirement=core.age(birth, member.retirement) if member and birth else None,
            age_at_pension=core.age(birth, member.pension_month) if member and birth else None,
        )


class RetirementSettingsOut(BaseModel):
    spending_share: Decimal | None
    """The share of today's spending outside the loans; null when an amount is set."""
    spending_amount: Decimal | None
    """A monthly amount set by hand, today's euros."""
    indexation: Decimal
    """The pensions' yearly indexation against inflation, a share."""
    horizon_age: int
    """The youngest member's age at which the plan ends."""
    default_spending_share: Decimal
    default_indexation: Decimal
    default_horizon_age: int


class RetirementSpendingOut(BaseModel):
    average: Decimal
    """Today's average monthly spending, expenses only."""
    debt_payments: Decimal
    """The running loans' payments and insurance, left out of the retirement spending."""
    base: Decimal
    months: int
    """The complete months the average is measured on."""
    retirement_spending: Decimal


class RetirementOut(BaseModel):
    members: list[RetirementMemberOut]
    settings: RetirementSettingsOut
    spending: RetirementSpendingOut


def _out(db: Db, viewer: User, now: Now) -> RetirementOut:
    household = db.get_one(Household, viewer.household_id)
    chosen = service.settings(household)
    spent = service.spending(db, viewer, Month.of(now.date()), chosen)
    return RetirementOut(
        members=[
            RetirementMemberOut.of(u, r, viewer)
            for u, r in service.members(db, viewer.household_id)
        ],
        settings=RetirementSettingsOut(
            spending_share=None if chosen.share is None else chosen.share.quantize(SHARE),
            spending_amount=chosen.amount,
            indexation=chosen.indexation.quantize(RATE),
            horizon_age=chosen.horizon_age,
            default_spending_share=core.DEFAULT_SPENDING_SHARE.quantize(SHARE),
            default_indexation=core.DEFAULT_INDEXATION.quantize(RATE),
            default_horizon_age=core.DEFAULT_HORIZON_AGE,
        ),
        spending=RetirementSpendingOut(
            average=spent.average,
            debt_payments=spent.debt_payments,
            base=spent.base,
            months=spent.months,
            retirement_spending=spent.retirement,
        ),
    )


@router.get("")
def get_retirement(user_session: CurrentSession, db: Db, now: Now) -> RetirementOut:
    return _out(db, user_session.user, now)


class MyRetirementIn(BaseModel):
    birth: MonthText
    retirement: MonthText
    """When you stop working."""
    earnings: Amount = Decimal(0)
    """Your net monthly earnings that stop then, as they reach the account."""
    pension_month: MonthText | None = None
    """When your pension starts; null: with the retirement."""
    pension: Amount = Decimal(0)
    """Your net monthly pension as it would reach the account, after withholding."""


@router.put("/me")
def set_my_retirement(
    body: MyRetirementIn, user_session: CurrentSession, db: Db, now: Now
) -> RetirementOut:
    retirement = _parse(body.retirement)
    birth = _parse(body.birth)
    pension_month = _parse(body.pension_month) if body.pension_month else retirement
    if months_between(birth, retirement) > (core.MAX_HORIZON_AGE * 12):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "one retires before 105 years old"
        )
    member = core.Member(
        user_session.user.id, birth, retirement, body.earnings, pension_month, body.pension
    )
    try:
        service.set_mine(db, user_session.user, member)
    except ProjectionError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from None
    return _out(db, user_session.user, now)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_my_retirement(user_session: CurrentSession, db: Db) -> None:
    service.delete_mine(db, user_session.user)


class RetirementSettingsPatch(BaseModel):
    """Only the fields present change; null brings a setting back to its default."""

    spending_share: Annotated[Decimal, Field(ge=0, lt=10)] | None = None
    """A share of today's spending outside the loans, whole percents from 0.50 to 1.50."""
    spending_amount: Amount | None = None
    """A monthly amount instead of the share."""
    indexation: Annotated[Decimal, Field(gt=-1, lt=1)] | None = None
    """Against inflation, a share to 0.1 %, from -0.02 to 0.01."""
    horizon_age: Annotated[int, Field(ge=0, le=200)] | None = None
    """From 85 to 105."""


@router.patch("/settings")
def update_retirement_settings(
    body: RetirementSettingsPatch, user_session: CurrentSession, db: Db, now: Now
) -> RetirementOut:
    household = db.get_one(Household, user_session.user.household_id)
    given = body.model_fields_set
    try:
        if body.spending_share is not None:
            core.check_spending_share(body.spending_share)
        if body.indexation is not None:
            core.check_indexation(body.indexation)
        if body.horizon_age is not None:
            core.check_horizon_age(body.horizon_age)
    except ProjectionError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from None

    user, action = user_session.user, AuditAction.SETTINGS_CHANGED
    if "spending_share" in given:
        household.retirement_share = body.spending_share
        household.retirement_spending = None
        audit.record(db, user, action, now, spending_share=str(body.spending_share or ""))
    if "spending_amount" in given:
        household.retirement_spending = body.spending_amount
        if body.spending_amount is not None:
            household.retirement_share = None
        audit.record(db, user, action, now, spending_amount=str(body.spending_amount or ""))
    if "indexation" in given:
        household.pension_indexation = body.indexation
        audit.record(db, user, action, now, indexation=str(body.indexation or ""))
    if "horizon_age" in given:
        household.horizon_age = body.horizon_age
        audit.record(db, user, action, now, horizon_age=str(body.horizon_age or ""))
    db.flush()
    return _out(db, user_session.user, now)


@router.get("/run")
def run_retirement(user_session: CurrentSession, db: Db, now: Now) -> figures.RetirementRunOut:
    """The household's plan, run on the Monte Carlo engine: nothing is saved."""
    try:
        plan = service.plan(db, user_session.user, now.date())
    except service.PlanError as reason:
        return figures.RetirementRunOut(problem=str(reason), plan=None)
    return figures.RetirementRunOut(problem=None, plan=figures.plan_out(plan, service.run(plan)))
