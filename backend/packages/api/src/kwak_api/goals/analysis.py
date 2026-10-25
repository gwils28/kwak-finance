"""The goals' Analysis tab (spec §4.12): the goals together, and the points to look at."""

from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from kwak_core import goal_analysis as ga
from kwak_core import goals as core
from kwak_core.budget import DEFAULT_BAND, Month
from kwak_core.money import quantize
from kwak_core.visibility import Scope
from pydantic import BaseModel

from kwak_api.auth.routes import CurrentSession, Db, Now
from kwak_api.services import goal_analysis as service
from kwak_api.services import goals

router = APIRouter(prefix="/api/goals/analysis", tags=["goals"])

ENOUGH_HISTORY = 3
"""Complete months of gains before the estimated date is more than a hint (F-ANA-3)."""

Horizon = Annotated[int, Query(ge=12, le=60, description="Months shown ahead, 12 to 60")]


class ForwardBandOut(BaseModel):
    goal_id: UUID
    name: str
    tier: core.Tier
    deadline: str | None
    amount: Decimal
    """Each month, from the reference month."""
    months: int
    """How many months it lasts: to the month before the deadline, or until the precaution is
    filled."""


class ForwardOut(BaseModel):
    """Required effort against capacity (F-ANA-2), over the household's goals, from the
    household's reference month."""

    reference: str | None
    months: list[str]
    bands: list[ForwardBandOut]
    """The precaution first, then the nearest deadline first."""
    totals: list[Decimal]
    over: int
    """The months above the capacity."""
    peak: Decimal
    """The largest excess over the capacity."""


class TimelineOut(BaseModel):
    """A goal's bar on the timeline (F-ANA-3)."""

    goal_id: UUID
    name: str
    tier: core.Tier
    start: str
    deadline: str | None
    estimated: str | None
    """YYYY-MM at the actual effort."""
    never: bool
    enough_history: bool
    """Three complete months or more: else the estimated date is only a hint."""
    at_plan: str | None
    """YYYY-MM at what the plan gives it; null when it gives nothing."""


class StatusMonthOut(BaseModel):
    month: str
    status: core.GoalStatus


class StatusRowOut(BaseModel):
    """A goal's statuses month by month (F-ANA-6), with today's target and deadline."""

    goal_id: UUID
    name: str
    tier: core.Tier
    months: list[StatusMonthOut]


class PointLineOut(BaseModel):
    line_id: UUID
    name: str


class PostponementOut(BaseModel):
    goal_id: UUID
    name: str
    months: int
    deadline: str
    tier: core.Tier
    lower_by: Decimal


class PointOut(BaseModel):
    """A point to look at (F-ANA-8): figures and options, never advice."""

    rule: ga.Rule
    severity: ga.Severity
    goal_id: UUID | None
    goal_name: str | None
    line_id: UUID | None
    line_name: str | None
    """The line it is about (a regulated ceiling)."""
    lines: list[PointLineOut]
    amount: Decimal | None
    deadline: str | None
    figures: dict[str, Decimal | int | bool | str | None]
    """The rule's figures: months as YYYY-MM; a ceiling's `regulated` type."""
    postponements: list[PostponementOut]
    subject_id: UUID | None
    """A goal the point names without belonging to it (idle money, the capstone)."""
    subject_name: str | None
    hideable: bool


class RiskPointOut(BaseModel):
    """A funded goal on the horizon and risk chart (F-ANA-4)."""

    goal_id: UUID
    name: str
    tier: core.Tier
    months_left: int | None
    """Null for a goal without a deadline, listed under the chart; 0 for the precaution."""
    volatility: Decimal
    """Weighted over its lines, a share (0.16 for 16 %)."""
    real_return: Decimal
    """Weighted over its lines, less the inflation, a share."""
    risky_share: Decimal
    """Its share on volatile or illiquid lines."""
    allowed_share: Decimal | None
    """The share the glide path allows, 25 to 60 months out; null elsewhere."""
    zone: ga.Zone | None
    loss: Decimal | None
    """Its envelope's change in one outcome in ten at the deadline, a share (negative: a loss)."""
    losing: bool
    """More than a tenth in a category that loses value."""


class SankeyCategoryOut(BaseModel):
    category_id: UUID
    name: str
    colour: str
    """Its `wealth-<key>` colour token."""
    amount: Decimal


class SankeyLineOut(BaseModel):
    line_id: UUID
    name: str
    category_id: UUID
    amount: Decimal
    free: Decimal
    """Beyond the envelopes of the goals the viewer sees: it may hold others' goals."""


class SankeyFlowOut(BaseModel):
    goal_id: UUID
    name: str
    tier: core.Tier
    line_id: UUID
    amount: Decimal


class SankeyElsewhereOut(BaseModel):
    """What a goal holds on lines left out of the chart (real estate, equipment)."""

    goal_id: UUID
    name: str
    tier: core.Tier
    amount: Decimal


class SankeyOut(BaseModel):
    """Where the goals' money sits (F-ANA-5): gross assets, debts not shown."""

    month: str
    all_assets: bool
    """Real estate and equipment shown too."""
    categories: list[SankeyCategoryOut]
    lines: list[SankeyLineOut]
    flows: list[SankeyFlowOut]
    elsewhere: list[SankeyElsewhereOut]


class GoalChanceOut(BaseModel):
    """The chance of reaching a goal by its deadline (F-ANA-7), on the projection's engine."""

    goal_id: UUID
    name: str
    tier: core.Tier
    deadline: str
    months_left: int
    certain: bool
    """No funding line has volatility: reached or short, rather than a chance."""
    planned: Decimal
    """The planned allocation a month (F-GOAL-6)."""
    chance_planned: Decimal
    """A share of the outcomes, at the planned allocation."""
    short_planned: Decimal | None
    """When certain: what the plan leaves missing (0 when reached)."""
    required: Decimal | None
    chance_required: Decimal | None
    short_required: Decimal | None


class PointsOut(BaseModel):
    shown: list[PointOut]
    more: list[PointOut]


class GoalAnalysisOut(BaseModel):
    month: str
    reference: str | None
    """YYYY-MM, the last month whose funding lines all have a value entered."""
    capacity: Decimal
    capacity_set: bool
    capacity_months: int
    """The complete months the capacity is measured over; 6 when it is set by hand (see
    `capacity_set`)."""
    forward: ForwardOut
    timeline: list[TimelineOut]
    statuses: list[StatusRowOut]
    risk: list[RiskPointOut]
    inflation: Decimal
    """The yearly inflation assumed, a share."""
    sankey: SankeyOut
    chances: list[GoalChanceOut]
    """Per goal, not of reaching them all: a crash hits every goal on the same lines."""
    precaution_months: int | None
    """The months the scope's plan takes to fill the precaution, shown instead of a chance."""
    points: PointsOut


def _text(month: Month | None) -> str | None:
    return None if month is None else str(month)


def _money(value: Decimal | None) -> Decimal | None:
    return None if value is None else quantize(value)


def _share(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.0001"))


def _figure(value: ga.Figure) -> Decimal | int | bool | str | None:
    if isinstance(value, Month):
        return str(value)
    if isinstance(value, Decimal):
        return quantize(value)
    return value


@router.get("")
def goal_analysis(
    user_session: CurrentSession,
    db: Db,
    now: Now,
    scope: Scope = Scope.HOUSEHOLD,
    horizon: Horizon = ga.DEFAULT_HORIZON,
    all_assets: Annotated[
        bool, Query(description="Real estate and equipment in the Sankey")
    ] = False,
) -> GoalAnalysisOut:
    """The goals at the reference month: against the capacity, on a timeline, month by month,
    and the points to look at (spec §4.12)."""
    a = service.analysis(
        db, user_session.user, scope, now.date(), DEFAULT_BAND, horizon, all_assets=all_assets
    )
    reference = a.reference or a.this_month
    names = {x.goal.id: x.goal.name for x in a.household}
    tiers = {x.goal.id: goals.tier(x.goal, a.this_month) for x in a.household}
    deadlines = {x.goal.id: x.facts.deadline for x in a.household}

    def figures(n: ga.Notice) -> dict[str, Decimal | int | bool | str | None]:
        out = {k: _figure(v) for k, v in n.figures.items()}
        if n.rule is ga.Rule.CEILING and n.line is not None:
            out["regulated"] = a.lines[n.line].regulated_type
        return out

    def point(n: ga.Notice) -> PointOut:
        return PointOut(
            rule=n.rule,
            severity=n.severity,
            goal_id=n.goal,
            goal_name=names.get(n.goal) if n.goal else None,
            line_id=n.line,
            line_name=a.lines[n.line].name if n.line else None,
            lines=[PointLineOut(line_id=k, name=a.lines[k].name) for k in n.lines],
            amount=_money(n.amount),
            deadline=_text(n.deadline),
            figures=figures(n),
            postponements=[
                PostponementOut(
                    goal_id=p.goal,
                    name=names[p.goal],
                    months=p.months,
                    deadline=str(p.deadline),
                    tier=p.tier,
                    lower_by=quantize(p.lower_by),
                )
                for p in n.postponements
            ],
            subject_id=n.subject,
            subject_name=names.get(n.subject) if n.subject else None,
            hideable=n.rule not in ga.NEVER_HIDDEN,
        )

    sk = a.sankey
    shown = sorted(
        (sk.lines[k] for k in sk.placement.lines),
        key=lambda line: (line.category.position, line.name.lower()),
    )
    categories = sorted(
        {line.category.id: line.category for line in shown}.values(), key=lambda c: c.position
    )
    goal_order = sk.goals
    line_order = [line.id for line in shown]
    flows = sorted(
        sk.placement.held.items(),
        key=lambda kv: (goal_order.index(kv[0][0]), line_order.index(kv[0][1])),
    )

    order = sorted(
        a.forward.bands,
        key=lambda g: (tiers[g] is not core.Tier.PRECAUTION, deadlines[g] or reference),
    )
    return GoalAnalysisOut(
        month=str(a.this_month),
        reference=_text(a.reference),
        capacity=quantize(a.capacity),
        capacity_set=a.capacity_set,
        capacity_months=a.capacity_months,
        forward=ForwardOut(
            reference=_text(a.household_reference),
            months=[str(m) for m in a.forward.months],
            bands=[
                ForwardBandOut(
                    goal_id=g,
                    name=names[g],
                    tier=tiers[g],
                    deadline=_text(deadlines[g]),
                    amount=quantize(a.forward.bands[g][0]),
                    months=a.bands[g][1],
                )
                for g in order
            ],
            totals=[quantize(t) for t in a.forward.totals],
            over=a.forward.over,
            peak=quantize(a.forward.peak),
        ),
        timeline=[
            TimelineOut(
                goal_id=x.goal.id,
                name=x.goal.name,
                tier=tiers[x.goal.id],
                start=str(x.facts.start),
                deadline=_text(x.facts.deadline),
                estimated=_text(x.facts.now.estimated),
                never=x.facts.now.never,
                enough_history=len(x.facts.history) > ENOUGH_HISTORY,
                at_plan=_text(service.plan_date(x, a.plan)),
            )
            for x in a.goals
        ],
        statuses=[
            StatusRowOut(
                goal_id=x.goal.id,
                name=x.goal.name,
                tier=tiers[x.goal.id],
                months=[
                    StatusMonthOut(month=str(t.months[-1].month), status=t.status)
                    for t in x.facts.history
                ],
            )
            for x in a.goals
        ],
        risk=[
            RiskPointOut(
                goal_id=p.goal.id,
                name=p.goal.name,
                tier=tiers[p.goal.id],
                months_left=p.months_left,
                volatility=_share(p.volatility),
                real_return=_share(p.real_return),
                risky_share=_share(p.risky_share),
                allowed_share=_share(p.allowed_share) if p.allowed_share is not None else None,
                zone=p.zone,
                loss=_share(p.loss) if p.loss is not None else None,
                losing=p.losing,
            )
            for p in a.risk
        ],
        inflation=_share(a.inflation),
        sankey=SankeyOut(
            month=str(sk.month),
            all_assets=sk.all_assets,
            categories=[
                SankeyCategoryOut(
                    category_id=c.id,
                    name=c.name,
                    colour=c.colour,
                    amount=quantize(sk.placement.categories[c.id]),
                )
                for c in categories
            ],
            lines=[
                SankeyLineOut(
                    line_id=line.id,
                    name=line.name,
                    category_id=line.category_id,
                    amount=quantize(sk.placement.lines[line.id]),
                    free=quantize(sk.placement.free[line.id]),
                )
                for line in shown
            ],
            flows=[
                SankeyFlowOut(
                    goal_id=g, name=names[g], tier=tiers[g], line_id=line, amount=quantize(amount)
                )
                for (g, line), amount in flows
            ],
            elsewhere=[
                SankeyElsewhereOut(goal_id=g, name=names[g], tier=tiers[g], amount=quantize(amount))
                for g in goal_order
                if (amount := sk.placement.elsewhere.get(g))
            ],
        ),
        chances=[
            GoalChanceOut(
                goal_id=c.analyzed.goal.id,
                name=c.analyzed.goal.name,
                tier=goals.tier(c.analyzed.goal, a.this_month),
                deadline=str(c.analyzed.facts.deadline),
                months_left=c.months_left,
                certain=c.at_plan.certain,
                planned=quantize(c.planned),
                chance_planned=_share(c.at_plan.chance),
                short_planned=quantize(c.at_plan.short) if c.at_plan.certain else None,
                required=_money(c.required),
                chance_required=_share(c.at_required.chance) if c.at_required else None,
                short_required=(
                    quantize(c.at_required.short)
                    if c.at_required and c.at_required.certain
                    else None
                ),
            )
            for c in a.chances
        ],
        precaution_months=a.precaution_months,
        points=PointsOut(
            shown=[point(n) for n in a.selection.shown],
            more=[point(n) for n in a.selection.more],
        ),
    )


class PointHideIn(BaseModel):
    rule: ga.Rule
    goal_id: UUID | None = None
    line_id: UUID | None = None
    action: Literal["snooze", "dismiss"]
    """Snooze until the next reference month, or dismiss until it worsens."""


@router.post("/hidden", status_code=status.HTTP_204_NO_CONTENT)
def hide_point(
    body: PointHideIn,
    user_session: CurrentSession,
    db: Db,
    now: Now,
    scope: Scope = Scope.HOUSEHOLD,
) -> None:
    """The viewer's own choice: the other members still see the point."""
    a = service.analysis(db, user_session.user, scope, now.date(), DEFAULT_BAND, ga.DEFAULT_HORIZON)
    try:
        service.hide(
            db,
            user_session.user,
            a,
            (body.rule, body.goal_id, body.line_id),
            snooze=body.action == "snooze",
        )
    except service.NoSuchPointError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such point to hide") from None


@router.delete("/hidden", status_code=status.HTTP_204_NO_CONTENT)
def show_hidden(user_session: CurrentSession, db: Db) -> None:
    """Show again every point the viewer snoozed or dismissed."""
    service.restore(db, user_session.user)
