"""The wealth projection (spec §4.11): its assumptions, saved per household (F-SIM-1: each asset
category's return and volatility, the inflation, each debt line's repayment), what a scope's
projection starts from (F-SIM-2, 3) and its runs (F-SIM-4), by `kwak_analytics.montecarlo`."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from uuid import UUID

from kwak_analytics import montecarlo as mc
from kwak_core import goal_analysis as ga
from kwak_core import projection as core
from kwak_core.budget import Month
from kwak_core.goals import EFFORT_MONTHS
from kwak_core.money import quantize
from kwak_core.projection import DEFAULT_INFLATION, Assumption, DebtTerms, assumption_of
from kwak_core.visibility import Scope
from kwak_core.wealth import CategoryInput, WealthKind, line_cell
from sqlalchemy.orm import Session

from kwak_api.models import Household, User, WealthCategory, WealthLine
from kwak_api.services import goals, wealth

MIN_YEARS = 1
MAX_YEARS = 40
DEFAULT_YEARS = 20


def assumption(category: WealthCategory) -> Assumption:
    """The household's own, else the default of its preset (0 % ± 0 for one added later)."""
    if category.expected_return is None or category.volatility is None:
        return assumption_of(category.preset)
    return Assumption(category.expected_return, category.volatility)


def risk(category: WealthCategory) -> ga.LineRisk:
    """How the goals analysis judges a line of this category (F-ANA-1)."""
    own = category.expected_return is not None
    return ga.risk_of(category.preset, assumption(category) if own else None)


def inflation(household: Household) -> Decimal:
    return DEFAULT_INFLATION if household.inflation is None else household.inflation


def debt_terms(line: WealthLine) -> DebtTerms:
    return DebtTerms(line.debt_payment, line.debt_rate, line.debt_insurance)


def debts(db: Session, viewer: User, month: Month) -> list[tuple[WealthLine, Decimal | None]]:
    """The debt lines the viewer sees, open in `month`, with what they owe then (carried
    forward; None before their first value)."""
    lines = [
        line
        for line in wealth.visible_lines(db, viewer)
        if line.category.kind is WealthKind.DEBT
        and (line.closed_from is None or Month.of(line.closed_from) > month)
    ]
    values = goals.line_values(db, {line.id for line in lines})
    out: list[tuple[WealthLine, Decimal | None]] = []
    for line in lines:
        cell = line_cell(values.get(line.id, {}), month)
        out.append((line, cell.amount if cell else None))
    return out


# F-SIM-2 to 4: the runs


@dataclass(frozen=True)
class CategoryInfo:
    id: UUID
    name: str
    colour: str
    preset: str | None


@dataclass(frozen=True)
class Basis:
    """What a projection of a scope starts from, read once per visit."""

    start: core.Start
    categories: list[CategoryInfo]
    """Every asset category of the household, in the matrix's order: a scenario may save into
    one the scope holds nothing in."""
    assumptions: dict[UUID, Assumption]
    allocation: dict[UUID, Decimal] | None
    """The default one; None when a scenario must set its own."""
    debts: dict[UUID, DebtTerms]
    """Each debt line of the start."""
    savings: Decimal
    """A month, today's euros: the goals' capacity (F-GOAL-6)."""
    savings_set: bool
    """Set by hand rather than measured."""
    savings_months: int
    """The complete months it was measured on."""
    inflation: Decimal


def basis(db: Session, viewer: User, scope: Scope, today: date) -> Basis | None:
    """None without a wealth line in scope: the page asks to enter the wealth first."""
    month = Month.of(today)
    scoped = wealth.scoped_lines(db, viewer, scope)
    if not scoped:
        return None
    rows = wealth.categories(db, viewer.household_id)
    start = core.starting_point(
        [CategoryInput(c.id, c.kind) for c in rows], [i for _, i in scoped], month
    )
    assets = [c for c in rows if c.kind is WealthKind.ASSET]
    try:
        allocation: dict[UUID, Decimal] | None = core.default_allocation(
            start.assets, {c.id: c.preset for c in assets}
        )
    except core.ProjectionError:
        allocation = None
    household = db.get_one(Household, viewer.household_id)
    savings_set = household.goal_capacity is not None
    return Basis(
        start=start,
        categories=[CategoryInfo(c.id, c.name, c.colour, c.preset) for c in assets],
        assumptions={c.id: assumption(c) for c in assets},
        allocation=allocation,
        debts={line.id: debt_terms(line) for line, _ in scoped if line.id in start.debts},
        savings=(
            household.goal_capacity
            if household.goal_capacity is not None
            else goals.capacity(db, viewer, month)
        ),
        savings_set=savings_set,
        savings_months=(
            EFFORT_MONTHS
            if savings_set
            else len(goals.capacity_months(db, viewer.household_id, month))
        ),
        inflation=inflation(household),
    )


@dataclass(frozen=True)
class WhatIf:
    """What a scenario changes from the saved assumptions, for this visit only (F-SIM-5)."""

    savings: Decimal | None = None
    allocation: Mapping[UUID, int] | None = None
    """Whole percentages summing to 100."""
    assumptions: Mapping[UUID, Assumption] = field(default_factory=dict)
    inflation: Decimal | None = None


BASE = WhatIf()


def scenario(b: Basis, *, years: int, what_if: WhatIf = BASE) -> mc.Scenario:
    months = years * 12
    if what_if.allocation is not None:
        core.check_allocation(what_if.allocation)
        shares = {k: Decimal(p) / 100 for k, p in what_if.allocation.items()}
    elif b.allocation is not None:
        shares = b.allocation
    else:
        raise core.ProjectionError("no category to save into: set an allocation")
    assumptions = b.assumptions | dict(what_if.assumptions)
    for a in what_if.assumptions.values():
        core.check_assumption(a)
    rate = b.inflation if what_if.inflation is None else what_if.inflation
    core.check_inflation(rate)
    owed = [Decimal(0)] * months
    freed = [Decimal(0)] * months
    for line_id, start_owed in b.start.debts.items():
        path = core.amortise(start_owed, b.debts[line_id], months=months)
        owed = [a + o for a, o in zip(owed, path.owed, strict=True)]
        freed = [a + f for a, f in zip(freed, path.freed, strict=True)]
    monthly = b.savings if what_if.savings is None else what_if.savings
    return mc.Scenario(
        categories=[
            mc.Category(
                c.id,
                c.preset,
                b.start.assets.get(c.id, Decimal(0)),
                assumptions[c.id],
                shares.get(c.id, Decimal(0)),
            )
            for c in b.categories
        ],
        savings=core.savings_path(monthly, months=months, inflation=rate, freed=freed),
        debts=owed,
        start_debts=sum(b.start.debts.values(), Decimal(0)),
        inflation=rate,
    )


@dataclass(frozen=True)
class Run:
    scenario: mc.Scenario
    outcome: mc.Outcome

    def debts(self, *, today: bool = True) -> list[Decimal]:
        """What the debt lines owe month by month, from the start: the same on every path."""
        owed = [self.scenario.start_debts, *self.scenario.debts]
        rate = self.scenario.inflation
        return [quantize(core.to_today(d, t, rate)) if today else d for t, d in enumerate(owed)]


def run(b: Basis, *, years: int, what_if: WhatIf = BASE, seed: int = mc.DEFAULT_SEED) -> Run:
    """The same draws for every scenario of a visit: their differences come from the
    assumptions only (F-SIM-4)."""
    if not MIN_YEARS <= years <= MAX_YEARS:
        raise core.ProjectionError(f"the horizon is from {MIN_YEARS} to {MAX_YEARS} years")
    chosen = scenario(b, years=years, what_if=what_if)
    return Run(chosen, mc.simulate(chosen, seed=seed))
