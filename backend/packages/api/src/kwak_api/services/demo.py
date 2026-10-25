"""The demo household (F-ADM-5): written from `kwak_core.demo`, kept until a reset, never mixed
with the real household (invariant §8.40)."""

from datetime import UTC, datetime, time, timedelta
from uuid import UUID

from kwak_core.categories import DEFAULT_SPENDING_CATEGORIES
from kwak_core.demo import Demo, generate
from kwak_core.users import Language
from sqlalchemy import delete, select, text, update
from sqlalchemy.orm import Session

from kwak_api.models import (
    AuditEvent,
    ClosedAs,
    FixedExpense,
    FixedSkip,
    Goal,
    GoalFunding,
    GoalNoticeDismissal,
    Household,
    Invite,
    MemberRetirement,
    Role,
    SpendingCategory,
    SpendingLine,
    SpendingLinePart,
    SpendingTarget,
    User,
    UserSession,
    WealthCategory,
    WealthLine,
    WealthValue,
)
from kwak_api.services import spending, wealth

NO_PASSWORD = "!"  # noqa: S105 - not a password: what none matches
"""Not an argon2 hash: no password ever matches it."""


def demo_household(db: Session) -> Household | None:
    return db.scalar(select(Household).where(Household.is_demo))


def _owner(db: Session, household_id: UUID) -> User:
    return db.scalars(
        select(User).where(User.household_id == household_id, User.role == Role.OWNER)
    ).one()


DEMO_LOCK = 0x6B77616B64656D6F
"""The advisory lock that serialises opening and resetting the demo ("kwakdemo")."""
RESET_PAUSE = timedelta(minutes=1)
"""How long a demo is kept before it can be reset again."""


class ResetTooSoonError(Exception):
    """The demo was generated less than RESET_PAUSE ago."""


def _lock(db: Session) -> None:
    """Held to the end of the transaction: two members opening or resetting the demo at once
    neither generate it twice nor point a session at a demo being deleted."""
    db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": DEMO_LOCK})


def enter(db: Session, user_session: UserSession, now: datetime) -> None:
    """Act as the demo's owner, generating the demo on first use."""
    _lock(db)
    household = demo_household(db)
    owner = (
        _owner(db, household.id)
        if household
        else build(db, generate(now.date(), user_session.account.language or Language.EN), now)
    )
    user_session.acting_user = owner


def leave(user_session: UserSession) -> None:
    user_session.acting_user = None


def reset(db: Session, user_session: UserSession, now: datetime) -> None:
    """Delete the whole demo and generate it again, dated from today. Every session that was in
    the old demo is in the new one: none falls back to its household unawares."""
    _lock(db)
    household = demo_household(db)
    inside: list[UUID] = []
    if household is not None:
        if now - household.created_at < RESET_PAUSE:
            raise ResetTooSoonError
        users = select(User.id).where(User.household_id == household.id)
        inside = list(
            db.scalars(
                select(UserSession.id).where(
                    UserSession.acting_user_id.in_(users), UserSession.id != user_session.id
                )
            )
        )
        user_session.acting_user = None
        db.flush()
        _delete(db, household.id)
        db.expire_all()
    owner = build(db, generate(now.date(), user_session.account.language or Language.EN), now)
    db.execute(
        update(UserSession).where(UserSession.id.in_(inside)).values(acting_user_id=owner.id),
        execution_options={"synchronize_session": False},
    )
    user_session.acting_user = owner


def _delete(db: Session, household_id: UUID) -> None:
    """Every row of the demo household, children before parents; the database cascades the
    rest (values, fundings, adjustments, parts, skips, targets, recovery codes)."""
    users = select(User.id).where(User.household_id == household_id).scalar_subquery()
    for statement in (
        delete(GoalNoticeDismissal).where(GoalNoticeDismissal.user_id.in_(users)),
        delete(Goal).where(Goal.household_id == household_id),
        delete(WealthLine).where(WealthLine.household_id == household_id),
        delete(WealthCategory).where(WealthCategory.household_id == household_id),
        delete(SpendingLine).where(SpendingLine.household_id == household_id),
        delete(FixedExpense).where(FixedExpense.household_id == household_id),
        delete(SpendingCategory).where(SpendingCategory.household_id == household_id),
        delete(Invite).where(Invite.household_id == household_id),
        delete(AuditEvent).where(AuditEvent.household_id == household_id),
        delete(MemberRetirement).where(MemberRetirement.user_id.in_(users)),
        delete(User).where(User.household_id == household_id),
        delete(Household).where(Household.id == household_id, Household.is_demo),
    ):
        db.execute(statement, execution_options={"synchronize_session": False})


def build(db: Session, demo: Demo, now: datetime) -> User:
    """Write the demo household; return its owner."""
    household = Household(
        name=demo.household,
        is_demo=True,
        wealth_start=demo.wealth_start.first_day(),
        created_at=now,
    )
    db.add(household)
    db.flush()
    users = {
        m.key: User(
            household_id=household.id,
            email=f"{m.key}.{household.id.hex[:12]}@demo.invalid",
            display_name=m.name,
            password_hash=NO_PASSWORD,
            role=Role.OWNER if m.owner else Role.MEMBER,
            language=demo.language,
        )
        for m in demo.members
    }
    db.add_all(users.values())
    db.flush()
    db.add_all(
        MemberRetirement(
            user_id=users[m.key].id,
            birth=m.birth.first_day(),
            retirement=m.retirement.first_day(),
            earnings=m.earnings,
            pension_month=m.pension_month.first_day(),
            pension=m.pension,
        )
        for m in demo.members
    )

    spending.seed_categories(db, household.id, demo.language)
    wealth.seed_defaults(db, household.id, demo.language)
    by_name = {c.position: c.id for c in spending.categories(db, household.id)}
    category = {d.names.en: by_name[i] for i, d in enumerate(DEFAULT_SPENDING_CATEGORIES)}
    wealth_categories = {c.preset: c for c in wealth.categories(db, household.id)}
    for preset, assumption in demo.assumptions.items():
        wealth_categories[preset].expected_return = assumption.ret
        wealth_categories[preset].volatility = assumption.volatility

    fixed = {
        f.key: FixedExpense(
            household_id=household.id,
            label=f.label,
            category_id=category[f.category],
            amount=f.amount,
            frequency=f.frequency,
            day=f.day,
            first_month=f.first.first_day(),
            last_month=f.last.first_day() if f.last else None,
            skips=[FixedSkip(month=m.first_day()) for m in f.skips],
        )
        for f in demo.fixed
    }
    db.add_all(fixed.values())
    db.flush()

    db.add_all(
        SpendingLine(
            household_id=household.id,
            day=line.day,
            label=line.label,
            amount=line.amount,
            category_id=category[line.category] if line.category else None,
            fixed_expense_id=fixed[line.fixed].id if line.fixed else None,
            entered_by_id=users[line.entered_by].id,
            created_at=min(datetime.combine(line.entered_on, time(19), UTC), now),
            parts=[
                SpendingLinePart(position=i, category_id=category[p.category], amount=p.amount)
                for i, p in enumerate(line.parts)
            ],
        )
        for line in demo.lines
    )
    db.add_all(
        SpendingTarget(
            category_id=category[t.category], from_month=t.start.first_day(), amount=t.amount
        )
        for t in demo.targets
    )

    lines = {
        w.key: WealthLine(
            household_id=household.id,
            category_id=wealth_categories[w.category].id,
            name=w.name,
            owner_id=users[w.owner].id,
            visibility=w.visibility,
            closed_from=w.closed_from.first_day() if w.closed_from else None,
            regulated_type=w.regulated,
            debt_payment=w.debt_payment,
            debt_rate=w.debt_rate,
            debt_insurance=w.debt_insurance,
        )
        for w in demo.wealth_lines
    }
    db.add_all(lines.values())
    db.flush()
    db.add_all(
        WealthValue(line_id=lines[w.key].id, month=month.first_day(), amount=amount)
        for w in demo.wealth_lines
        for month, amount in w.values.items()
    )

    db.add_all(
        Goal(
            household_id=household.id,
            name=g.name,
            precaution=g.precaution,
            permanent=g.permanent,
            pleasure=g.pleasure,
            target=g.target,
            start=g.start.first_day(),
            deadline=g.deadline.first_day() if g.deadline else None,
            owner_id=users[g.owner].id,
            visibility=g.visibility,
            closed_from=g.closed_from.first_day() if g.closed_from else None,
            closed_as=ClosedAs(g.closed_as) if g.closed_as else None,
            fundings=[
                GoalFunding(line=lines[f.line], share=f.share, opening=f.opening)
                for f in g.fundings
            ],
        )
        for g in demo.goals
    )
    db.flush()
    return users[next(m.key for m in demo.members if m.owner)]
