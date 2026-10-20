"""Financial goals funded by wealth lines (F-GOAL): who sees them, their funding, the pyramid
and the month's effort plan."""

from collections import defaultdict
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from uuid import UUID

from kwak_core import goals as core
from kwak_core.accounts import Scope, Visibility, can_view, in_scope
from kwak_core.analysis import counted_months
from kwak_core.budget import Month, month_range
from kwak_core.categories import CategoryKind
from kwak_core.kpis import month_figures
from kwak_core.recurring import Frequency
from kwak_core.wealth import WealthKind
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from kwak_api.models import (
    Category,
    ClosedAs,
    Goal,
    GoalFunding,
    Household,
    User,
    WealthLine,
    WealthValue,
)
from kwak_api.services import recurring, wealth
from kwak_api.services.budget import crossing_by_month, scoped_accounts
from kwak_api.services.dashboard import flows_by_month
from kwak_api.services.households import analysis_start


class SharesExceededError(Exception):
    """A line's shares in open goals would sum to more than 100 %."""

    def __init__(self, line: str, left: int) -> None:
        super().__init__(line)
        self.line, self.left = line, left


class PrecautionTakenError(Exception):
    """The owner (or the household, for a joint goal) already has an open precaution goal."""


def _loaded() -> list[object]:
    return [
        joinedload(Goal.owner),
        selectinload(Goal.fundings).joinedload(GoalFunding.line).joinedload(WealthLine.category),
    ]


def visible_goals(db: Session, viewer: User) -> list[Goal]:
    goals = db.scalars(
        select(Goal)
        .where(Goal.household_id == viewer.household_id)
        .options(*_loaded())  # type: ignore[arg-type]
        .order_by(Goal.deadline.nulls_first(), Goal.name)
    )
    return [
        g
        for g in goals
        if can_view(owner_id=g.owner_id, visibility=g.visibility, viewer_id=viewer.id)
    ]


def find(db: Session, viewer: User, goal_id: UUID) -> Goal | None:
    return next((g for g in visible_goals(db, viewer) if g.id == goal_id), None)


def check_funding(goal: Goal, line: WealthLine, visibility: Visibility | None = None) -> None:
    """`visibility`: the line's, once changed."""
    core.check_funding_line(
        goal_owner_id=goal.owner_id,
        goal_visibility=goal.visibility,
        line_owner_id=line.owner_id,
        line_visibility=visibility or line.visibility,
        line_kind=line.category.kind,
    )


def _open_shares(db: Session, line_id: UUID, but: UUID | None) -> list[int]:
    query = (
        select(GoalFunding.share)
        .join(Goal)
        .where(GoalFunding.line_id == line_id, Goal.closed_from.is_(None))
    )
    if but is not None:
        query = query.where(Goal.id != but)
    return list(db.scalars(query))


def check_open(db: Session, goal: Goal) -> None:
    """What an open goal must respect against the household's other open goals."""
    for funding in goal.fundings:
        taken = _open_shares(db, funding.line_id, goal.id)
        try:
            core.check_line_shares([*taken, funding.share])
        except core.GoalError:
            raise SharesExceededError(funding.line.name, max(0, 100 - sum(taken))) from None
    if goal.precaution:
        others = db.execute(
            select(Goal.owner_id, Goal.visibility).where(
                Goal.household_id == goal.household_id,
                Goal.precaution.is_(True),
                Goal.closed_from.is_(None),
                Goal.id != goal.id,
            )
        )
        try:
            core.check_precaution_slot([(o, v) for o, v in others], goal.owner_id, goal.visibility)
        except core.GoalError as exc:
            raise PrecautionTakenError(str(exc)) from None


def check_line_visibility(db: Session, line: WealthLine, visibility: Visibility) -> None:
    """A line keeps funding its goals under its new visibility (F-GOAL-3)."""
    for funding in db.scalars(
        select(GoalFunding)
        .where(GoalFunding.line_id == line.id)
        .options(joinedload(GoalFunding.goal))
    ):
        check_funding(funding.goal, line, visibility)


def _values(db: Session, line_ids: set[UUID]) -> dict[UUID, dict[Month, Decimal]]:
    out: dict[UUID, dict[Month, Decimal]] = defaultdict(dict)
    if line_ids:
        for line_id, month, amount in db.execute(
            select(WealthValue.line_id, WealthValue.month, WealthValue.amount).where(
                WealthValue.line_id.in_(line_ids)
            )
        ):
            out[line_id][Month.of(month)] = amount
    return out


def last_month(goal: Goal, this_month: Month) -> Month:
    """The month a goal is tracked to: this month, or the one before it closed."""
    if goal.closed_from is None:
        return this_month
    closed = Month.of(goal.closed_from).previous()
    return max(min(closed, this_month), Month.of(goal.start))


def tier(goal: Goal, this_month: Month) -> core.Tier:
    """The tier its deadline gives it in the last month it is tracked."""
    return core.tier_of(
        Month.of(goal.deadline) if goal.deadline else None,
        this_month=last_month(goal, this_month),
        precaution=goal.precaution,
    )


def _funded(goal: Goal) -> core.FundedGoal:
    return core.FundedGoal(
        goal.id,
        goal.target,
        Month.of(goal.start),
        [core.Envelope(f.line_id, f.share, f.opening) for f in goal.fundings],
        Month.of(goal.deadline) if goal.deadline else None,
        goal.precaution,
        Month.of(goal.closed_from) if goal.closed_from else None,
    )


def envelopes(db: Session, household_id: UUID, this_month: Month) -> core.Envelopes:
    """Every goal's envelopes in the household up to this month (F-GOAL-3).

    All the household's goals count, whoever sees them: a line's rises and falls are shared
    out the same way for every viewer.
    """
    goals = list(
        db.scalars(
            select(Goal)
            .where(Goal.household_id == household_id)
            .options(selectinload(Goal.fundings).joinedload(GoalFunding.line))
        )
    )
    line_rows = {f.line_id: f.line for g in goals for f in g.fundings}
    values = _values(db, set(line_rows))
    lines = {
        line_id: core.Line(
            values.get(line_id, {}),
            Month.of(line.closed_from) if line.closed_from else None,
        )
        for line_id, line in line_rows.items()
    }
    first = min((Month.of(g.start) for g in goals), default=this_month)
    return core.envelopes(
        lines, [_funded(g) for g in goals], month_range(min(first, this_month), this_month)
    )


def _at(env: core.Envelopes, month: Month) -> int:
    return list(env.months).index(month)


def held(goal: Goal, env: core.Envelopes, this_month: Month) -> dict[UUID, Decimal]:
    """What the goal holds on each of its lines in the last month it is tracked."""
    k = _at(env, last_month(goal, this_month))
    return {f.line_id: env.held(goal.id, f.line_id)[k] for f in goal.fundings}


def track(goal: Goal, env: core.Envelopes, this_month: Month, band: Decimal) -> core.Tracking:
    last = last_month(goal, this_month)
    values = env.value(goal.id)[_at(env, Month.of(goal.start)) : _at(env, last) + 1]
    return core.track(
        goal.target,
        Month.of(goal.start),
        Month.of(goal.deadline) if goal.deadline else None,
        values,
        this_month=last,
        precaution=goal.precaution,
        band=band,
    )


def reached(db: Session, goal: Goal, today: date, band: Decimal) -> bool:
    """Whether an open goal that is not permanent would archive itself at once."""
    this_month = Month.of(today)
    t = track(goal, envelopes(db, goal.household_id, this_month), this_month, band)
    return core.archives_itself(t, permanent=goal.permanent)


@dataclass
class LineFree:
    line: WealthLine
    worth: Decimal
    set_aside: Decimal
    """By the goals the viewer sees."""


def lines_free(db: Session, viewer: User, today: date) -> list[LineFree]:
    """This month, each visible asset line's worth and the part the viewer's goals set aside."""
    this_month = Month.of(today)
    env = envelopes(db, viewer.household_id, this_month)
    k = _at(env, this_month)
    goals = [g for g in visible_goals(db, viewer) if g.closed_from is None]
    lines = [
        line for line in wealth.visible_lines(db, viewer) if line.category.kind is WealthKind.ASSET
    ]
    values = _values(db, {line.id for line in lines})
    out = []
    for line in lines:
        worth = core.line_worth(
            core.Line(
                values.get(line.id, {}),
                Month.of(line.closed_from) if line.closed_from else None,
            ),
            this_month,
        )
        set_aside = sum((env.held(g.id, line.id)[k] for g in goals), Decimal(0))
        out.append(LineFree(line, worth, set_aside))
    return out


def capacity(db: Session, viewer: User, scope: Scope, this_month: Month) -> Decimal:
    """The average monthly net cash flow of the last complete months with transactions."""
    accounts = scoped_accounts(db, viewer, scope)
    last = this_month.previous()
    first = core.add_months(this_month, -core.EFFORT_MONTHS)
    months = counted_months(month_range(first, last), analysis_start(db, viewer.household_id))
    if not accounts or not months:
        return Decimal(0)
    kinds = {
        c.id: c.kind
        for c in db.scalars(select(Category).where(Category.household_id == viewer.household_id))
    }
    flows = flows_by_month(db, accounts, months[0], months[-1])
    crossed = crossing_by_month(db, accounts, months)
    nets = []
    for m in months:
        if not flows[m] and m not in crossed:
            continue  # before the first transaction: not a month of zero
        paid_in, paid_out = crossed.get(m, (Decimal(0), Decimal(0)))
        nets.append(replace(month_figures(flows[m], kinds), paid_in=paid_in, paid_out=paid_out).net)
    return core.capacity(nets)


@dataclass
class Overview:
    this_month: Month
    open: list[tuple[Goal, core.Tracking]]
    closed: list[tuple[Goal, core.Tracking]]
    pyramid: dict[core.Tier, core.TierProgress]
    capacity: Decimal
    capacity_set: bool
    precaution_share: Decimal
    plan: core.EffortPlan
    envelopes: core.Envelopes


def overview(db: Session, viewer: User, scope: Scope, today: date, band: Decimal) -> Overview:
    this_month = Month.of(today)
    goals = [
        g
        for g in visible_goals(db, viewer)
        if in_scope(scope, owner_id=g.owner_id, visibility=g.visibility, viewer_id=viewer.id)
    ]
    env = envelopes(db, viewer.household_id, this_month)
    tracked = [(g, track(g, env, this_month, band)) for g in goals]
    for g, t in tracked:
        if g.closed_from is None and core.archives_itself(t, permanent=g.permanent):
            # From next month: this month, when it got there, still counts.
            g.closed_from, g.closed_as = this_month.next().first_day(), ClosedAs.ARCHIVED
    open_ = [(g, t) for g, t in tracked if g.closed_from is None]
    closed = [(g, t) for g, t in tracked if g.closed_from is not None]

    household = db.get_one(Household, viewer.household_id)
    cap = (
        household.goal_capacity
        if household.goal_capacity is not None
        else capacity(db, viewer, scope, this_month)
    )
    plan = core.effort_plan(
        cap,
        household.precaution_share,
        precaution={g.id: t.remaining for g, t in open_ if g.precaution},
        others={
            g.id: t.required
            for g, t in open_
            if not g.precaution and t.required is not None and t.remaining
        },
    )
    return Overview(
        this_month,
        open_,
        closed,
        core.pyramid(core.PyramidGoal(tier(g, this_month), t.value, g.target) for g, t in open_),
        cap,
        household.goal_capacity is not None,
        household.precaution_share,
        plan,
        env,
    )


@dataclass
class FixedItem:
    label: str
    frequency: Frequency
    amount: Decimal
    """The expected outflow, positive."""
    monthly: Decimal


def fixed_items(db: Session, viewer: User, scope: Scope, today: date) -> list[FixedItem]:
    """The active recurring expense items of the scope's accounts, at their expected amount."""
    accounts = set(scoped_accounts(db, viewer, scope))
    savings = {
        c.id
        for c in db.scalars(
            select(Category).where(
                Category.household_id == viewer.household_id,
                Category.kind == CategoryKind.SAVINGS,
            )
        )
    }
    out = []
    for view in recurring.overview(db, viewer, today):
        item = view.item
        if (
            item.destination_id is not None
            or item.paused
            or (item.end_on is not None and item.end_on < today)
            or item.account_id not in accounts
            or item.category_id in savings
        ):
            continue
        expected = view.next.expected if view.next else item.amount
        if expected >= 0:
            continue
        out.append(
            FixedItem(
                item.label,
                item.frequency,
                -expected,
                core.fixed_expenses([(item.frequency, expected)]),
            )
        )
    return sorted(out, key=lambda i: i.label.lower())


def lines_by_id(db: Session, viewer: User, ids: list[UUID]) -> dict[UUID, WealthLine]:
    """The lines among `ids` the viewer can see."""
    wanted = set(ids)
    return {line.id: line for line in wealth.visible_lines(db, viewer) if line.id in wanted}
