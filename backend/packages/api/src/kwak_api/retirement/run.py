"""The Retirement page's figures (spec §4.13 F-RET-4): the standard of living at the household's
retirement, how long the wealth lasts, the fan of net worth to the horizon, the income once
retired, and the inputs they come from. Words are the page's: here only numbers and months, in
today's euros."""

from collections.abc import Sequence
from decimal import Decimal
from typing import Literal

from kwak_analytics import montecarlo as mc
from kwak_core import retirement as core
from kwak_core.budget import Month
from kwak_core.goals import add_months, months_between
from kwak_core.money import quantize
from pydantic import BaseModel

from kwak_api.services import retirement as service

ONE = Decimal(1)
ZERO = Decimal(0)
TENTH = Decimal("0.1")
HALF = Decimal("0.5")
SHARE = Decimal("0.0001")

type Problem = Literal["no_wealth", "no_member", "horizon", "no_allocation"]


def _real(amount: Decimal, rate: Decimal, inflation: Decimal, t: int) -> Decimal:
    """An amount of today's euros growing by `rate` a year, in today's euros at month t."""
    return amount * ((ONE + rate) / (ONE + inflation)) ** (Decimal(t) / 12)


def pensions_at(p: service.Plan, t: int) -> Decimal:
    """The pensions received in month t, in today's euros."""
    month = add_months(p.this_month, t)
    rate = p.basis.inflation + p.settings.indexation
    return sum(
        (
            _real(m.pension, rate, p.basis.inflation, t)
            for _, m in p.members
            if m.pension_month <= month
        ),
        ZERO,
    )


def spending_at(p: service.Plan, t: int, costs: Sequence[Decimal]) -> Decimal:
    """The retirement spending in month t, the loans still running included, today's euros."""
    return p.spending.retirement + costs[t - 1] / (ONE + p.basis.inflation) ** (Decimal(t) / 12)


class RetirementLivingOut(BaseModel):
    """At the household's retirement, once every pension has started."""

    pensions: Decimal
    withdrawal: Decimal | None
    """What the liquid wealth can pay a month in nine outcomes in ten, indexed; null when it has
    already run out by then in more than one in ten."""
    withdrawal_half: Decimal | None
    """The same in half of the outcomes."""
    spending: Decimal
    later_pension: bool
    """A pension starts after the household's retirement: the years before it are left to the
    wealth, which the chance counts and the withdrawal does not."""


class RetirementLastsOut(BaseModel):
    chance: Decimal
    """That the liquid wealth does not run out before the horizon."""
    ten_age: int | None
    """The youngest member's age by which it runs out in one outcome in ten; null: not before
    the horizon."""
    half_age: int | None
    shortfall: bool
    """It runs out in some outcomes."""


class RetirementFanMonthOut(BaseModel):
    month: str
    p10: Decimal
    p25: Decimal
    p50: Decimal
    p75: Decimal
    p90: Decimal
    liquid: Decimal
    """The liquid holdings' median, which pay the withdrawal."""


class RetirementIncomeMonthOut(BaseModel):
    month: str
    pensions: Decimal
    withdrawal: Decimal
    spending: Decimal
    """The retirement spending, the loans still running included."""


class RetirementPersonOut(BaseModel):
    name: str
    birth: str
    retirement: str
    age_at_retirement: int
    earnings: Decimal
    pension_month: str
    age_at_pension: int
    pension: Decimal


class RetirementPlanSpendingOut(BaseModel):
    retirement: Decimal
    share: Decimal | None
    """Of today's spending outside the loans; null when the amount is set by hand."""
    base: Decimal
    months: int


class RetirementEngineOut(BaseModel):
    paths: int
    seed: int
    version: int


class RetirementPlanOut(BaseModel):
    this_month: str
    retired: str
    """The household's retirement: its last member's."""
    horizon: str
    horizon_age: int
    youngest: str
    youngest_age_at_horizon: int
    living: RetirementLivingOut
    lasts: RetirementLastsOut
    months: list[RetirementFanMonthOut]
    """From this month to the horizon."""
    income: list[RetirementIncomeMonthOut]
    """From the household's retirement to the horizon."""
    people: list[RetirementPersonOut]
    """The members counted, by name."""
    left_out: list[str]
    """Members without a retirement entered."""
    spending: RetirementPlanSpendingOut
    indexation: Decimal
    engine: RetirementEngineOut


class RetirementRunOut(BaseModel):
    problem: Problem | None
    """Why no plan can run: no wealth line, no member's retirement, a horizon before the
    retirement, no category to save into."""
    plan: RetirementPlanOut | None


def _share(value: Decimal) -> Decimal:
    return value.quantize(SHARE)


def _youngest(p: service.Plan) -> tuple[str, Month]:
    name, member = max(p.members, key=lambda nm: nm[1].birth or p.this_month)
    assert member.birth is not None  # noqa: S101 - counted members have one
    return name, member.birth


def plan_out(p: service.Plan, result: service.Result) -> RetirementPlanOut:
    outcome = result.outcome
    w = result.withdrawal
    at = p.retired_at
    last = max(m.pension_month for _, m in p.members)
    full = max(at, months_between(p.this_month, last))
    living = RetirementLivingOut(
        pensions=quantize(pensions_at(p, full)),
        withdrawal=None if w.nine_tenths is None else quantize(w.nine_tenths),
        withdrawal_half=(None if w.nine_tenths is None else quantize(w.half or w.nine_tenths)),
        spending=quantize(p.spending.retirement),
        later_pension=last > p.retired,
    )

    youngest_name, youngest = _youngest(p)

    def age_by(share: Decimal) -> int | None:
        k = outcome.ran_out_by(share)
        return None if k is None else core.age(youngest, add_months(p.this_month, k))

    shortfall = outcome.shortfall_share()
    lasts = RetirementLastsOut(
        chance=_share(ONE - shortfall),
        ten_age=age_by(TENTH),
        half_age=age_by(HALF),
        shortfall=shortfall > 0,
    )

    percentiles = outcome.percentiles(today=True)
    liquid = outcome.liquid_medians(today=True)
    months = [
        RetirementFanMonthOut(
            month=str(add_months(p.this_month, t)),
            p10=q[10],
            p25=q[25],
            p50=q[50],
            p75=q[75],
            p90=q[90],
            liquid=quantize(liquid[t]),
        )
        for t, q in enumerate(percentiles)
    ]

    n = len(p.scenario.savings)
    costs = core.debt_costs(
        [core.Debt(owed, p.basis.debts[k]) for k, owed in p.basis.start.debts.items()], n
    )
    paid = quantize(w.nine_tenths or ZERO)
    income = [
        RetirementIncomeMonthOut(
            month=str(add_months(p.this_month, t)),
            pensions=quantize(pensions_at(p, t)),
            withdrawal=paid,
            spending=quantize(spending_at(p, t, costs)),
        )
        for t in range(at, n + 1)
    ]

    people = []
    for name, m in p.members:
        assert m.birth is not None  # noqa: S101 - counted members have one
        people.append(
            RetirementPersonOut(
                name=name,
                birth=str(m.birth),
                retirement=str(m.retirement),
                age_at_retirement=core.age(m.birth, m.retirement),
                earnings=quantize(m.earnings),
                pension_month=str(m.pension_month),
                age_at_pension=core.age(m.birth, m.pension_month),
                pension=quantize(m.pension),
            )
        )
    s = p.spending
    return RetirementPlanOut(
        this_month=str(p.this_month),
        retired=str(p.retired),
        horizon=str(p.horizon),
        horizon_age=p.settings.horizon_age,
        youngest=youngest_name,
        youngest_age_at_horizon=core.age(youngest, p.horizon),
        living=living,
        lasts=lasts,
        months=months,
        income=income,
        people=people,
        left_out=p.left_out,
        spending=RetirementPlanSpendingOut(
            retirement=quantize(s.retirement),
            share=None if p.settings.share is None else p.settings.share.quantize(Decimal("0.01")),
            base=quantize(s.base),
            months=s.months,
        ),
        indexation=p.settings.indexation.quantize(Decimal("0.001")),
        engine=RetirementEngineOut(
            paths=int(outcome.net.shape[1]), seed=outcome.seed, version=mc.ENGINE_VERSION
        ),
    )
