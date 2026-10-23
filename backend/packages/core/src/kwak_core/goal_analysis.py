"""Goals analysis and points to look at (§4.12, invariants §8.30-36).

The goals seen together: against the capacity, in time and by risk, at a reference month every
funding line has a value entered in. Points to look at are fixed rules over those facts: they
state figures and options, never advice, and move nothing.
"""

import enum
import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from uuid import UUID

from kwak_core.budget import DEFAULT_BAND, Month, month_range
from kwak_core.goals import (
    GoalStatus,
    Line,
    Tier,
    Tracking,
    add_months,
    gate_of,
    months_between,
    tier_of,
    track,
)
from kwak_core.money import quantize

ZERO = Decimal(0)
VOLATILE = Decimal("0.05")
"""A category above this volatility is volatile, as one returning less than 0 (F-ANA-1)."""
MIN_CAPACITY_MONTHS = 3
"""Below this many complete months of spending, the capacity is too short to judge."""
HORIZONS = range(12, 61)
DEFAULT_HORIZON = 24
Z_ONE_IN_TEN = Decimal("1.2815515655446004")
"""The standard normal's 90th percentile."""

SHORT_RISK_MONTHS = 24
GLIDE_MONTHS = 60
ERODING_MONTHS = 96
LOSING_SHARE = Decimal("0.1")

OVER_FLOOR = Decimal(20)
OVER_SHARE = Decimal("0.05")
MAX_POSTPONEMENT = 60
MAX_MONTHS_AHEAD = 480
BEHIND_FLOOR = Decimal(50)
BEHIND_RUN = 3
BEHIND_CLEARS = 2
SOON_MONTHS = 12
NO_GAIN_MONTHS = 6
PRECAUTION_LOW = 3
PRECAUTION_SHORT = 6
SHOWN = 3
WORSENS = Decimal("1.25")
DEFAULT_INFLATION = Decimal("0.02")
"""The projection's default (F-SIM-1), until the household's own assumptions exist."""
SHORT_RISK_SHARE = Decimal("0.1")
SHORT_RISK_FLOOR = Decimal(500)
ERODING_FLOOR = Decimal(5000)
NOT_INDEXED_MONTHS = 60
IDLE_FIXED_MONTHS = 4
LEFT_OVER_FLOOR = Decimal(50)
CAPSTONE_MONTHS = 3


# F-ANA-1: the reference month


def _entered(line: Line, month: Month) -> bool:
    """Whether the line waits for a value in `month` and has one."""
    if line.closed_from is not None and month >= line.closed_from:
        return True
    if not any(m <= month for m in line.values):
        return True
    return month in line.values


def reference_month(lines: Iterable[Line], this_month: Month, *, floor: Month) -> Month | None:
    """The last month, this one at most, in which every line funding an open goal that is open
    then has a value entered (not carried); None when no month from `floor` has."""
    lines = list(lines)
    month = this_month
    while month >= floor:
        if all(_entered(line, month) for line in lines) and any(
            month in line.values for line in lines
        ):
            return month
        month = month.previous()
    return None


def stale_lines(lines: Mapping[UUID, Line], this_month: Month) -> list[UUID]:
    """The lines with no value entered for the last complete month (R0), but those opened since."""
    last = this_month.previous()
    return [
        k
        for k, line in lines.items()
        if not (line.closed_from is not None and last >= line.closed_from)
        and last not in line.values
        and not (line.values and min(line.values) > last)
    ]


# F-ANA-2: required effort against capacity


@dataclass(frozen=True)
class Forward:
    months: list[Month]
    bands: dict[UUID, list[Decimal]]
    totals: list[Decimal]
    over: int
    """The months whose stack is above the capacity."""
    peak: Decimal
    """The largest excess over the capacity."""


def forward_efforts(
    reference: Month,
    bands: Mapping[UUID, tuple[Decimal, int]],
    *,
    capacity: Decimal,
    horizon: int = DEFAULT_HORIZON,
) -> Forward:
    """`bands`: each goal's monthly amount and how many months it lasts from `reference`: a
    goal's required effort until the month before its deadline (a goal due this month for one
    month, as its required effort counts it), the precaution's allocation until it is filled.
    A goal paid its required effort keeps it, so each band is flat."""
    if horizon not in HORIZONS:
        raise ValueError("the horizon is 12 to 60 months")
    months = [add_months(reference, k) for k in range(horizon)]
    out = {
        g: [amount if k < max(1, n) else ZERO for k in range(horizon)]
        for g, (amount, n) in bands.items()
    }
    totals = [sum((b[k] for b in out.values()), ZERO) for k in range(horizon)]
    excess = [t - capacity for t in totals]
    return Forward(months, out, totals, sum(e > 0 for e in excess), max([ZERO, *excess]))


# F-ANA-4: horizon and risk


@dataclass(frozen=True)
class LineRisk:
    """A funding line's category, as the projection assumes it (F-SIM-1)."""

    ret: Decimal = ZERO
    volatility: Decimal = ZERO
    illiquid: bool = False
    current: bool = False
    """A current account."""

    @property
    def volatile(self) -> bool:
        return self.volatility > VOLATILE or self.ret < 0

    @property
    def risky(self) -> bool:
        return self.volatile or self.illiquid


DEFAULT_RISKS: Mapping[str, LineRisk] = {
    "savings": LineRisk(ret=Decimal("0.017")),
    "current": LineRisk(current=True),
    "stocks": LineRisk(ret=Decimal("0.07"), volatility=Decimal("0.16")),
    "crypto": LineRisk(ret=Decimal("0.08"), volatility=Decimal("0.6")),
    "bonds": LineRisk(ret=Decimal("0.03"), volatility=Decimal("0.06")),
    "private-equity": LineRisk(ret=Decimal("0.06"), volatility=Decimal("0.25"), illiquid=True),
    "gold": LineRisk(ret=Decimal("0.03"), volatility=Decimal("0.15")),
    "real-estate": LineRisk(ret=Decimal("0.025"), volatility=Decimal("0.08"), illiquid=True),
    "equipment": LineRisk(ret=Decimal("-0.15"), illiquid=True),
    "exotic": LineRisk(volatility=Decimal("0.2"), illiquid=True),
}
"""The projection's defaults (F-SIM-1) for the default categories, by their preset (the
default colour key, kept whatever colour the category takes), until the household's own
assumptions exist."""


def risk_of(preset: str | None) -> LineRisk:
    """A category added later, without a preset, starts at 0 % ± 0, liquid."""
    return DEFAULT_RISKS.get(preset, LineRisk()) if preset else LineRisk()


def weights(held: Mapping[UUID, Decimal], shares: Mapping[UUID, int]) -> dict[UUID, Decimal]:
    """A goal's weight on each line: what its envelope holds there over its value, or for a
    goal holding nothing yet its shares of the rises, normalised."""
    total = sum(held.values(), ZERO)
    if total > 0:
        return {k: v / total for k, v in held.items() if v > 0}
    count = sum(shares.values())
    return {k: Decimal(s) / count for k, s in shares.items()} if count else {}


def weighted(w: Mapping[UUID, Decimal], per_line: Mapping[UUID, Decimal]) -> Decimal:
    return sum((w[k] * per_line[k] for k in w), ZERO)


def loss_one_in_ten(ret: Decimal, volatility: Decimal, months: int) -> Decimal:
    """The change of a lump sum, in one outcome in ten, after `months`: the 10th percentile of
    the lognormal of F-SIM-4, whose mean annual return is `ret` and volatility `volatility`."""
    one = Decimal(1)
    if ret <= -1:
        raise ValueError("a return is above -100 %")
    annual = (one + volatility**2 / (one + ret) ** 2).ln()
    t = Decimal(months) / 12
    mean = t * ((one + ret).ln() - annual / 2)
    spread = (t * annual).sqrt()
    return (mean - Z_ONE_IN_TEN * spread).exp() - one


def glide_limit(months_left: int) -> Decimal:
    """The volatile share a goal may hold: all of it 60 months out, none at 24."""
    span = GLIDE_MONTHS - SHORT_RISK_MONTHS
    return min(Decimal(1), max(ZERO, Decimal(months_left - SHORT_RISK_MONTHS) / span))


class Zone(enum.StrEnum):
    NONE = "none"
    RED_SHORT = "red_short"
    """Near and volatile."""
    AMBER_GLIDE = "amber_glide"
    """More volatile than the glide path allows."""
    RED_ERODING = "red_eroding"
    """Far, and losing to inflation."""


def zone(months_left: int, volatility: Decimal, volatile_share: Decimal, real: Decimal) -> Zone:
    if months_left <= SHORT_RISK_MONTHS:
        return Zone.RED_SHORT if volatility > VOLATILE else Zone.NONE
    if months_left <= GLIDE_MONTHS:
        return Zone.AMBER_GLIDE if volatile_share > glide_limit(months_left) else Zone.NONE
    if months_left > ERODING_MONTHS and real <= 0:
        return Zone.RED_ERODING
    return Zone.NONE


def losing_value(w: Mapping[UUID, Decimal], risks: Mapping[UUID, LineRisk]) -> bool:
    """More than 10 % of the goal in a category whose return is below 0."""
    return sum((w[k] for k in w if risks[k].ret < 0), ZERO) > LOSING_SHARE


# F-ANA-6: status by month


def history(
    target: Decimal,
    start: Month,
    deadline: Month | None,
    values: Sequence[Decimal],
    *,
    precaution: bool = False,
    locked: Sequence[bool] = (),
    band: Decimal = DEFAULT_BAND,
) -> list[Tracking]:
    """The goal tracked at each month from its start, as F-GOAL-4 and 5 judged it then, with
    today's target and deadline; `values` run from the start to the reference month, and
    `locked`, for a pleasure goal, tells the months its capstone was locked."""
    return [
        track(
            target,
            start,
            deadline,
            values[: k + 1],
            this_month=month,
            precaution=precaution,
            locked=k < len(locked) and locked[k],
            band=band,
        )
        for k, month in enumerate(month_range(start, add_months(start, len(values) - 1)))
    ]


# F-ANA-8: points to look at


class Severity(enum.StrEnum):
    WARNING = "warning"
    INFO = "info"
    GOOD = "good"


_SEVERITY = [Severity.WARNING, Severity.INFO, Severity.GOOD]


class Rule(enum.StrEnum):
    """The rules, in the order their points are shown within a severity."""

    DATA = "data"
    """R0."""
    PRECAUTION_NONE = "precaution_none"
    PRECAUTION_LOW = "precaution_low"
    PRECAUTION_RISKY = "precaution_risky"
    UNFUNDED = "unfunded"
    """R11."""
    OVERCOMMITTED = "overcommitted"
    """R1."""
    SHORT_RISK = "short_risk"
    """R3."""
    BEHIND = "behind"
    """R2."""
    NO_GAIN = "no_gain"
    """R9."""
    COSTLY_DEBT = "costly_debt"
    """R12."""
    PRECAUTION_CURRENT = "precaution_current"
    IDLE = "idle"
    """R7."""
    CEILING = "ceiling"
    """R6."""
    DEBT_PAYMENTS = "debt_payments"
    """R13."""
    ERODING = "eroding"
    """R4."""
    LOSING_VALUE = "losing_value"
    """R3b."""
    NOT_INDEXED = "not_indexed"
    """R10."""
    CAPSTONE = "capstone"
    """R8."""
    LEFT_OVER = "left_over"
    """R14."""


_RANK = list(Rule)
NEVER_HIDDEN = frozenset({Rule.DATA, Rule.PRECAUTION_NONE})
SILENCED_BY_DATA = frozenset({Rule.BEHIND, Rule.IDLE, Rule.NO_GAIN})

Figure = Decimal | int | bool | Month | None


@dataclass(frozen=True)
class Postponement:
    goal: UUID
    months: int
    deadline: Month
    tier: Tier
    """The tier the goal would be in."""
    lower_by: Decimal
    """Or lowering its target by this much fits too."""


@dataclass(frozen=True)
class Notice:
    rule: Rule
    severity: Severity
    goal: UUID | None = None
    line: UUID | None = None
    amount: Decimal | None = None
    """The point's main amount, which a dismissed point is watched on."""
    deadline: Month | None = None
    lines: tuple[UUID, ...] = ()
    """The lines it is about, for R0."""
    figures: Mapping[str, Figure] = field(default_factory=dict)
    postponements: tuple[Postponement, ...] = ()
    subject: UUID | None = None
    """A goal the point names without belonging to it (R7, R8)."""

    @property
    def key(self) -> tuple[Rule, UUID | None, UUID | None]:
        return self.rule, self.goal, self.line


@dataclass(frozen=True)
class GoalFacts:
    """An open goal at the reference month."""

    id: UUID
    target: Decimal
    start: Month
    deadline: Month | None
    history: Sequence[Tracking]
    """From its start to the reference month."""
    held: Mapping[UUID, Decimal]
    """What its envelopes hold, line by line."""
    shares: Mapping[UUID, int]
    """Its shares of the lines' rises: no line, no funding."""
    precaution: bool = False
    pleasure: bool = False
    volatility: Decimal = ZERO
    """Weighted over its lines (F-ANA-1)."""

    @property
    def now(self) -> Tracking:
        return self.history[-1]

    @property
    def reference(self) -> Month:
        return add_months(self.start, len(self.history) - 1)


def data_notices(stale: Sequence[UUID], *, capacity_months: int) -> list[Notice]:
    """R0: values to enter, or a capacity measured over too few months."""
    out = [Notice(Rule.DATA, Severity.WARNING, lines=tuple(stale))] if stale else []
    if capacity_months < MIN_CAPACITY_MONTHS:
        out.append(
            Notice(Rule.DATA, Severity.WARNING, figures={"capacity_months": capacity_months})
        )
    return out


def precaution_notices(
    goals: Sequence[GoalFacts], risks: Mapping[UUID, LineRisk], *, monthly_fixed: Decimal
) -> list[Notice]:
    """R5: no precaution, one below months of fixed expenses, or one on risky lines."""
    precautions = [g for g in goals if g.precaution]
    if not precautions:
        return [Notice(Rule.PRECAUTION_NONE, Severity.WARNING)]
    out = []
    for g in precautions:
        if monthly_fixed > 0:
            months = g.target / monthly_fixed
            if months < PRECAUTION_SHORT:
                low = months < PRECAUTION_LOW
                out.append(
                    Notice(
                        Rule.PRECAUTION_LOW,
                        Severity.WARNING if low else Severity.INFO,
                        goal=g.id,
                        amount=quantize(
                            (PRECAUTION_LOW if low else PRECAUTION_SHORT) * monthly_fixed - g.target
                        ),
                        figures={"months": quantize(months), "monthly_fixed": monthly_fixed},
                    )
                )
        risky = sum((v for k, v in g.held.items() if risks[k].risky), ZERO)
        if risky > 0:
            out.append(Notice(Rule.PRECAUTION_RISKY, Severity.WARNING, goal=g.id, amount=risky))
        current = sum((v for k, v in g.held.items() if risks[k].current), ZERO)
        if current > 0:
            out.append(Notice(Rule.PRECAUTION_CURRENT, Severity.INFO, goal=g.id, amount=current))
    return out


def unfunded_notices(goals: Sequence[GoalFacts]) -> list[Notice]:
    """R11: a goal no line funds can never progress."""
    return [
        Notice(Rule.UNFUNDED, Severity.WARNING, goal=g.id, amount=g.target, deadline=g.deadline)
        for g in goals
        if not g.shares
    ]


def _dated(goals: Sequence[GoalFacts]) -> list[GoalFacts]:
    return [g for g in goals if g.deadline is not None and not (g.precaution or g.pleasure)]


def _postpone(remaining: Decimal, months: int, room: Decimal) -> int | None:
    """The fewest months by which what is left, over them, needs no more than `room`."""
    if room <= 0:
        return None
    n = max(months + 1, math.ceil(remaining / room))
    while n > months + 1 and quantize(remaining / (n - 1)) <= room:
        n -= 1
    while quantize(remaining / n) > room:
        n += 1
    return n


def overcommitted_notices(
    goals: Sequence[GoalFacts],
    *,
    capacity: Decimal,
    capacity_months: int,
    allocations: Mapping[UUID, Decimal],
    months_to_fill: int | None,
    this_month: Month,
) -> list[Notice]:
    """R1, over the household's goals: their required efforts, next to what the plan gives the
    precaution while it fills (F-GOAL-6), against the capacity."""
    if capacity_months < MIN_CAPACITY_MONTHS:
        return []
    dated = _dated(goals)
    required = {g.id: g.now.required or ZERO for g in dated}
    precaution = sum((allocations.get(g.id, ZERO) for g in goals if g.precaution), ZERO)
    excess = sum(required.values(), ZERO) + precaution - capacity
    if excess <= max(OVER_FLOOR, OVER_SHARE * capacity):
        return []
    if months_to_fill is not None and precaution > 0:
        m = months_to_fill
        later = [
            (g.now.remaining - allocations.get(g.id, ZERO) * m, (g.now.months_left or 0) - m)
            for g in dated
        ]
        if all(n > 0 or left <= 0 for left, n in later) and (
            sum((quantize(left / n) for left, n in later if left > 0), ZERO) <= capacity
        ):
            return [
                Notice(
                    Rule.OVERCOMMITTED,
                    Severity.INFO,
                    amount=excess,
                    figures={"months_to_fill": m},
                )
            ]
    postponements = []
    for g in sorted(dated, key=lambda g: g.deadline or g.start, reverse=True):
        months = g.now.months_left or 0
        n = _postpone(g.now.remaining, months, required[g.id] - excess)
        if n is None or n - months > MAX_POSTPONEMENT:
            continue
        deadline = add_months(g.reference, n)
        if months_between(this_month, deadline) > MAX_MONTHS_AHEAD:
            continue
        postponements.append(
            Postponement(
                g.id,
                n - months,
                deadline,
                tier_of(deadline, this_month=this_month),
                excess * max(1, months),
            )
        )
    return [
        Notice(
            Rule.OVERCOMMITTED,
            Severity.WARNING,
            amount=excess,
            postponements=tuple(postponements),
        )
    ]


def _soon(g: GoalFacts) -> Severity:
    months = g.now.months_left
    return Severity.WARNING if months is not None and months <= SOON_MONTHS else Severity.INFO


def _behind_now(history: Sequence[Tracking]) -> bool:
    """Behind for three months by a real gap, until two months in a row are not."""
    on = False
    run = calm = 0
    for t in history:
        gap = t.months[-1].gap
        behind = t.status is GoalStatus.BEHIND
        real = behind and gap is not None and -gap >= max(BEHIND_FLOOR, t.required or ZERO)
        run = run + 1 if real else 0
        calm = 0 if behind else calm + 1
        if run >= BEHIND_RUN:
            on = True
        elif calm >= BEHIND_CLEARS:
            on = False
    return on


def behind_notices(goals: Sequence[GoalFacts]) -> list[Notice]:
    """R2: behind for three months."""
    out = []
    for g in _dated(goals):
        if not _behind_now(g.history):
            continue
        now = g.now
        reachable = (
            min(g.target, now.value + now.actual * (now.months_left or 0))
            if now.actual is not None and now.actual > 0
            else None
        )
        out.append(
            Notice(
                Rule.BEHIND,
                _soon(g),
                goal=g.id,
                amount=max(ZERO, -(now.months[-1].gap or ZERO)),
                deadline=g.deadline,
                figures={
                    "extra": max(
                        ZERO,
                        now.extra
                        if now.extra is not None
                        else (now.required or ZERO) - max(ZERO, now.actual or ZERO),
                    ),
                    "estimated": now.estimated,
                    "never": now.never,
                    "reachable": reachable,
                    "market": g.volatility > VOLATILE,
                },
            )
        )
    return out


def no_gain_notices(goals: Sequence[GoalFacts]) -> list[Notice]:
    """R9: six months old or more, and no month with a gain in the last six."""
    out = []
    for g in goals:
        now = g.now
        if (
            months_between(g.start, g.reference) < NO_GAIN_MONTHS
            or now.status in (GoalStatus.REACHED, GoalStatus.LOCKED)
            or any((m.gained or ZERO) > 0 for m in now.months[-NO_GAIN_MONTHS:])
        ):
            continue
        out.append(
            Notice(
                Rule.NO_GAIN,
                _soon(g),
                goal=g.id,
                amount=now.remaining,
                deadline=g.deadline,
                figures={"required": now.required},
            )
        )
    return out


def _risky(g: GoalFacts, risks: Mapping[UUID, LineRisk]) -> Decimal:
    return sum((v for k, v in g.held.items() if risks[k].risky), ZERO)


def short_risk_notices(goals: Sequence[GoalFacts], risks: Mapping[UUID, LineRisk]) -> list[Notice]:
    """R3: a goal near its deadline on volatile or illiquid lines, and the glide path."""
    out = []
    for g in _dated(goals):
        months = g.now.months_left or 0
        value = g.now.value
        risky = _risky(g, risks)
        if value <= 0 or months > GLIDE_MONTHS or not g.now.remaining:
            continue
        share = risky / value
        if months <= SHORT_RISK_MONTHS:
            if share <= SHORT_RISK_SHARE or risky <= SHORT_RISK_FLOOR:
                continue
            severity = Severity.WARNING
        elif share > glide_limit(months):
            severity = Severity.INFO
        else:
            continue
        w = weights(g.held, g.shares)
        ret = weighted(w, {k: risks[k].ret for k in w})
        sigma = weighted(w, {k: risks[k].volatility for k in w})
        loss = -loss_one_in_ten(ret, sigma, max(1, months)) * value
        out.append(
            Notice(
                Rule.SHORT_RISK,
                severity,
                goal=g.id,
                amount=risky,
                deadline=g.deadline,
                figures={
                    "loss": quantize(max(ZERO, loss)),
                    "months": months,
                },
            )
        )
    return out


def losing_value_notices(
    goals: Sequence[GoalFacts], risks: Mapping[UUID, LineRisk]
) -> list[Notice]:
    """R3b: more than a tenth of a goal in a category that loses value."""
    out = []
    for g in goals:
        w = weights(g.held, g.shares)
        if not w or not losing_value(w, risks):
            continue
        losing = sum((v for k, v in g.held.items() if risks[k].ret < 0), ZERO)
        if losing <= 0:
            continue
        out.append(
            Notice(Rule.LOSING_VALUE, Severity.INFO, goal=g.id, amount=losing, deadline=g.deadline)
        )
    return out


def eroding_notices(
    goals: Sequence[GoalFacts], risks: Mapping[UUID, LineRisk], *, inflation: Decimal
) -> list[Notice]:
    """R4: a long goal on lines that earn no more than inflation."""
    out = []
    for g in _dated(goals):
        months = g.now.months_left or 0
        w = weights(g.held, g.shares)
        if months <= ERODING_MONTHS or not w or g.now.value + g.now.remaining < ERODING_FLOOR:
            continue
        ret = weighted(w, {k: risks[k].ret for k in w})
        if ret - inflation > 0:
            continue
        years = Decimal(months) / 12
        erosion = quantize(g.now.value * (1 - ((1 + ret) / (1 + inflation)) ** years))
        if erosion <= 0:
            continue
        out.append(
            Notice(
                Rule.ERODING,
                Severity.INFO,
                goal=g.id,
                amount=erosion,
                deadline=g.deadline,
                figures={"months": months},
            )
        )
    return out


def not_indexed_notices(goals: Sequence[GoalFacts], *, inflation: Decimal) -> list[Notice]:
    """R10: a target in today's euros, more than five years away."""
    out = []
    for g in _dated(goals):
        months = g.now.months_left or 0
        if months <= NOT_INDEXED_MONTHS or not g.now.remaining:
            continue
        out.append(
            Notice(
                Rule.NOT_INDEXED,
                Severity.INFO,
                goal=g.id,
                amount=g.target,
                deadline=g.deadline,
                figures={
                    "indexed": quantize(g.target * (1 + inflation) ** (Decimal(months) / 12)),
                    "months": months,
                },
            )
        )
    return out


def idle_notices(
    goals: Sequence[GoalFacts],
    *,
    current_free: Decimal,
    income: Decimal,
    spending: Decimal,
    history_months: int,
    monthly_fixed: Decimal,
) -> list[Notice]:
    """R7: more on the current accounts, free of every goal, than a month's income and spending
    (next month's salary sits there at the end of a month). Spending counts as an amount,
    whatever its sign."""
    threshold = (
        income + abs(spending)
        if history_months >= MIN_CAPACITY_MONTHS
        else IDLE_FIXED_MONTHS * monthly_fixed
    )
    excess = current_free - threshold
    if threshold <= 0 or excess <= 0:
        return []
    behind = sorted(
        (g for g in _dated(goals) if g.now.status is GoalStatus.BEHIND),
        key=lambda g: g.deadline or g.start,
    )
    short = [g for g in goals if g.precaution and g.now.remaining]
    if behind:
        subject, gap = behind[0], -(behind[0].now.months[-1].gap or ZERO)
    elif short:
        subject, gap = short[0], short[0].now.remaining
    else:
        subject, gap = None, ZERO
    return [
        Notice(
            Rule.IDLE,
            Severity.WARNING if subject else Severity.INFO,
            amount=quantize(excess),
            subject=subject.id if subject else None,
            figures={"set_aside": quantize(min(excess, gap)) if subject else None},
        )
    ]


def _to_ahead(expected: Decimal, value: Decimal, target: Decimal, band: Decimal) -> Decimal:
    """The fewest whole euros that make a goal ahead (strictly above its expected value and
    the band, kwak_core.budget.budget_status) or reached, which counts as ahead too."""
    above = Decimal(math.floor(expected * (1 + band) - value) + 1)
    return max(ZERO, min(above, Decimal(math.ceil(target - value))))


def capstone_notices(goals: Sequence[GoalFacts], *, band: Decimal = DEFAULT_BAND) -> list[Notice]:
    """R8: how close the capstone is, when there are pleasure goals to unlock. The goals given
    are the scope's: in *mine* and *joint* the capstone's own reckoning (F-GOAL-10); in the
    household, everyone's together. The one-off amount makes one goal ahead now; "monthly" is
    what it would take each month, in all, to be ahead in three months."""
    if not any(g.pleasure for g in goals):
        return []
    precautions = [g for g in goals if g.precaution]
    dated = _dated(goals)
    gate = gate_of(((g.now.value, g.target) for g in precautions), (g.now.status for g in dated))
    if gate.precaution is None:
        return []
    if gate.precaution < 1:
        missing = sum((g.now.remaining for g in precautions), ZERO)
        return [
            Notice(
                Rule.CAPSTONE,
                Severity.GOOD,
                amount=missing,
                figures={"progress": gate.precaution.quantize(Decimal("0.01"))},
            )
        ]
    if gate.needed - gate.ahead != 1:
        return []
    options = []
    for g in dated:
        if g.now.status not in (GoalStatus.ON, GoalStatus.BEHIND):
            continue
        expected = g.now.months[-1].expected or ZERO
        once = _to_ahead(expected, g.now.value, g.target, band)
        months = max(1, g.now.months_left or 1)
        later = expected + (g.target - expected) * min(CAPSTONE_MONTHS, months) / months
        # In all, a month for three months, from what it holds now.
        monthly = Decimal(
            math.ceil(_to_ahead(later, g.now.value, g.target, band) / CAPSTONE_MONTHS)
        )
        options.append((once, g.deadline or g.start, g, monthly))
    if not options:
        return []
    once, _, g, monthly = min(options, key=lambda o: (o[0], o[1]))
    return [
        Notice(
            Rule.CAPSTONE,
            Severity.GOOD,
            amount=once,
            subject=g.id,
            figures={"monthly": monthly, "months": CAPSTONE_MONTHS},
        )
    ]


def left_over_notices(
    goals: Sequence[GoalFacts], *, unallocated: Decimal, capacity_months: int
) -> list[Notice]:
    """R14: the plan leaves capacity over, and no goal is behind."""
    if (
        capacity_months < MIN_CAPACITY_MONTHS
        or unallocated <= LEFT_OVER_FLOOR
        or any(g.now.status is GoalStatus.BEHIND for g in goals)
    ):
        return []
    return [Notice(Rule.LEFT_OVER, Severity.GOOD, amount=quantize(unallocated))]


# Order, one per goal, dismissal (invariant §8.36)


@dataclass(frozen=True)
class Dismissal:
    """A member's choice on a point: snoozed `until` a month, or dismissed as it was then."""

    until: Month | None = None
    severity: Severity | None = None
    amount: Decimal | None = None


def hidden(notice: Notice, dismissal: Dismissal, reference: Month) -> bool:
    if notice.rule in NEVER_HIDDEN:
        return False
    if dismissal.until is not None:
        return reference < dismissal.until
    if dismissal.severity is not None and _SEVERITY.index(notice.severity) < _SEVERITY.index(
        dismissal.severity
    ):
        return False
    return not (
        dismissal.amount is not None
        and notice.amount is not None
        and notice.amount > dismissal.amount * WORSENS
    )


@dataclass(frozen=True)
class Selection:
    shown: list[Notice]
    more: list[Notice]


def select(
    notices: Iterable[Notice],
    dismissals: Mapping[tuple[Rule, UUID | None, UUID | None], Dismissal],
    reference: Month,
) -> Selection:
    """Stale data silences what it would skew; then the points not hidden, most severe first,
    in the rules' order, nearest deadline first, at most one per goal; three shown."""
    notices = list(notices)
    stale = any(n.rule is Rule.DATA for n in notices)
    kept = [
        n
        for n in notices
        if not (stale and n.rule in SILENCED_BY_DATA)
        and not (n.key in dismissals and hidden(n, dismissals[n.key], reference))
    ]
    kept.sort(
        key=lambda n: (
            _SEVERITY.index(n.severity),
            _RANK.index(n.rule),
            n.deadline is None,
            n.deadline or reference,
        )
    )
    seen: set[UUID] = set()
    out = []
    for n in kept:
        if n.goal is not None:
            if n.goal in seen:
                continue
            seen.add(n.goal)
        out.append(n)
    return Selection(out[:SHOWN], out[SHOWN:])
