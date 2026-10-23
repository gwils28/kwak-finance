"""The goals seen together, at a reference month, and the points to look at (spec §4.12)."""

import math
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from kwak_core import goal_analysis as ga
from kwak_core import goals as core
from kwak_core.budget import Month, month_range
from kwak_core.visibility import Scope, in_scope
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from kwak_api.models import Goal, GoalNoticeDismissal, Household, User, WealthLine
from kwak_api.services import goals, spending_budget


class NoSuchPointError(Exception):
    """No point to look at with that key, or one that cannot be hidden."""


@dataclass
class Analyzed:
    goal: Goal
    facts: ga.GoalFacts


@dataclass
class Analysis:
    this_month: Month
    reference: Month | None
    """The scope's: None while no funding line has a value entered."""
    household_reference: Month | None
    """The household's, for the views against the capacity."""
    capacity: Decimal
    capacity_set: bool
    capacity_months: int
    goals: list[Analyzed]
    """The open goals in scope, from the base of the pyramid up."""
    household: list[Analyzed]
    """The open goals the viewer sees, in every scope: the capacity is the household's."""
    plan: core.EffortPlan
    """The scope's, as the Goals page shows it."""
    bands: dict[UUID, tuple[Decimal, int]]
    """Each band's monthly amount and length, from the household's reference month."""
    forward: ga.Forward
    notices: list[ga.Notice]
    selection: ga.Selection
    lines: dict[UUID, WealthLine]


def _month(day: date | None) -> Month | None:
    return Month.of(day) if day else None


def _capacity_months(db: Session, household_id: UUID, this_month: Month) -> int:
    """The complete months the capacity is measured over (F-GOAL-6)."""
    return len(
        spending_budget.counted(
            month_range(core.add_months(this_month, -core.EFFORT_MONTHS), this_month.previous()),
            spending_budget.first_month(db, household_id),
        )
    )


def _facts(
    goal: Goal, env: core.Envelopes, reference: Month | None, this_month: Month, band: Decimal
) -> ga.GoalFacts:
    """The goal tracked to the reference month; a goal started since, at its start month, on
    the values carried to it; this month while nothing is entered."""
    start = Month.of(goal.start)
    last = max(start, reference) if reference is not None else this_month
    k0, k = env.months.index(start), env.months.index(last)
    risks = {f.line_id: ga.risk_of(f.line.category.preset) for f in goal.fundings}
    held = {f.line_id: env.held(goal.id, f.line_id)[k] for f in goal.fundings}
    shares = {f.line_id: f.share for f in goal.fundings}
    w = ga.weights(held, shares)
    return ga.GoalFacts(
        id=goal.id,
        target=goal.target,
        start=start,
        deadline=_month(goal.deadline),
        history=ga.history(
            goal.target,
            start,
            _month(goal.deadline),
            env.value(goal.id)[k0 : k + 1],
            precaution=goal.precaution,
            locked=[goal.pleasure and not g.unlocked for g in env.gates(goal.id)[k0 : k + 1]],
            band=band,
        ),
        held=held,
        shares=shares,
        precaution=goal.precaution,
        pleasure=goal.pleasure,
        volatility=ga.weighted(w, {line: r.volatility for line, r in risks.items()}),
    )


def _dismissals(
    db: Session, viewer: User
) -> dict[tuple[ga.Rule, UUID | None, UUID | None], ga.Dismissal]:
    out = {}
    rules = {r.value for r in ga.Rule}
    for row in db.scalars(
        select(GoalNoticeDismissal).where(GoalNoticeDismissal.user_id == viewer.id)
    ):
        if row.rule not in rules:
            continue
        out[(ga.Rule(row.rule), row.goal_id, row.line_id)] = ga.Dismissal(
            until=_month(row.until),
            severity=ga.Severity(row.severity) if row.severity else None,
            amount=row.amount,
        )
    return out


def _tiered(analyzed: list[Analyzed], this_month: Month) -> list[Analyzed]:
    tiers = list(core.Tier)
    return sorted(analyzed, key=lambda a: tiers.index(goals.tier(a.goal, this_month)))


def _reference(lines: dict[UUID, core.Line], this_month: Month) -> Month | None:
    """Searched back to the lines' first value, whenever their goals started."""
    first = min((m for line in lines.values() for m in line.values), default=None)
    if first is None:
        return None
    return ga.reference_month(lines.values(), this_month, floor=first)


def _plan(facts: list[ga.GoalFacts], cap: Decimal, share: Decimal) -> core.EffortPlan:
    """The effort plan (F-GOAL-6) over these goals, at the month they are tracked to."""
    return core.effort_plan(
        cap,
        share,
        precaution={f.id: f.now.remaining for f in facts if f.precaution},
        others={
            f.id: f.now.required
            for f in facts
            if not f.precaution and f.now.required is not None and f.now.remaining
        },
        pleasure={
            f.id: f.now.remaining
            for f in facts
            if f.pleasure and f.now.status is core.GoalStatus.OPEN and f.now.remaining
        },
    )


def analysis(
    db: Session, viewer: User, scope: Scope, today: date, band: Decimal, horizon: int
) -> Analysis:
    """The scope's goals at the scope's reference month; the views against the capacity (the
    forward efforts and R1) over the household's goals, at the household's reference month."""
    this_month = Month.of(today)
    visible = [g for g in goals.visible_goals(db, viewer) if g.closed_from is None]
    in_view = [
        g
        for g in visible
        if in_scope(scope, owner_id=g.owner_id, visibility=g.visibility, viewer_id=viewer.id)
    ]
    line_rows = {f.line_id: f.line for g in visible for f in g.fundings}
    values = goals.line_values(db, set(line_rows))
    all_lines = {
        k: core.Line(values.get(k, {}), _month(line.closed_from)) for k, line in line_rows.items()
    }
    lines = {f.line_id: all_lines[f.line_id] for g in in_view for f in g.fundings}
    reference = _reference(lines, this_month)
    household_reference = _reference(all_lines, this_month)
    env = goals.envelopes(db, viewer.household_id, this_month)
    household = [
        Analyzed(g, _facts(g, env, household_reference, this_month, band)) for g in visible
    ]
    scoped = [Analyzed(g, _facts(g, env, reference, this_month, band)) for g in in_view]

    row = db.get_one(Household, viewer.household_id)
    capacity_set = row.goal_capacity is not None
    cap = (
        row.goal_capacity
        if row.goal_capacity is not None
        else goals.capacity(db, viewer, this_month)
    )
    capacity_months = (
        core.EFFORT_MONTHS
        if capacity_set
        else _capacity_months(db, viewer.household_id, this_month)
    )
    facts = [a.facts for a in household]
    household_plan = _plan(facts, cap, row.precaution_share)
    bands = {
        f.id: (f.now.required or Decimal(0), f.now.months_left or 0)
        for f in facts
        if f.deadline is not None and not (f.precaution or f.pleasure) and f.now.remaining
    } | {
        f.id: (household_plan.allocations.get(f.id, Decimal(0)), household_plan.months_to_fill or 0)
        for f in facts
        if f.precaution and household_plan.allocations.get(f.id)
    }
    forward = ga.forward_efforts(
        household_reference or this_month, bands, capacity=cap, horizon=horizon
    )

    scope_facts = [a.facts for a in scoped]
    risks = {k: ga.risk_of(line.category.preset) for k, line in line_rows.items()}
    monthly_fixed = core.fixed_expenses(
        (i.frequency, -i.amount) for i in goals.fixed_items(db, viewer, today)
    )
    notices = [
        *ga.data_notices(ga.stale_lines(lines, this_month), capacity_months=capacity_months),
        *ga.precaution_notices(scope_facts, risks, monthly_fixed=monthly_fixed),
        *ga.unfunded_notices(scope_facts),
        *ga.overcommitted_notices(
            facts,
            capacity=cap,
            capacity_months=capacity_months,
            allocations=household_plan.allocations,
            months_to_fill=household_plan.months_to_fill,
            this_month=this_month,
        ),
        *ga.behind_notices(scope_facts),
        *ga.no_gain_notices(scope_facts),
    ]
    return Analysis(
        this_month,
        reference,
        household_reference,
        cap,
        capacity_set,
        capacity_months,
        _tiered(scoped, this_month),
        household,
        _plan(scope_facts, cap, row.precaution_share),
        bands,
        forward,
        notices,
        ga.select(notices, _dismissals(db, viewer), reference or this_month),
        {k: line_rows[k] for k in lines},
    )


def plan_date(a: Analyzed, plan: core.EffortPlan) -> Month | None:
    """When the goal is reached at what the scope's plan gives it (F-ANA-3); never for a
    pleasure goal, which shows its estimated date only."""
    remaining = a.facts.now.remaining
    reference = a.facts.reference
    if a.facts.pleasure:
        return None
    if not remaining:
        return reference
    allocation = plan.allocations.get(a.goal.id, Decimal(0))
    if allocation <= 0:
        return None
    return core.add_months(reference, math.ceil(remaining / allocation))


def hide(
    db: Session,
    viewer: User,
    found: Analysis,
    key: tuple[ga.Rule, UUID | None, UUID | None],
    *,
    snooze: bool,
) -> None:
    """Snooze a point until the next reference month, or dismiss it as it stands."""
    notice = next((n for n in found.notices if n.key == key), None)
    if notice is None or notice.rule in ga.NEVER_HIDDEN:
        raise NoSuchPointError
    rule, goal_id, line_id = key
    row = db.scalar(
        select(GoalNoticeDismissal).where(
            GoalNoticeDismissal.user_id == viewer.id,
            GoalNoticeDismissal.rule == rule.value,
            GoalNoticeDismissal.goal_id.is_(None)
            if goal_id is None
            else GoalNoticeDismissal.goal_id == goal_id,
            GoalNoticeDismissal.line_id.is_(None)
            if line_id is None
            else GoalNoticeDismissal.line_id == line_id,
        )
    ) or GoalNoticeDismissal(user_id=viewer.id, rule=rule.value, goal_id=goal_id, line_id=line_id)
    if snooze:
        row.until = (found.reference or found.this_month).next().first_day()
        row.severity = row.amount = None
    else:
        row.until = None
        row.severity, row.amount = notice.severity.value, notice.amount
    db.add(row)


def restore(db: Session, viewer: User) -> None:
    """Show again every point the viewer snoozed or dismissed."""
    db.execute(delete(GoalNoticeDismissal).where(GoalNoticeDismissal.user_id == viewer.id))
