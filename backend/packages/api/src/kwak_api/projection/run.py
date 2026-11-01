"""The simulator's run (spec §4.11 F-SIM-5): the settings being typed, run through the engine,
nothing saved. The page posts them on every change and draws what comes back."""

from dataclasses import replace
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from kwak_analytics import montecarlo as mc
from kwak_core import projection as core
from kwak_core.budget import Month
from kwak_core.goals import add_months, months_between
from kwak_core.money import quantize, require_cents
from kwak_core.projection import Assumption, Contribution
from kwak_core.visibility import Scope
from kwak_core.wealth import SAVINGS_PRESET
from pydantic import AfterValidator, BaseModel, Field
from sqlalchemy.orm import Session

from kwak_api.models import User
from kwak_api.services import projection

HALF, NINE_TENTHS = Decimal("0.5"), Decimal("0.9")
CHANCE = Decimal("0.0001")

# Wide enough for NUMERIC, narrow enough for kwak_core to judge.
Share = Annotated[Decimal, Field(gt=-10, lt=10)]
Money = Annotated[
    Decimal, Field(gt=-Decimal("1e12"), lt=Decimal("1e12")), AfterValidator(require_cents)
]
MonthText = Annotated[str, Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")]


class RunError(ValueError):
    """A run the settings make impossible: its reason."""


class ContributionDraft(BaseModel):
    category_id: UUID
    amount: Money
    """A month, from €1 to €100,000 (kwak_core checks)."""
    indexed: bool = True


class ReturnDraft(BaseModel):
    category_id: UUID
    ret: Share
    """The category's return being typed, its volatility kept."""


class WhatIfIn(BaseModel):
    savings: Money | None = None
    """The monthly savings' total, today's euros: it scales the contributions, above zero."""
    inflation: Share | None = None
    category_id: UUID | None = None
    ret: Share | None = None
    """Null: the category's own return."""
    volatility: Share | None = None
    """Null: the category's own volatility."""


class RunIn(BaseModel):
    scope: Scope = Scope.HOUSEHOLD
    years: int = Field(ge=projection.MIN_YEARS, le=projection.MAX_YEARS)
    today: bool = True
    """Today's euros, else current ones."""
    contributions: list[ContributionDraft] | None = Field(default=None, max_length=50)
    """The contributions being typed; null: the saved ones."""
    returns: list[ReturnDraft] = Field(default_factory=list, max_length=50)
    amount: Money | None = None
    """An amount to reach, in the euros shown."""
    reach_month: MonthText | None = None
    withdrawal_rate: Share = core.DEFAULT_WITHDRAWAL
    what_ifs: list[WhatIfIn] = Field(default_factory=list, max_length=2)
    savings_source: core.SavingsSource | None = None
    """Where the savings come from, being chosen; null: the saved choice (F-SIM-3)."""


class MonthOut(BaseModel):
    month: str
    p10: Decimal
    p25: Decimal
    p50: Decimal
    p75: Decimal
    p90: Decimal
    today: Decimal
    """Where the median comes from: today's net worth..."""
    contributed: Decimal
    """...the savings added up, freed debt payments included..."""
    repaid: Decimal
    """...the capital the debts repaid..."""
    gains: Decimal
    """...and the rest, after inflation in today's euros (negative as losses)."""
    debts: Decimal
    """What the debt lines owe, the same on every path."""
    shortfall: Decimal
    """The Shortfall's median, as owed."""


class SavingsOut(BaseModel):
    source: core.SavingsSource
    """Declared: the contributions alone; measured: the capacity, split like the
    contributions if any (F-SIM-3)."""
    mode: Literal["contributions", "capacity"]
    """Declared with contributions, or the capacity (declared without any saves nothing)."""
    monthly: Decimal
    """What the household saves a month now in the projection."""
    capacity: Decimal
    capacity_set: bool
    capacity_months: int
    share_of_capacity: Decimal | None
    """The contributions over a positive capacity."""


class HorizonOut(BaseModel):
    median: Decimal
    p10: Decimal
    p90: Decimal
    income_median: Decimal
    """The liquid holdings' median times the withdrawal rate, over 12."""
    income_low: Decimal
    """The same in nine outcomes in ten."""


class ReachOut(BaseModel):
    chance: Decimal | None
    """Of being at least the amount in the month; null outside the horizon."""
    half: str | None
    """The month half the outcomes have reached it once by; null: not within the horizon."""
    ninety: str | None


class CategoryOut(BaseModel):
    id: UUID
    name: str
    colour: str
    medians: list[Decimal]
    """Its own median month by month: together they need not add up to the net worth's."""


class WhatIfOut(BaseModel):
    medians: list[Decimal]
    median: Decimal
    p10: Decimal
    p90: Decimal
    chance: Decimal | None


class RunOut(BaseModel):
    start_month: str
    months: list[MonthOut]
    savings: SavingsOut
    horizon: HorizonOut
    reach: ReachOut | None
    shortfall_share: Decimal
    """Of the outcomes whose liquid holdings run out."""
    categories: list[CategoryOut]
    """The asset categories held or saved into."""
    what_ifs: list[WhatIfOut]
    ceiling_note: bool
    """Savings accounts beyond the regulated ceilings at the horizon (F-SIM-3)."""
    paths: int
    seed: int
    engine_version: int


def _drafted(b: projection.Basis, body: RunIn) -> projection.Basis:
    """The basis with the contributions and returns being typed."""
    assets = {c.id for c in b.categories}
    contributions = b.contributions
    if body.contributions is not None:
        contributions = [
            Contribution(c.category_id, c.amount, c.indexed) for c in body.contributions
        ]
    if any(c.category_id not in assets for c in contributions):
        raise RunError("a contribution goes to an asset category")
    core.check_contributions(contributions)
    assumptions = dict(b.assumptions)
    for r in body.returns:
        if r.category_id not in assets:
            raise RunError("a return belongs to an asset category")
        assumptions[r.category_id] = Assumption(r.ret, assumptions[r.category_id].volatility)
        core.check_assumption(assumptions[r.category_id])
    choice = b.savings_choice if body.savings_source is None else body.savings_source
    return replace(
        b, contributions=list(contributions), assumptions=assumptions, savings_choice=choice
    )


def _what_if(b: projection.Basis, w: WhatIfIn) -> projection.WhatIf:
    """A field left out keeps the category's own value."""
    changes: dict[UUID, Assumption] = {}
    if w.category_id is not None:
        if w.category_id not in b.assumptions:
            raise RunError("a what-if changes an asset category")
        own = b.assumptions[w.category_id]
        if w.ret is not None or w.volatility is not None:
            changes[w.category_id] = Assumption(
                own.ret if w.ret is None else w.ret,
                own.volatility if w.volatility is None else w.volatility,
            )
    return projection.WhatIf(savings=w.savings, assumptions=changes, inflation=w.inflation)


def _chance(value: Decimal) -> Decimal:
    return value.quantize(CHANCE)


def run(db: Session, viewer: User, b: projection.Basis, body: RunIn) -> RunOut:
    """`b` read with its contributions. Raises `RunError` or `core.ProjectionError` for settings
    it cannot run."""
    core.check_withdrawal_rate(body.withdrawal_rate)
    b = _drafted(b, body)
    what_ifs_in = [_what_if(b, w) for w in body.what_ifs]
    today = body.today
    base = projection.run(b, years=body.years)
    out = base.outcome
    n = out.months
    start = b.start.month
    percentiles = out.percentiles(today=today)
    parts = core.breakdown(
        start_net=b.start.net,
        savings=base.scenario.savings,
        start_debts=base.scenario.start_debts,
        owed=base.scenario.debts,
        medians=[p[50] for p in percentiles],
        inflation=base.scenario.inflation,
        today=today,
    )
    debts = [quantize(d) for d in base.debts(today=today)]
    shortfall = out.shortfall_median(today=today)
    months = [
        MonthOut(
            month=str(add_months(start, t)),
            p10=p[10],
            p25=p[25],
            p50=p[50],
            p75=p[75],
            p90=p[90],
            today=part.today,
            contributed=part.contributed,
            repaid=part.repaid,
            gains=part.gains,
            debts=debts[t],
            shortfall=shortfall[t],
        )
        for t, (p, part) in enumerate(zip(percentiles, parts, strict=True))
    ]
    rate = body.withdrawal_rate
    horizon = HorizonOut(
        median=percentiles[n][50],
        p10=percentiles[n][10],
        p90=percentiles[n][90],
        income_median=core.withdrawal_income(out.liquid_medians(today=today)[n], rate),
        income_low=core.withdrawal_income(out.liquid_lows(today=today)[n], rate),
    )

    index = None
    if body.reach_month is not None:
        index = months_between(start, Month.parse(body.reach_month))

    def chance(o: mc.Outcome) -> Decimal | None:
        if body.amount is None or index is None or not 0 <= index <= n:
            return None
        return _chance(o.chance(body.amount, index, today=today))

    reach = None
    if body.amount is not None:
        half = out.reached_by(body.amount, HALF, today=today)
        ninety = out.reached_by(body.amount, NINE_TENTHS, today=today)
        reach = ReachOut(
            chance=chance(out),
            half=None if half is None else str(add_months(start, half)),
            ninety=None if ninety is None else str(add_months(start, ninety)),
        )

    what_ifs = []
    for w in what_ifs_in:
        other = projection.run(b, years=body.years, what_if=w).outcome
        p = other.percentiles(today=today)
        what_ifs.append(
            WhatIfOut(
                medians=[q[50] for q in p],
                median=p[n][50],
                p10=p[n][10],
                p90=p[n][90],
                chance=chance(other),
            )
        )

    by_category = out.medians_by_category(today=today)
    saved_into = {c.category_id for c in b.contributions}
    categories = [
        CategoryOut(id=c.id, name=c.name, colour=c.colour, medians=[row[k] for row in by_category])
        for k, c in enumerate(b.categories)
        if by_category[0][k] or by_category[n][k] or c.id in saved_into
    ]
    nominal = out.medians_by_category(today=False)[n]
    members = projection.members(db, viewer, body.scope)
    ceiling = any(
        c.preset == SAVINGS_PRESET
        and c.id in saved_into
        and core.beyond_ceilings(nominal[k], members=members)
        for k, c in enumerate(b.categories)
    )

    contributed = sum((c.amount for c in b.contributions), Decimal(0))
    declared = b.source is core.SavingsSource.DECLARED
    return RunOut(
        start_month=str(start),
        months=months,
        savings=SavingsOut(
            source=b.source,
            mode="contributions" if declared and b.contributions else "capacity",
            monthly=quantize(contributed if declared else b.savings),
            capacity=quantize(b.savings),
            capacity_set=b.savings_set,
            capacity_months=b.savings_months,
            share_of_capacity=(
                _chance(contributed / b.savings)
                if declared and b.contributions and b.savings > 0
                else None
            ),
        ),
        horizon=horizon,
        reach=reach,
        shortfall_share=_chance(out.shortfall_share()),
        categories=categories,
        what_ifs=what_ifs,
        ceiling_note=ceiling,
        paths=int(out.net.shape[1]),
        seed=out.seed,
        engine_version=mc.ENGINE_VERSION,
    )
