"""Retirement (spec §4.13): each member's own, the household's settings, the spending it is
measured on, and the plan read from the household, run on the Monte Carlo engine."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from kwak_analytics import montecarlo as mc
from kwak_analytics import retirement as engine
from kwak_core import retirement as core
from kwak_core.budget import Month
from kwak_core.goals import months_between
from kwak_core.money import quantize
from kwak_core.projection import ProjectionError, amortise
from kwak_core.visibility import Scope
from sqlalchemy import select
from sqlalchemy.orm import Session

from kwak_api.models import Household, MemberRetirement, User
from kwak_api.services import goals, projection, spending_budget

ZERO = Decimal(0)


class PlanError(Exception):
    """Why no plan can run: `no_wealth`, `no_member`, `horizon` (it comes before the
    household retires) or `no_allocation`."""


def members(db: Session, household_id: object) -> list[tuple[User, MemberRetirement | None]]:
    """The household's active members, with what each entered."""
    users = list(
        db.scalars(
            select(User)
            .where(User.household_id == household_id, User.is_active)
            .order_by(User.display_name)
        )
    )
    plans = {
        p.user_id: p
        for p in db.scalars(
            select(MemberRetirement).where(MemberRetirement.user_id.in_([u.id for u in users]))
        )
    }
    return [(u, plans.get(u.id)) for u in users]


def as_member(row: MemberRetirement) -> core.Member:
    return core.Member(
        row.user_id,
        Month.of(row.birth),
        Month.of(row.retirement),
        row.earnings,
        Month.of(row.pension_month),
        row.pension,
    )


def set_mine(db: Session, user: User, member: core.Member) -> None:
    """The member's own; raises ProjectionError when it cannot be."""
    core.check_member(member)
    if member.birth is None:
        raise ProjectionError("a retirement needs a birth month")
    row = db.scalar(select(MemberRetirement).where(MemberRetirement.user_id == user.id))
    if row is None:
        row = MemberRetirement(user_id=user.id)
        db.add(row)
    row.birth = member.birth.first_day()
    row.retirement = member.retirement.first_day()
    row.earnings = member.earnings
    row.pension_month = member.pension_month.first_day()
    row.pension = member.pension
    db.flush()


def delete_mine(db: Session, user: User) -> None:
    row = db.scalar(select(MemberRetirement).where(MemberRetirement.user_id == user.id))
    if row is not None:
        db.delete(row)
        db.flush()


@dataclass(frozen=True)
class Settings:
    """The ones in use: the household's, else the defaults."""

    share: Decimal | None
    """None when an amount is set."""
    amount: Decimal | None
    indexation: Decimal
    horizon_age: int


def settings(household: Household) -> Settings:
    amount = household.retirement_spending
    return Settings(
        share=None
        if amount is not None
        else (household.retirement_share or core.DEFAULT_SPENDING_SHARE),
        amount=amount,
        indexation=(
            core.DEFAULT_INDEXATION
            if household.pension_indexation is None
            else household.pension_indexation
        ),
        horizon_age=household.horizon_age or core.DEFAULT_HORIZON_AGE,
    )


@dataclass(frozen=True)
class Spending:
    average: Decimal
    """Today's average monthly spending (expenses only), over the capacity's months."""
    debt_payments: Decimal
    """The running debts' payments and insurance, which the spending lines hold."""
    base: Decimal
    months: int
    retirement: Decimal
    """What the household would spend once retired, today's euros."""


def spending(db: Session, viewer: User, this_month: Month, chosen: Settings) -> Spending:
    household_id = viewer.household_id
    months = goals.capacity_months(db, household_id, this_month)
    figures = list(
        spending_budget.figures_by_month(
            db, household_id, months, spending_budget.kinds(db, household_id)
        ).values()
    )
    average = (
        quantize(abs(sum((f.spent for f in figures), ZERO)) / len(figures))
        if figures
        else quantize(ZERO)
    )
    payments = sum(
        (
            (line.debt_payment or ZERO) + line.debt_insurance
            for line, owed in projection.debts(db, viewer, this_month)
            if line.debt_payment is not None and owed
        ),
        ZERO,
    )
    base = core.spending_base(average, payments)
    return Spending(
        average,
        quantize(payments),
        quantize(base),
        len(figures),
        quantize(core.retirement_spending(base, share=chosen.share, amount=chosen.amount)),
    )


@dataclass(frozen=True)
class Plan:
    basis: projection.Basis
    members: list[tuple[str, core.Member]]
    """The counted ones, by name."""
    left_out: list[str]
    """Members without a birth month."""
    settings: Settings
    spending: Spending
    this_month: Month
    retired: Month
    """The household's retirement: its last member's."""
    horizon: Month
    retired_at: int
    """The household's retirement counted from now, 1 when already retired."""
    scenario: mc.Scenario


def plan(db: Session, viewer: User, today: date) -> Plan:
    """The household's plan of F-RET-3, the wealth lines the viewer sees."""
    this_month = Month.of(today)
    b = projection.basis(db, viewer, Scope.HOUSEHOLD, today)
    if b is None:
        raise PlanError("no_wealth")
    rows = members(db, viewer.household_id)
    counted = [(u.display_name, as_member(r)) for u, r in rows if r is not None]
    left_out = [u.display_name for u, r in rows if r is None]
    if not counted:
        raise PlanError("no_member")
    chosen = settings(db.get_one(Household, viewer.household_id))
    spent = spending(db, viewer, this_month, chosen)
    people = [m for _, m in counted]
    retired = core.household_retirement(people)
    if retired is None:
        raise PlanError("no_member")
    end = core.horizon(people, chosen.horizon_age, this_month)
    months = months_between(this_month, end)
    retired_at = max(1, months_between(this_month, retired))
    if retired_at > months:
        raise PlanError("horizon")
    debts = [core.Debt(owed, b.debts[k]) for k, owed in b.start.debts.items()]
    owed = [ZERO] * months
    for d in debts:
        owed = [
            a + o for a, o in zip(owed, amortise(d.owed, d.terms, months=months).owed, strict=True)
        ]
    allocation = b.allocation
    if allocation is None:
        raise PlanError("no_allocation")
    scenario = mc.Scenario(
        categories=[
            mc.Category(
                c.id,
                c.preset,
                b.start.assets.get(c.id, ZERO),
                b.assumptions[c.id],
                allocation.get(c.id, ZERO),
            )
            for c in b.categories
        ],
        savings=core.plan_savings(
            people,
            capacity=b.savings,
            spending=spent.retirement,
            debts=debts,
            inflation=b.inflation,
            indexation=chosen.indexation,
            this_month=this_month,
            months=months,
        ),
        debts=owed,
        start_debts=sum(b.start.debts.values(), ZERO),
        inflation=b.inflation,
    )
    return Plan(b, counted, left_out, chosen, spent, this_month, retired, end, retired_at, scenario)


@dataclass(frozen=True)
class Result:
    outcome: mc.Outcome
    withdrawal: engine.Withdrawal


def run(p: Plan, *, paths: int = mc.PATHS, seed: int = mc.DEFAULT_SEED) -> Result:
    """The plan's outcomes, and what its wealth alone pays from the retirement (F-RET-4)."""
    return Result(
        mc.simulate(p.scenario, paths=paths, seed=seed),
        engine.sustainable_withdrawal(p.scenario, retired_at=p.retired_at, paths=paths, seed=seed),
    )
