"""Financial goals: a three-tier pyramid funded by wealth lines (F-GOAL, invariants §8.19-20).

A goal is an amount to gather by a date. Its value in a month is the sum of the values of the
wealth lines that fund it, each times its share, so it follows the wealth matrix with nothing
more to enter. Shares are rounded down to the cent, so goals never hold more than their lines.
"""

import enum
import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal
from uuid import UUID

from kwak_core.accounts import Visibility
from kwak_core.budget import DEFAULT_BAND, BudgetStatus, Month, budget_status, month_range
from kwak_core.money import quantize
from kwak_core.recurring import Frequency
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
    PRECAUTION = "precaution"
    """The emergency fund, filled first (F-GOAL-6)."""
    MEDIUM = "medium"
    """One to five years."""
    LONG = "long"
    """Beyond five years."""


class GoalStatus(enum.StrEnum):
    REACHED = "reached"
    AHEAD = "ahead"
    ON = "on"
    BEHIND = "behind"
    FILL_FIRST = "fill_first"
    """A precaution goal short of its target."""


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
    tier: Tier, target: Decimal, *, deadline: Month | None, start: Month, this_month: Month
) -> None:
    if target <= 0 or target != target.quantize(CENT):
        raise GoalError("a target is a positive amount in cents")
    if deadline is None and tier is not Tier.PRECAUTION:
        raise GoalError("a medium- or long-term goal needs a deadline")
    if start > this_month:
        raise GoalError("a goal's start is never a month to come")
    if deadline is not None and deadline < this_month:
        raise GoalError("a deadline is never a past month")


def horizon_flagged(tier: Tier, deadline: Month | None, *, this_month: Month) -> bool:
    """A deadline outside the tier's horizon: shown as a warning, never refused."""
    if deadline is None:
        return False
    months = months_between(this_month, deadline)
    if tier is Tier.PRECAUTION:
        return months > 12
    if tier is Tier.MEDIUM:
        return not 12 <= months <= 60
    return months <= 60


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

_PER_MONTH = {
    Frequency.WEEKLY: Decimal(52) / 12,
    Frequency.MONTHLY: Decimal(1),
    Frequency.QUARTERLY: Decimal(1) / 3,
    Frequency.YEARLY: Decimal(1) / 12,
}


def fixed_expenses(items: Iterable[tuple[Frequency, Decimal]]) -> Decimal:
    """The monthly equivalent of the recurring outflows given (signed, as transactions')."""
    return quantize(sum((-amount * _PER_MONTH[f] for f, amount in items if amount < 0), ZERO))


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
    """A goal uses its owner's lines and joint ones; a joint goal joint lines only."""
    if line_kind is WealthKind.DEBT:
        raise GoalError("a debt cannot fund a goal")
    if line_visibility is Visibility.JOINT:
        return
    if goal_visibility is Visibility.JOINT:
        raise GoalError("a joint goal uses joint lines only")
    if line_owner_id != goal_owner_id:
        raise GoalError("a goal uses its owner's lines and joint ones")


def check_line_shares(shares: Sequence[int]) -> None:
    """A line's shares in open goals, in %: each from 1 to 100, 100 at most in all."""
    if any(not 1 <= s <= 100 for s in shares):
        raise GoalError("a share is from 1 to 100 %")
    if sum(shares) > 100:
        raise GoalError("a line's shares sum to 100 % at most")


@dataclass(frozen=True)
class Funding:
    values: Mapping[Month, Decimal]
    """The line's monthly values, as entered (F-WLT-3)."""
    share: int
    """In %; 100 is the line in full."""
    closed_from: Month | None = None


def goal_values(fundings: Sequence[Funding], months: Sequence[Month]) -> list[Decimal]:
    """The goal's value in each month; shares hold for the whole history."""
    out = []
    for month in months:
        total = ZERO
        for f in fundings:
            cell = line_cell(f.values, month, closed_from=f.closed_from)
            if cell is not None:
                total += _floor(cell.amount * f.share / 100)
        out.append(total)
    return out


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
    tier: Tier,
    target: Decimal,
    start: Month,
    deadline: Month | None,
    values: Sequence[Decimal],
    *,
    this_month: Month,
    band: Decimal = DEFAULT_BAND,
) -> Tracking:
    """`values` are the goal's values for every month from `start` to `this_month`."""
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
    elif tier is Tier.PRECAUTION:
        status = GoalStatus.FILL_FIRST
    elif (exp := rows[-1].expected) is None:
        raise GoalError("a medium- or long-term goal needs a deadline")
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
) -> EffortPlan:
    """`precaution`: each precaution goal's gap; `others`: each goal's required effort.

    The precaution receives its gap up to `share` of the capacity, the others the rest in
    proportion to their required effort; what they leave goes to the precaution, then is
    unallocated.
    """
    check_precaution_share(share)
    gaps = {k: max(ZERO, v) for k, v in precaution.items()}
    needs = {k: max(ZERO, v) for k, v in others.items()}
    gap_total = sum(gaps.values(), ZERO)

    first = _split(min(gap_total, _floor(cap * share)), gaps)
    rest = cap - sum(first.values(), ZERO)
    second = _split(rest, needs)
    need_total = sum(needs.values(), ZERO)
    if rest >= need_total:  # the others are served: the precaution takes what they leave
        gaps_left = {k: gaps[k] - first[k] for k in gaps}
        topped = _split(min(rest - need_total, sum(gaps_left.values(), ZERO)), gaps_left)
        first = {k: first[k] + topped[k] for k in gaps}

    allocations = first | second
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
