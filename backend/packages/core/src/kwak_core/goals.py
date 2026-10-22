"""Financial goals: a three-tier pyramid funded by wealth lines (F-GOAL, invariants §8.19-20, 22).

A goal is an amount to gather by a date. Its value in a month is the sum of the values of the
wealth lines that fund it, each times its share, so it follows the wealth matrix with nothing
more to enter. Shares are rounded down to the cent, so goals never hold more than their lines.
"""

import enum
import math
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from decimal import ROUND_DOWN, Decimal
from functools import partial
from uuid import UUID

from kwak_core.budget import DEFAULT_BAND, BudgetStatus, Month, budget_status, month_range
from kwak_core.fixed import STEP, FixedFrequency
from kwak_core.money import quantize
from kwak_core.visibility import Visibility
from kwak_core.wealth import WealthKind, line_cell

ZERO = Decimal(0)
CENT = Decimal("0.01")
EFFORT_MONTHS = 6
"""The actual effort and the capacity average this many months."""
PROPOSAL_MONTHS = range(1, 13)
DEFAULT_PROPOSAL_MONTHS = 6
DEFAULT_PRECAUTION_SHARE = Decimal("0.7")
MIN_PRECAUTION_SHARE = Decimal("0.5")


class Tier(enum.StrEnum):
    """The pyramid's levels, from its foundation up."""

    PRECAUTION = "precaution"
    """The foundation: the emergency fund, filled first (F-GOAL-6)."""
    SHORT = "short"
    """Up to a year."""
    MEDIUM = "medium"
    """Over a year, up to five."""
    LONG = "long"
    """Beyond five years."""
    PLEASURE = "pleasure"
    """The capstone: what is wanted for the pleasure of it, unlocked by the rest (F-GOAL-10)."""


SHORT_MONTHS = 12
MEDIUM_MONTHS = 60
"""A deadline up to a year away is short term, up to five years medium term, then long term."""


class GoalStatus(enum.StrEnum):
    REACHED = "reached"
    AHEAD = "ahead"
    ON = "on"
    BEHIND = "behind"
    FILL_FIRST = "fill_first"
    """A precaution goal short of its target."""
    OPEN = "open"
    """A permanent goal without a deadline, short of its target: no pace to keep."""
    LOCKED = "locked"
    """A pleasure goal short of its target while its capstone is locked."""


class GoalError(ValueError):
    """A goal, a funding or a setting that breaks a rule of F-GOAL."""


def _floor(amount: Decimal) -> Decimal:
    return amount.quantize(CENT, rounding=ROUND_DOWN)


def months_between(start: Month, end: Month) -> int:
    """How many months from `start` to `end` (negative when `end` is earlier)."""
    return (end.year - start.year) * 12 + end.month - start.month


def add_months(month: Month, n: int) -> Month:
    index = month.year * 12 + month.month - 1 + n
    return Month(index // 12, index % 12 + 1)


# F-GOAL-1


def check_goal(
    target: Decimal,
    *,
    precaution: bool = False,
    permanent: bool = False,
    pleasure: bool = False,
    deadline: Month | None,
    start: Month,
    this_month: Month,
) -> None:
    if target <= 0 or target != target.quantize(CENT):
        raise GoalError("a target is a positive amount in cents")
    if precaution and not permanent:
        raise GoalError("the precaution is permanent")
    if pleasure and (precaution or permanent):
        raise GoalError("a pleasure goal is neither the precaution nor permanent")
    if pleasure and deadline is not None:
        raise GoalError("a pleasure goal has no deadline")
    if deadline is None and not (permanent or pleasure):
        raise GoalError("a goal needs a deadline, unless it is permanent")
    if start > this_month:
        raise GoalError("a goal's start is never a month to come")
    if deadline is not None and deadline < this_month:
        raise GoalError("a deadline is never a past month")


def tier_of(
    deadline: Month | None, *, this_month: Month, precaution: bool = False, pleasure: bool = False
) -> Tier:
    """The tier is never chosen: it follows the deadline, so a goal moves down as it nears.
    The precaution is the foundation, whatever its deadline, and a pleasure goal the capstone."""
    if precaution:
        return Tier.PRECAUTION
    if pleasure:
        return Tier.PLEASURE
    if deadline is None:
        return Tier.SHORT
    months = months_between(this_month, deadline)
    if months <= SHORT_MONTHS:
        return Tier.SHORT
    return Tier.MEDIUM if months <= MEDIUM_MONTHS else Tier.LONG


def check_precaution_slot(
    open_precautions: Iterable[tuple[UUID, Visibility]], owner_id: UUID, visibility: Visibility
) -> None:
    """At most one open precaution goal per member, and one joint for the household."""
    for other_owner, other_visibility in open_precautions:
        if visibility is Visibility.JOINT and other_visibility is Visibility.JOINT:
            raise GoalError("the household already has a joint precaution goal")
        if (
            visibility is not Visibility.JOINT
            and other_visibility is not Visibility.JOINT
            and other_owner == owner_id
        ):
            raise GoalError("this member already has a precaution goal")


# F-GOAL-2


def fixed_expenses(items: Iterable[tuple[FixedFrequency, Decimal]]) -> Decimal:
    """The monthly equivalent of the fixed outflows given (signed, as lines')."""
    return quantize(sum((-amount / STEP[f] for f, amount in items if amount < 0), ZERO))


def precaution_proposal(monthly_fixed: Decimal, months: int) -> Decimal:
    if months not in PROPOSAL_MONTHS:
        raise GoalError("the proposal counts 1 to 12 months")
    return quantize(monthly_fixed * months)


# F-GOAL-3


def check_funding_line(
    *,
    goal_owner_id: UUID,
    goal_visibility: Visibility,
    line_owner_id: UUID,
    line_visibility: Visibility,
    line_kind: WealthKind,
) -> None:
    """A goal uses its owner's lines and joint ones; a joint goal joint lines only; a private
    line only a private goal, whose value would otherwise show it to the household."""
    if line_kind is WealthKind.DEBT:
        raise GoalError("a debt cannot fund a goal")
    if line_visibility is Visibility.JOINT:
        return
    if goal_visibility is Visibility.JOINT:
        raise GoalError("a joint goal uses joint lines only")
    if line_owner_id != goal_owner_id:
        raise GoalError("a goal uses its owner's lines and joint ones")
    if line_visibility is Visibility.PRIVATE and goal_visibility is not Visibility.PRIVATE:
        raise GoalError("a private line funds a private goal only: it would show its value")


def check_line_shares(shares: Sequence[int]) -> None:
    """A line's shares in open goals, in %: each from 1 to 100, 100 at most in all."""
    if any(not 1 <= s <= 100 for s in shares):
        raise GoalError("a share is from 1 to 100 %")
    if sum(shares) > 100:
        raise GoalError("a line's shares sum to 100 % at most")


@dataclass(frozen=True)
class Line:
    values: Mapping[Month, Decimal]
    """The line's monthly values, as entered (F-WLT-3)."""
    closed_from: Month | None = None


def line_worth(line: Line, month: Month) -> Decimal:
    """What the line is worth in `month`: its value carried forward, never below zero."""
    cell = line_cell(line.values, month, closed_from=line.closed_from)
    return max(ZERO, cell.amount) if cell is not None else ZERO


@dataclass(frozen=True)
class Envelope:
    """A goal's claim on a line."""

    line: UUID
    share: int
    """Of the line's rises, in %."""
    opening: Decimal = ZERO
    """Taken from the line's free part in the goal's start month."""


@dataclass(frozen=True)
class FundedGoal:
    id: UUID
    target: Decimal
    start: Month
    envelopes: Sequence[Envelope]
    deadline: Month | None = None
    precaution: bool = False
    closed_from: Month | None = None
    """From this month, its envelopes are freed."""
    adjustments: Mapping[tuple[UUID, Month], Decimal] = field(default_factory=dict)
    """(line, month) -> what its envelope on the line holds from that month, set by hand."""
    pleasure: bool = False
    owner: UUID | None = None
    visibility: Visibility = Visibility.SHARED


# F-GOAL-10

AHEAD_SHARE = Decimal("0.75")
"""The share of the goals with a deadline that must be ahead to unlock the capstone."""


@dataclass(frozen=True)
class Gate:
    """What unlocks the capstone, at the end of a month."""

    precaution: Decimal | None
    """The precaution goals' progress, each counting up to its target; None without one."""
    ahead: int
    """Of the goals with a deadline, those ahead or reached."""
    counted: int
    """The open goals with a deadline."""

    @property
    def needed(self) -> int:
        return math.ceil(self.counted * AHEAD_SHARE)

    @property
    def unlocked(self) -> bool:
        return self.precaution == 1 and self.ahead >= self.needed


LOCKED = Gate(None, 0, 0)


def gate_of(precautions: Iterable[tuple[Decimal, Decimal]], statuses: Iterable[GoalStatus]) -> Gate:
    """`precautions`: each precaution goal's (value, target); `statuses`: those of the open goals
    with a deadline, the precaution and pleasure goals left out."""
    precautions = list(precautions)
    statuses = list(statuses)
    target = sum((t for _, t in precautions), ZERO)
    return Gate(
        sum((min(v, t) for v, t in precautions), ZERO) / target if target else None,
        sum(s in (GoalStatus.AHEAD, GoalStatus.REACHED) for s in statuses),
        len(statuses),
    )


def gate_at(
    goals: Iterable[FundedGoal],
    month: Month,
    values: Callable[[FundedGoal], Sequence[Decimal]],
    *,
    owner: UUID | None,
    joint: bool,
    band: Decimal = DEFAULT_BAND,
) -> Gate:
    """The gate at the end of `month` for a pleasure goal of `owner`, or a joint one: it looks
    at its owner's goals and the joint ones, a joint one at the joint ones only. `values` gives
    a goal's values from its start to `month`."""

    def counts(g: FundedGoal) -> bool:
        if g.pleasure or not (
            g.start <= month and (g.closed_from is None or month < g.closed_from)
        ):
            return False
        if g.visibility is Visibility.JOINT:
            return True
        return not joint and g.owner == owner

    open_ = [g for g in goals if counts(g)]
    return gate_of(
        ((values(g)[-1], g.target) for g in open_ if g.precaution),
        (
            track(g.target, g.start, g.deadline, values(g), this_month=month, band=band).status
            for g in open_
            if not g.precaution and g.deadline is not None
        ),
    )


@dataclass(frozen=True)
class Envelopes:
    months: Sequence[Month]
    _held: Mapping[tuple[UUID, UUID], list[Decimal]]
    _free: Mapping[UUID, list[Decimal]]
    _gates: Mapping[UUID, list[Gate]] = field(default_factory=dict)

    def held(self, goal: UUID, line: UUID) -> list[Decimal]:
        """What the goal holds on the line, month by month."""
        return self._held.get((goal, line), [ZERO] * len(self.months))

    def value(self, goal: UUID) -> list[Decimal]:
        """The goal's value, month by month: the sum of its envelopes."""
        out = [ZERO] * len(self.months)
        for (g, _), amounts in self._held.items():
            if g == goal:
                out = [a + b for a, b in zip(out, amounts, strict=True)]
        return out

    def free(self, line: UUID) -> list[Decimal]:
        """What the line holds beyond every goal's envelope, month by month."""
        return list(self._free.get(line, [ZERO] * len(self.months)))

    def gates(self, goal: UUID) -> list[Gate]:
        """A pleasure goal's gate month by month, judged at the end of the month before."""
        return list(self._gates.get(goal, [LOCKED] * len(self.months)))


def envelopes(
    lines: Mapping[UUID, Line],
    goals: Sequence[FundedGoal],
    months: Sequence[Month],
    *,
    band: Decimal = DEFAULT_BAND,
) -> Envelopes:
    """Every goal's envelopes on its lines, month by month (F-GOAL-3, invariant §8.19).

    `months` run without a gap from the earliest start. Each month: a line's rise is shared out
    by the goals it funded the month before, never beyond their targets; goals starting take
    their opening amounts from what is free; envelopes adjusted by hand take the amount set, as
    far as the line and the target allow; closed goals free theirs; then a line worth less
    than its envelopes cuts them from the pleasure goals, then the farthest deadline to the
    nearest, the precaution last. A pleasure goal takes no rise in a month its gate, judged on
    the month before, leaves locked (F-GOAL-10, invariant §8.22).
    """
    if any(g.start < months[0] for g in goals):
        raise ValueError("months must start no later than the earliest goal")
    held: dict[tuple[UUID, UUID], Decimal] = {}
    out: dict[tuple[UUID, UUID], list[Decimal]] = {
        (g.id, e.line): [] for g in goals for e in g.envelopes
    }
    free: dict[UUID, list[Decimal]] = {line: [] for line in lines}
    gates: dict[UUID, list[Gate]] = {g.id: [] for g in goals if g.pleasure}
    before = dict.fromkeys(lines, ZERO)

    def total(goal: FundedGoal) -> Decimal:
        return sum((held.get((goal.id, e.line), ZERO) for e in goal.envelopes), ZERO)

    def on_line(line: UUID) -> Decimal:
        return sum((a for (_, ln), a in held.items() if ln == line), ZERO)

    def history(goal: FundedGoal, k: int) -> list[Decimal]:
        """The goal's values from its start to months[k]."""
        series = [ZERO] * (k + 1)
        for e in goal.envelopes:
            series = [a + b for a, b in zip(series, out[(goal.id, e.line)][: k + 1], strict=True)]
        return series[months.index(goal.start) :]

    for k, month in enumerate(months):
        for g in goals:
            if g.pleasure:
                gates[g.id].append(
                    gate_at(
                        goals,
                        months[k - 1],
                        partial(history, k=k - 1),
                        owner=g.owner,
                        joint=g.visibility is Visibility.JOINT,
                        band=band,
                    )
                    if k
                    else LOCKED
                )
        worth = {line: line_worth(lines[line], month) for line in lines}
        active = [
            g
            for g in goals
            if g.start <= month and (g.closed_from is None or month < g.closed_from)
        ]
        for g in active:
            if g.start == month or (g.pleasure and not gates[g.id][-1].unlocked):
                continue
            for e in g.envelopes:
                rise = worth[e.line] - before[e.line]
                if rise > 0:
                    gain = min(_floor(rise * e.share / 100), max(ZERO, g.target - total(g)))
                    held[(g.id, e.line)] = held.get((g.id, e.line), ZERO) + gain
        for g in active:
            if g.start == month:
                for e in g.envelopes:
                    room = max(ZERO, worth[e.line] - on_line(e.line))
                    take = min(e.opening, room, max(ZERO, g.target - total(g)))
                    held[(g.id, e.line)] = take
        for g in active:
            for e in g.envelopes:
                wanted = g.adjustments.get((e.line, month))
                if wanted is None:
                    continue
                mine = held.get((g.id, e.line), ZERO)
                room = max(ZERO, worth[e.line] - on_line(e.line) + mine)
                elsewhere = total(g) - mine
                held[(g.id, e.line)] = min(wanted, room, max(ZERO, g.target - elsewhere))
        for key in [k for k in held if k[0] not in {g.id for g in active}]:
            del held[key]
        for line in lines:
            excess = on_line(line) - worth[line]
            if excess <= 0:
                continue
            claims = sorted(
                (g for g in active if (g.id, line) in held),
                key=lambda g: (
                    g.precaution,
                    not g.pleasure,
                    -months_between(month, g.deadline) if g.deadline is not None else 0,
                ),
            )
            for g in claims:
                cut = min(excess, held[(g.id, line)])
                held[(g.id, line)] -= cut
                excess -= cut
        for key, amounts in out.items():
            amounts.append(held.get(key, ZERO))
        for line in lines:
            free[line].append(worth[line] - on_line(line))
        before = worth
    return Envelopes(months, out, free, gates)


# F-GOAL-4 and 5


@dataclass(frozen=True)
class TrackedMonth:
    month: Month
    value: Decimal
    gained: Decimal | None
    """Against the month before; None for the start month."""
    expected: Decimal | None
    """On the straight line to the target at the deadline; None without a deadline."""
    gap: Decimal | None


@dataclass(frozen=True)
class Tracking:
    months: list[TrackedMonth]
    value: Decimal
    progress: Decimal
    remaining: Decimal
    months_left: int | None
    required: Decimal | None
    """The monthly effort that reaches the target at the deadline."""
    actual: Decimal | None
    """The average monthly gain over the last 6 months; None with no complete month yet."""
    estimated: Month | None
    never: bool
    """The actual effort is nil or negative: the target is never reached at this pace."""
    months_early: int | None
    """Against the deadline: positive early, negative late."""
    extra: Decimal | None
    """When late, the extra monthly effort that keeps the deadline."""
    status: GoalStatus


def track(
    target: Decimal,
    start: Month,
    deadline: Month | None,
    values: Sequence[Decimal],
    *,
    this_month: Month,
    precaution: bool = False,
    locked: bool = False,
    band: Decimal = DEFAULT_BAND,
) -> Tracking:
    """`values` are the goal's values for every month from `start` to `this_month`; `locked`
    for a pleasure goal whose capstone is locked."""
    months = month_range(start, this_month)
    if len(values) != len(months):
        raise ValueError("values must cover every month from the start to this month")
    span = months_between(start, deadline) if deadline is not None else None

    def expected(k: int) -> Decimal | None:
        if span is None:
            return None
        if span <= 0:
            return target
        return quantize(values[0] + (target - values[0]) * min(k, span) / span)

    rows = []
    for k, (month, value) in enumerate(zip(months, values, strict=True)):
        exp = expected(k)
        rows.append(
            TrackedMonth(
                month,
                value,
                value - values[k - 1] if k else None,
                exp,
                value - exp if exp is not None else None,
            )
        )

    value = values[-1]
    remaining = max(ZERO, target - value)
    months_left = months_between(this_month, deadline) if deadline is not None else None
    required = quantize(remaining / max(1, months_left)) if months_left is not None else None
    n = min(EFFORT_MONTHS, len(values) - 1)
    actual = quantize((value - values[-1 - n]) / n) if n else None

    estimated: Month | None = None
    never = False
    if remaining == 0:
        estimated = this_month
    elif actual is not None and actual > 0:
        estimated = add_months(this_month, math.ceil(remaining / actual))
    elif actual is not None:
        never = True
    months_early = (
        months_between(estimated, deadline)
        if estimated is not None and deadline is not None
        else None
    )
    extra = (
        max(ZERO, required - actual)
        if months_early is not None
        and months_early < 0
        and required is not None
        and actual is not None
        else None
    )

    if remaining == 0:
        status = GoalStatus.REACHED
    elif precaution:
        status = GoalStatus.FILL_FIRST
    elif locked:
        status = GoalStatus.LOCKED
    elif (exp := rows[-1].expected) is None:
        status = GoalStatus.OPEN
    else:
        status = _STATUS[budget_status(value, exp, band, minimum=True)]
    return Tracking(
        rows,
        value,
        value / target,
        remaining,
        months_left,
        required,
        actual,
        estimated,
        never,
        months_early,
        extra,
        status,
    )


def archives_itself(tracking: Tracking, *, permanent: bool) -> bool:
    """A goal that is not permanent is archived once it reaches its target (F-GOAL-8)."""
    return not permanent and tracking.status is GoalStatus.REACHED


_STATUS = {
    BudgetStatus.AHEAD: GoalStatus.AHEAD,
    BudgetStatus.ON: GoalStatus.ON,
    BudgetStatus.BEHIND: GoalStatus.BEHIND,
}


# F-GOAL-6


def capacity(net_flows: Sequence[Decimal]) -> Decimal:
    """The average monthly net cash flow of the complete months given, the last 6 at most."""
    recent = list(net_flows)[-EFFORT_MONTHS:]
    if not recent:
        return ZERO
    return max(ZERO, quantize(sum(recent, ZERO) / len(recent)))


def check_precaution_share(share: Decimal) -> None:
    if not MIN_PRECAUTION_SHARE <= share <= 1:
        raise GoalError("the precaution share is from 50 % to 100 %")


@dataclass(frozen=True)
class EffortPlan:
    allocations: dict[UUID, Decimal]
    unallocated: Decimal
    months_to_fill: int | None
    """At this pace, how many months fill the precaution; None without a gap."""
    shortfall: Decimal
    """What the other goals miss of their required effort this month."""


def _split(amount: Decimal, needs: Mapping[UUID, Decimal]) -> dict[UUID, Decimal]:
    """`amount` in proportion to `needs` (never beyond them), rounded down to the cent."""
    total = sum(needs.values(), ZERO)
    if total <= amount:
        return dict(needs)
    return {k: _floor(amount * need / total) for k, need in needs.items()}


def effort_plan(
    cap: Decimal,
    share: Decimal,
    *,
    precaution: Mapping[UUID, Decimal],
    others: Mapping[UUID, Decimal],
    pleasure: Mapping[UUID, Decimal] | None = None,
) -> EffortPlan:
    """`precaution`: each precaution goal's gap; `others`: each goal's required effort;
    `pleasure`: what each unlocked pleasure goal still lacks.

    The precaution receives its gap up to `share` of the capacity, the others the rest in
    proportion to their required effort; what they leave goes to the precaution, then to the
    pleasure goals in proportion to what they lack, then is unallocated.
    """
    check_precaution_share(share)
    gaps = {k: max(ZERO, v) for k, v in precaution.items()}
    needs = {k: max(ZERO, v) for k, v in others.items()}
    lacks = {k: max(ZERO, v) for k, v in (pleasure or {}).items()}
    gap_total = sum(gaps.values(), ZERO)

    first = _split(min(gap_total, _floor(cap * share)), gaps)
    rest = cap - sum(first.values(), ZERO)
    second = _split(rest, needs)
    need_total = sum(needs.values(), ZERO)
    third = dict.fromkeys(lacks, ZERO)
    if rest >= need_total:  # the others are served: the precaution takes what they leave
        gaps_left = {k: gaps[k] - first[k] for k in gaps}
        topped = _split(min(rest - need_total, sum(gaps_left.values(), ZERO)), gaps_left)
        first = {k: first[k] + topped[k] for k in gaps}
        if all(first[k] == gaps[k] for k in gaps):  # the cents a split rounds down stay out
            third = _split(rest - need_total - sum(topped.values(), ZERO), lacks)

    allocations = first | second | third
    to_precaution = sum(first.values(), ZERO)
    return EffortPlan(
        allocations,
        cap - sum(allocations.values(), ZERO),
        math.ceil(gap_total / to_precaution) if gap_total and to_precaution else None,
        need_total - sum(second.values(), ZERO),
    )


# F-GOAL-7


@dataclass(frozen=True)
class PyramidGoal:
    tier: Tier
    value: Decimal
    target: Decimal


@dataclass(frozen=True)
class TierProgress:
    value: Decimal
    target: Decimal
    progress: Decimal | None
    """Each goal counting up to its target; None for a tier without a goal."""


def pyramid(goals: Iterable[PyramidGoal]) -> dict[Tier, TierProgress]:
    out = {}
    goals = list(goals)
    for tier in Tier:
        mine = [g for g in goals if g.tier is tier]
        target = sum((g.target for g in mine), ZERO)
        capped = sum((min(g.value, g.target) for g in mine), ZERO)
        out[tier] = TierProgress(
            sum((g.value for g in mine), ZERO), target, capped / target if target else None
        )
    return out
