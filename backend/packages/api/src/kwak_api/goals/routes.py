import re
from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from kwak_core import goals as core
from kwak_core.accounts import Scope, Visibility
from kwak_core.audit import AuditAction
from kwak_core.budget import DEFAULT_BAND, Month
from kwak_core.money import quantize, require_cents
from kwak_core.recurring import Frequency
from pydantic import AfterValidator, BaseModel, Field, StringConstraints

from kwak_api.auth.routes import CurrentSession, Db, Now
from kwak_api.models import ClosedAs, Goal, GoalFunding
from kwak_api.services import audit
from kwak_api.services import goals as service

router = APIRouter(prefix="/api/goals", tags=["goals"])

MONTH = re.compile(r"[0-9]{4}-[0-9]{2}")
RATIO = Decimal("0.0001")
NOT_FOUND = HTTPException(status.HTTP_404_NOT_FOUND, "no such goal")

GoalName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
MonthText = Annotated[str, StringConstraints(max_length=7)]
# What NUMERIC(14, 2) holds, whole cents only.
Target = Annotated[Decimal, Field(gt=0, lt=Decimal("1e12")), AfterValidator(require_cents)]


def _unprocessable(message: str) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, message)


def _month(text: str) -> Month:
    try:
        month = Month.parse(text) if MONTH.fullmatch(text) else None
    except ValueError:
        month = None
    if month is None or not 1900 <= month.year <= 2200:
        raise _unprocessable(f"invalid month {text!r}, expected YYYY-MM")
    return month


def _text(month: Month | None) -> str | None:
    return None if month is None else str(month)


def _ratio(value: Decimal | None) -> Decimal | None:
    return None if value is None else value.quantize(RATIO, rounding=ROUND_HALF_UP)


def _money(value: Decimal | None) -> Decimal | None:
    return None if value is None else quantize(value)


class GoalFundingIn(BaseModel):
    line_id: UUID
    share: int = Field(ge=1, le=100)
    """In %; 100 is the line in full."""


class GoalFundingOut(BaseModel):
    line_id: UUID
    line_name: str
    share: int


class GoalIn(BaseModel):
    name: GoalName
    tier: core.Tier
    target: Target
    deadline: MonthText | None = None
    """YYYY-MM; required but for the precaution."""
    start: MonthText | None = None
    """YYYY-MM, the first month tracked; default: this month."""
    visibility: Visibility = Visibility.SHARED
    fundings: list[GoalFundingIn] = Field(default=[], max_length=50)


class GoalPatch(BaseModel):
    """Only the fields present change."""

    name: GoalName | None = None
    tier: core.Tier | None = None
    target: Target | None = None
    deadline: MonthText | None = None
    start: MonthText | None = None
    visibility: Visibility | None = None
    fundings: list[GoalFundingIn] | None = Field(default=None, max_length=50)
    """The whole list: it replaces the goal's."""
    closed_from: MonthText | None = None
    """YYYY-MM, the first month it is closed; null to reopen it."""
    closed_as: ClosedAs | None = None
    """Required to close it."""


class GoalOut(BaseModel):
    id: UUID
    name: str
    tier: core.Tier
    target: Decimal
    start: str
    deadline: str | None
    owner_id: UUID
    owner_name: str
    visibility: Visibility
    closed_from: str | None
    closed_as: ClosedAs | None
    fundings: list[GoalFundingOut]
    horizon_flagged: bool
    """The deadline lies outside the tier's horizon (F-GOAL-1)."""
    value: Decimal
    progress: Decimal
    remaining: Decimal
    months_left: int | None
    required: Decimal | None
    """The monthly effort that reaches the target at the deadline."""
    actual: Decimal | None
    """The average monthly gain over the last 6 months; null with no complete month yet."""
    estimated: str | None
    """YYYY-MM the target is reached at the actual effort."""
    never: bool
    """The actual effort is nil or negative."""
    months_early: int | None
    """Against the deadline: positive early, negative late."""
    extra: Decimal | None
    """When late, the extra monthly effort that keeps the deadline."""
    status: core.GoalStatus
    effort: Decimal | None
    """This month's share of the effort plan (F-GOAL-6); null for a goal outside it."""


def _out(goal: Goal, t: core.Tracking, this_month: Month, effort: Decimal | None) -> GoalOut:
    return GoalOut(
        id=goal.id,
        name=goal.name,
        tier=goal.tier,
        target=quantize(goal.target),
        start=str(Month.of(goal.start)),
        deadline=_text(Month.of(goal.deadline) if goal.deadline else None),
        owner_id=goal.owner_id,
        owner_name=goal.owner.display_name,
        visibility=goal.visibility,
        closed_from=_text(Month.of(goal.closed_from) if goal.closed_from else None),
        closed_as=goal.closed_as,
        fundings=[
            GoalFundingOut(line_id=f.line_id, line_name=f.line.name, share=f.share)
            for f in goal.fundings
        ],
        horizon_flagged=core.horizon_flagged(
            goal.tier, Month.of(goal.deadline) if goal.deadline else None, this_month=this_month
        ),
        value=quantize(t.value),
        progress=_ratio(t.progress) or Decimal(0),
        remaining=quantize(t.remaining),
        months_left=t.months_left,
        required=_money(t.required),
        actual=_money(t.actual),
        estimated=_text(t.estimated),
        never=t.never,
        months_early=t.months_early,
        extra=_money(t.extra),
        status=t.status,
        effort=_money(effort),
    )


class GoalTierOut(BaseModel):
    tier: core.Tier
    value: Decimal
    target: Decimal
    progress: Decimal | None
    """Each goal counting up to its target; null for a tier without a goal."""


class GoalPlanOut(BaseModel):
    capacity: Decimal
    capacity_set: bool
    """Set by hand in the household settings; else the average net cash flow."""
    precaution_share: Decimal
    unallocated: Decimal
    months_to_fill: int | None
    """At this pace, how many months fill the precaution; null without a gap."""
    shortfall: Decimal
    """What the other goals miss of their required effort this month."""


class GoalsOut(BaseModel):
    month: str
    pyramid: list[GoalTierOut]
    plan: GoalPlanOut
    goals: list[GoalOut]
    """Open goals, from the base of the pyramid up."""
    closed: list[GoalOut]


class GoalMonthOut(BaseModel):
    month: str
    value: Decimal
    gained: Decimal | None
    expected: Decimal | None
    gap: Decimal | None


class GoalDetailOut(BaseModel):
    goal: GoalOut
    months: list[GoalMonthOut]
    """From the start, the latest last."""


def _overview(db: Db, user_session: CurrentSession, now: Now, scope: Scope) -> service.Overview:
    return service.overview(db, user_session.user, scope, now.date(), DEFAULT_BAND)


@router.get("")
def list_goals(
    user_session: CurrentSession, db: Db, now: Now, scope: Scope = Scope.HOUSEHOLD
) -> GoalsOut:
    """The pyramid, the month's effort plan and the goals in scope (F-GOAL-6, 7)."""
    o = _overview(db, user_session, now, scope)
    tiers = list(core.Tier)
    efforts = o.plan.allocations
    return GoalsOut(
        month=str(o.this_month),
        pyramid=[
            GoalTierOut(
                tier=tier,
                value=quantize(p.value),
                target=quantize(p.target),
                progress=_ratio(p.progress),
            )
            for tier, p in o.pyramid.items()
        ],
        plan=GoalPlanOut(
            capacity=quantize(o.capacity),
            capacity_set=o.capacity_set,
            precaution_share=o.precaution_share,
            unallocated=quantize(o.plan.unallocated),
            months_to_fill=o.plan.months_to_fill,
            shortfall=quantize(o.plan.shortfall),
        ),
        goals=[
            _out(g, t, o.this_month, efforts.get(g.id))
            for g, t in sorted(o.open, key=lambda pair: tiers.index(pair[0].tier))
        ],
        closed=[_out(g, t, o.this_month, None) for g, t in o.closed],
    )


class GoalFixedItemOut(BaseModel):
    label: str
    frequency: Frequency
    amount: Decimal
    """The expected outflow, positive."""
    monthly: Decimal


class PrecautionProposalOut(BaseModel):
    months: int
    monthly_fixed: Decimal
    """The monthly equivalent of the active recurring expense items."""
    amount: Decimal
    items: list[GoalFixedItemOut]


@router.get("/precaution-proposal")
def precaution_proposal(
    user_session: CurrentSession,
    db: Db,
    now: Now,
    months: Annotated[int, Query(description="1 to 12")] = core.DEFAULT_PROPOSAL_MONTHS,
    scope: Scope = Scope.HOUSEHOLD,
) -> PrecautionProposalOut:
    """A target for the precaution: months of fixed expenses (F-GOAL-2)."""
    items = service.fixed_items(db, user_session.user, scope, now.date())
    monthly = core.fixed_expenses((i.frequency, -i.amount) for i in items)
    try:
        amount = core.precaution_proposal(monthly, months)
    except core.GoalError as exc:
        raise _unprocessable(str(exc)) from None
    return PrecautionProposalOut(
        months=months,
        monthly_fixed=monthly,
        amount=amount,
        items=[
            GoalFixedItemOut(
                label=i.label, frequency=i.frequency, amount=quantize(i.amount), monthly=i.monthly
            )
            for i in items
        ],
    )


@router.get("/{goal_id}")
def get_goal(goal_id: UUID, user_session: CurrentSession, db: Db, now: Now) -> GoalDetailOut:
    """A goal with its months (F-GOAL-7)."""
    o = _overview(db, user_session, now, Scope.HOUSEHOLD)
    found = next(((g, t) for g, t in [*o.open, *o.closed] if g.id == goal_id), None)
    if found is None:
        raise NOT_FOUND
    goal, t = found
    return GoalDetailOut(
        goal=_out(goal, t, o.this_month, o.plan.allocations.get(goal.id)),
        months=[
            GoalMonthOut(
                month=str(m.month),
                value=quantize(m.value),
                gained=_money(m.gained),
                expected=_money(m.expected),
                gap=_money(m.gap),
            )
            for m in t.months
        ],
    )


def _fundings(
    db: Db, user_session: CurrentSession, goal: Goal, given: list[GoalFundingIn]
) -> list[GoalFunding]:
    ids = [f.line_id for f in given]
    if len(set(ids)) != len(ids):
        raise _unprocessable("a line funds a goal once")
    lines = service.lines_by_id(db, user_session.user, ids)
    out = []
    for f in given:
        line = lines.get(f.line_id)
        if line is None:
            raise _unprocessable("unknown wealth line")
        try:
            service.check_funding(goal, line)
        except core.GoalError as exc:
            raise _unprocessable(str(exc)) from None
        out.append(GoalFunding(line_id=line.id, line=line, share=f.share))
    return out


def _check(goal: Goal, this_month: Month) -> None:
    deadline = Month.of(goal.deadline) if goal.deadline else None
    try:
        core.check_goal(
            goal.tier,
            goal.target,
            deadline=deadline,
            start=Month.of(goal.start),
            this_month=this_month,
        )
    except core.GoalError as exc:
        raise _unprocessable(str(exc)) from None


def _check_open(db: Db, goal: Goal) -> None:
    db.flush()
    try:
        service.check_open(db, goal)
    except service.SharesExceededError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"{exc} would fund open goals beyond 100 %"
        ) from None
    except service.PrecautionTakenError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from None


def _detail(db: Db, user_session: CurrentSession, now: Now, goal: Goal) -> GoalOut:
    db.flush()
    db.refresh(goal)
    return get_goal(goal.id, user_session, db, now).goal


@router.post("", status_code=status.HTTP_201_CREATED)
def create_goal(body: GoalIn, user_session: CurrentSession, db: Db, now: Now) -> GoalOut:
    """The user owns the goals they create."""
    user = user_session.user
    this_month = Month.of(now.date())
    goal = Goal(
        household_id=user.household_id,
        name=body.name,
        tier=body.tier,
        target=body.target,
        start=(_month(body.start) if body.start else this_month).first_day(),
        deadline=_month(body.deadline).first_day() if body.deadline else None,
        owner_id=user.id,
        visibility=body.visibility,
    )
    _check(goal, this_month)
    goal.fundings = _fundings(db, user_session, goal, body.fundings)
    db.add(goal)
    _check_open(db, goal)
    return _detail(db, user_session, now, goal)


def _goal(db: Db, user_session: CurrentSession, goal_id: UUID) -> Goal:
    goal = service.find(db, user_session.user, goal_id)
    if goal is None:
        raise NOT_FOUND
    return goal


@router.patch("/{goal_id}")
def update_goal(
    goal_id: UUID, body: GoalPatch, user_session: CurrentSession, db: Db, now: Now
) -> GoalOut:
    """Anyone who sees a goal edits it; only its owner changes who sees it (F-GOAL-8)."""
    goal = _goal(db, user_session, goal_id)
    given = body.model_fields_set
    this_month = Month.of(now.date())
    if body.visibility is not None and body.visibility != goal.visibility:
        if goal.owner_id != user_session.user.id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "only its owner changes who sees it")
        goal.visibility = body.visibility
    if body.name is not None:
        goal.name = body.name
    if body.tier is not None:
        goal.tier = body.tier
    if body.target is not None:
        goal.target = body.target
    if "deadline" in given:
        goal.deadline = _month(body.deadline).first_day() if body.deadline else None
    if body.start is not None:
        goal.start = _month(body.start).first_day()
    if {"deadline", "start", "tier", "target"} & given:
        # An overdue goal stays editable: its deadline is only checked when it changes.
        kept = goal.deadline if "deadline" not in given else None
        _check(goal, min(this_month, Month.of(kept)) if kept else this_month)
    if "closed_from" in given:
        if body.closed_from is None:
            goal.closed_from, goal.closed_as = None, None
        else:
            closed = _month(body.closed_from)
            if body.closed_as is None:
                raise _unprocessable("say whether the goal was reached or abandoned")
            if not Month.of(goal.start) <= closed <= this_month:
                raise _unprocessable("a goal closes from a month between its start and this one")
            goal.closed_from, goal.closed_as = closed.first_day(), body.closed_as
    if body.fundings is not None:
        goal.fundings = _fundings(db, user_session, goal, body.fundings)
    elif "visibility" in given:
        for f in goal.fundings:
            try:
                service.check_funding(goal, f.line)
            except core.GoalError as exc:
                raise _unprocessable(str(exc)) from None
    if goal.closed_from is None:
        _check_open(db, goal)
    return _detail(db, user_session, now, goal)


@router.delete("/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_goal(goal_id: UUID, user_session: CurrentSession, db: Db, now: Now) -> None:
    """With its funding, never a line. Only its owner can; closing it keeps it instead."""
    goal = _goal(db, user_session, goal_id)
    if goal.owner_id != user_session.user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "only its owner deletes it")
    audit.record(
        db,
        user_session.user,
        AuditAction.GOAL_DELETED,
        now,
        private_to=goal.owner_id if goal.visibility is Visibility.PRIVATE else None,
        name=goal.name,
        tier=goal.tier.value,
    )
    db.delete(goal)
