"""The audit document for a chosen reader (§4.15): built from today's data each time, stored
nowhere (invariant §8.48).

Lines and goals go through the visibility rules (§3): a member's private line or goal never
reaches another member's document. Spending is the household's in every scope, its lines
by category only: never a line's label or note (invariant §8.47).
"""

from collections import defaultdict
from collections.abc import Callable, Sequence
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from kwak_core import audit_document as core
from kwak_core.budget import DEFAULT_BAND, Month, month_range
from kwak_core.categories import CategoryKind
from kwak_core.fixed import STEP, FixedFrequency
from kwak_core.goals import GoalStatus, Tier
from kwak_core.goals import fixed_expenses as monthly_fixed
from kwak_core.money import quantize
from kwak_core.retirement import age
from kwak_core.spending import MonthFigures
from kwak_core.users import Language
from kwak_core.visibility import Scope, Visibility, in_scope
from kwak_core.wealth import CEILINGS, WealthKind, envelope_age, line_cell, milestone
from sqlalchemy.orm import Session

from kwak_api.audit_document import schemas as out
from kwak_api.models import Household, User, WealthCategory, WealthLine
from kwak_api.services import goals, projection, retirement, spending, wealth
from kwak_api.services import spending_budget as budget

ZERO = Decimal(0)
HUNDREDTH = Decimal("0.01")
TENTH = Decimal("0.1")
SPENDING_SHOWN = 8
"""The expense categories listed before the rest is grouped."""


class Rounding:
    """The privacy's amounts: exact, or monthly amounts to €10 and wealth to €1,000."""

    def __init__(self, exact: bool) -> None:
        self.exact = exact

    def monthly(self, amount: Decimal) -> Decimal:
        return amount if self.exact else core.rounded(amount, core.MONTHLY_STEP)

    def wealth(self, amount: Decimal) -> Decimal:
        return amount if self.exact else core.rounded(amount, core.WEALTH_STEP)

    def parts[K](self, parts: dict[K, Decimal], step: Decimal) -> dict[K, Decimal]:
        """Rounded so that they still add up to their rounded total (invariant §8.48)."""
        return dict(parts) if self.exact else core.rounded_parts(parts, step)


def _period(body: out.AuditIn, db: Session, viewer: User, this_month: Month) -> core.AuditPeriod:
    if (body.start is None) != (body.end is None):
        raise core.AuditError("a period has a start and an end month, or neither")
    since = budget.first_month(db, viewer.household_id)
    if body.start is not None and body.end is not None:
        start, end = Month.parse(body.start), Month.parse(body.end)
        core.check_period(start, end, current=this_month)
        # Months before the first line are not months of zero (as on the reports).
        if since is not None and since > start:
            return core.AuditPeriod(min(since, end), end, shortened=True)
        return core.AuditPeriod(start, end, shortened=False)
    return core.default_period(current=this_month, since=since)


def _pct(ratio: Decimal | None) -> Decimal | None:
    return core.percent(ratio) if ratio is not None else None


class Labels:
    """Names, or the pseudonyms the privacy asks for (F-AUD-4)."""

    def __init__(
        self,
        privacy: core.Privacy,
        members: Sequence[User],
        lines: Sequence[WealthLine],
        positions: dict[UUID, int],
    ) -> None:
        self.privacy = privacy
        everyone = list(members)
        for line in lines:  # a former member's lines keep their owner
            if all(u.id != line.owner_id for u in everyone):
                everyone.append(line.owner)
        self.names = {u.id: u.display_name for u in everyone}
        self.letters = {u.id: core.member_letter(i) for i, u in enumerate(everyone)}
        ordered = sorted(lines, key=lambda ln: (positions.get(ln.category_id, 0), ln.name.lower()))
        self.line_numbers = core.number_within(
            [(ln.id, ln.tax_envelope or ln.category_id) for ln in ordered]
        )

    def member(self, user_id: UUID) -> out.AuditLabelOut:
        if self.privacy.named_members:
            return out.AuditLabelOut(name=self.names.get(user_id, ""))
        return out.AuditLabelOut(group="member", key=self.letters.get(user_id, "?"))

    def line(self, line: WealthLine) -> out.AuditLabelOut:
        if self.privacy.named_lines:
            return out.AuditLabelOut(name=line.name)
        number = self.line_numbers.get(line.id)
        if line.tax_envelope is not None:
            return out.AuditLabelOut(group="envelope", key=line.tax_envelope.value, number=number)
        return out.AuditLabelOut(group="category", key=line.category.name, number=number)

    def holder(self, line: WealthLine) -> out.AuditLabelOut | None:
        return None if line.visibility is Visibility.JOINT else self.member(line.owner_id)


def _spread(
    values: list[tuple[Month, Decimal]], r: Callable[[Decimal], Decimal]
) -> out.AuditSpreadOut:
    """`values` already as shown: the total is their sum, the average rounded again."""
    s = core.spread(values)
    return out.AuditSpreadOut(
        total=s.total,
        average=r(s.average),
        lowest_month=str(s.lowest[0]),
        lowest=s.lowest[1],
        highest_month=str(s.highest[0]),
        highest=s.highest[1],
    )


def _fixed(
    db: Session, viewer: User, today: date
) -> tuple[list[tuple[str, FixedFrequency, Decimal]], Decimal]:
    """The fixed expenses the goals page counts (F-GOAL-2), by category and frequency, their
    labels left out; and their exact monthly total, rounded once as on the goals page."""
    items = goals.fixed_items(db, viewer, today)
    by: dict[tuple[str, FixedFrequency], Decimal] = defaultdict(Decimal)
    for item in items:
        by[item.category, item.frequency] += item.amount / STEP[item.frequency]
    total = monthly_fixed((i.frequency, -i.amount) for i in items)
    return [(c, f, m) for (c, f), m in sorted(by.items(), key=lambda kv: -kv[1])], total


def build(db: Session, viewer: User, body: out.AuditIn, now: datetime) -> out.AuditOut:
    today = now.date()
    this_month = Month.of(today)
    household = db.get_one(Household, viewer.household_id)
    period = _period(body, db, viewer, this_month)
    months = month_range(period.start, period.end)
    privacy = (
        core.Privacy(**body.privacy.model_dump())
        if body.privacy is not None
        else core.default_privacy(body.audience)
    )
    if body.withholding is not None:
        core.check_withholding(body.withholding)
    language = body.language or viewer.language or Language.EN
    r = Rounding(privacy.exact_amounts)
    scope = body.scope

    # The members, the lines and the labels
    roster = retirement.members(db, viewer.household_id)
    # The viewer first, then by joining order: never the names' alphabetical order, which an
    # anonymised document would hint at.
    roster.sort(key=lambda ur: (ur[0].id != viewer.id, ur[0].created_at, str(ur[0].id)))
    users = [u for u, _ in roster]
    visible = wealth.visible_lines(db, viewer)
    values = goals.line_values(db, {ln.id for ln in visible})
    scoped = [
        ln
        for ln in visible
        if in_scope(scope, owner_id=ln.owner_id, visibility=ln.visibility, viewer_id=viewer.id)
    ]
    rows = wealth.categories(db, viewer.household_id)
    positions = {c.id: c.position for c in rows}
    # The loans running today, values carried forward: the ones a bank counts. A debt
    # without a value yet is still listed, as left out.
    running_debts = [
        (ln, owed)
        for ln, owed in projection.debts(db, viewer, this_month)
        if owed is None or owed > 0
    ]
    labels = Labels(
        privacy,
        users,
        list({ln.id: ln for ln in [*scoped, *(d for d, _ in running_debts)]}.values()),
        positions,
    )
    in_household = [u for u in users if scope is not Scope.MINE or u.id == viewer.id]
    members = [
        out.AuditMemberOut(
            label=labels.member(u.id),
            age=age(Month.of(row.birth), this_month) if row is not None else None,
        )
        for u, row in roster
        if u in in_household
    ]

    money, totals_by_category, figures = _money(db, viewer, months, today, household, r)
    fixed_exact = _fixed(db, viewer, today)[1]

    wealth_out, liquid = _wealth(scoped, values, rows, period, labels, r)

    # The debt ratio (F-AUD-2)
    categories = spending.categories(db, viewer.household_id)
    income_categories = {c.id: c for c in categories if c.kind is CategoryKind.INCOME}
    counted = (
        {c for c in body.counted if c in income_categories}
        if body.counted is not None
        else core.counted_by_default({c.id: c.preset for c in income_categories.values()})
    )
    ratio_income = core.ratio_income(totals_by_category, counted=counted, months=len(months))
    with_payment = [
        (ln, owed) for ln, owed in running_debts if ln.debt_payment is not None and owed is not None
    ]
    payments = sum(((ln.debt_payment or ZERO) + ln.debt_insurance for ln, _ in with_payment), ZERO)
    ratio = core.debt_ratio(payments, ratio_income)
    # The withholding rate is the banker's (F-AUD-1).
    w = body.withholding if body.audience is core.Audience.BANKER else None
    before = core.debt_ratio(payments, core.before_tax(ratio_income, w)) if w is not None else None
    ratio_out = out.AuditRatioOut(
        income=r.monthly(ratio_income),
        counted=[c.name for c in income_categories.values() if c.id in counted],
        left_out=[c.name for c in income_categories.values() if c.id not in counted],
        payments=r.monthly(payments),
        ratio=_pct(ratio),
        above_ceiling=ratio is not None and ratio > core.DEBT_CEILING,
        withholding=_pct(w),
        before_tax_ratio=_pct(before),
        before_tax_above=before is not None and before > core.DEBT_CEILING,
        remaining=r.monthly(ratio_income) - r.monthly(payments),
        debts=[_debt(ln, owed, values, this_month, labels, r) for ln, owed in with_payment],
        left_out_debts=[
            labels.line(ln) for ln, owed in running_debts if ln.debt_payment is None or owed is None
        ],
    )

    goals_out, precaution = _goals(db, viewer, scope, this_month, labels, privacy, fixed_exact, r)

    retirement_out = [
        out.AuditRetirementOut(
            member=labels.member(u.id),
            retirement=str(Month.of(row.retirement)),
            pension_month=str(Month.of(row.pension_month)),
            pension=r.monthly(row.pension),
        )
        for u, row in roster
        if row is not None and u in in_household
    ]
    used = {ln.category_id for ln in scoped}
    assumptions = [
        out.AuditAssumptionOut(
            category=c.name,
            expected_return=core.percent(projection.assumption(c).ret),
            volatility=core.percent(projection.assumption(c).volatility),
        )
        for c in rows
        if c.kind is WealthKind.ASSET and c.id in used
    ]

    project_out = None
    if body.project is not None and body.audience is core.Audience.BANKER:
        total_saved = sum((f.saved for f in figures), ZERO)
        project_out = _project(
            body.project,
            ratio_income=ratio_income,
            payments=payments,
            withholding=w,
            liquid=liquid,
            average_saved=quantize(total_saved / len(months)),
            capacity=goals_capacity(db, viewer, household, this_month),
            precaution=precaution,
            r=r,
        )

    return out.AuditOut(
        audience=body.audience,
        scope=scope,
        language=language,
        privacy=out.AuditPrivacyIn(**privacy.__dict__),
        generated_at=now,
        period=out.AuditPeriodOut(
            start=str(period.start),
            end=str(period.end),
            months=len(months),
            shortened=period.shortened,
        ),
        household=out.AuditHouseholdOut(
            name=household.name if privacy.named_members else None, members=members
        ),
        money=money,
        wealth=wealth_out,
        ratio=ratio_out,
        goals=goals_out,
        retirement=retirement_out,
        assumptions=assumptions,
        project=project_out,
    )


def goals_capacity(db: Session, viewer: User, household: Household, this_month: Month) -> Decimal:
    """The goals' capacity (F-GOAL-6): set by hand, else measured."""
    if household.goal_capacity is not None:
        return household.goal_capacity
    return goals.capacity(db, viewer, this_month)


def _money(
    db: Session,
    viewer: User,
    months: list[Month],
    today: date,
    household: Household,
    r: Rounding,
) -> tuple[out.AuditMoneyOut, dict[UUID, Decimal], list[MonthFigures]]:
    household_id = viewer.household_id
    categories = spending.categories(db, household_id)
    kinds = {c.id: c.kind for c in categories}
    names = {c.id: c.name for c in categories}
    by_month = budget.figures_by_month(db, household_id, months, kinds)
    figures = [by_month[m] for m in months]
    amounts = budget.spending_by_month(db, household_id, months[0], months[-1])
    totals: dict[UUID, Decimal] = defaultdict(Decimal)
    for (category, _), amount in amounts.items():
        if category is not None:
            totals[category] += amount

    this_month = Month.of(today)

    def shown(pick: Callable[[MonthFigures], Decimal]) -> dict[Month, Decimal]:
        """Each month as shown: rounded so they add up to the rounded total (§8.48)."""
        return r.parts({m: pick(by_month[m]) for m in months}, core.MONTHLY_STEP)

    inc, sp, sv = shown(lambda f: f.income), shown(lambda f: f.spent), shown(lambda f: f.saved)
    rounded_figures = [MonthFigures(inc[m], sp[m], sv[m]) for m in months]

    def series(pick: Callable[[MonthFigures], Decimal]) -> list[tuple[Month, Decimal]]:
        return [(m, pick(f)) for m, f in zip(months, rounded_figures, strict=True)]

    income = sum((f.income for f in figures), ZERO)
    spent = sum((f.spent for f in figures), ZERO)
    saved = sum((f.saved for f in figures), ZERO)

    income_parts = r.parts(
        {c: a for c, a in totals.items() if kinds.get(c) is CategoryKind.INCOME},
        core.MONTHLY_STEP,
    )
    top, _ = core.largest_first(
        {c: a for c, a in totals.items() if kinds.get(c) is CategoryKind.EXPENSE},
        limit=SPENDING_SHOWN,
    )
    # The rest holds every other category, a net refund (below zero) included: the parts add
    # up to what was spent.
    rest = spent - sum((a for _, a in top), ZERO)
    rest_key = None
    spending_parts = r.parts({**dict(top), rest_key: rest}, core.MONTHLY_STEP)
    fixed, fixed_total = _fixed(db, viewer, today)
    fixed_parts = (
        {(c, f): quantize(m) for c, f, m in fixed}
        if r.exact
        else core.rounded_parts({(c, f): m for c, f, m in fixed}, core.MONTHLY_STEP)
    )
    cap_months = goals.capacity_months(db, household_id, this_month)

    def month_out(m: Month, f: MonthFigures) -> out.AuditMonthOut:
        return out.AuditMonthOut(
            month=str(m), income=f.income, spent=f.spent, saved=f.saved, rest=f.rest
        )

    def year_out(y: core.YearTotals) -> out.AuditYearOut:
        f = y.figures
        return out.AuditYearOut(
            year=y.year,
            months=y.months,
            partial=y.partial,
            income=f.income,
            spent=f.spent,
            saved=f.saved,
            rest=f.rest,
        )

    money = out.AuditMoneyOut(
        months=[month_out(m, f) for m, f in zip(months, rounded_figures, strict=True)],
        income=_spread(series(lambda f: f.income), r.monthly),
        spent=_spread(series(lambda f: f.spent), r.monthly),
        saved=_spread(series(lambda f: f.saved), r.monthly),
        rest=_spread(series(lambda f: f.rest), r.monthly),
        no_income=[str(m) for m in months if by_month[m].income == 0],
        income_by_category=[
            out.AuditNamedAmountOut(name=names[c], amount=a)
            for c, a in sorted(income_parts.items(), key=lambda kv: -totals[kv[0]])
        ],
        spending_by_category=[
            out.AuditNamedAmountOut(name=names[c], amount=spending_parts[c]) for c, _ in top
        ],
        spending_rest=spending_parts[rest_key],
        fixed=[
            out.AuditFixedOut(category=c, frequency=f, monthly=fixed_parts[c, f])
            for c, f, _ in fixed
        ],
        fixed_monthly=r.monthly(fixed_total),
        savings_rate=_pct((income - spent) / income) if income > 0 else None,
        saved_share=_pct(saved / income) if income > 0 else None,
        capacity=r.monthly(goals_capacity(db, viewer, household, this_month)),
        capacity_start=str(cap_months[0]) if cap_months else None,
        capacity_end=str(cap_months[-1]) if cap_months else None,
        capacity_set=household.goal_capacity is not None,
        years=[year_out(y) for y in core.by_year(list(zip(months, rounded_figures, strict=True)))],
    )
    return money, dict(totals), figures


def _value_at(
    line: WealthLine, values: dict[UUID, dict[Month, Decimal]], month: Month
) -> tuple[Decimal, bool] | None:
    closed = Month.of(line.closed_from) if line.closed_from else None
    cell = line_cell(values.get(line.id, {}), month, closed_from=closed)
    return (cell.amount, cell.carried) if cell is not None else None


def _entered_month(values: dict[Month, Decimal], month: Month) -> Month:
    """The month a carried value was entered: a debt's end counts from it."""
    earlier = [m for m in values if m <= month]
    return max(earlier) if earlier else month


def _debt(
    line: WealthLine,
    owed: Decimal,
    values: dict[UUID, dict[Month, Decimal]],
    end: Month,
    labels: Labels,
    r: Rounding,
    shown: Decimal | None = None,
) -> out.AuditDebtOut:
    terms = projection.debt_terms(line)
    ends = core.debt_end(owed, terms, last=_entered_month(values.get(line.id, {}), end))
    if ends is not None and ends <= end:
        ends = None  # a stale value says it is repaid by now: the end is not known
    return out.AuditDebtOut(
        label=labels.line(line),
        owed=shown if shown is not None else r.wealth(owed),
        payment=r.monthly(line.debt_payment) if line.debt_payment is not None else None,
        insurance=r.monthly(line.debt_insurance),
        rate=(line.debt_rate * 100).quantize(HUNDREDTH, rounding=ROUND_HALF_UP),
        ends=str(ends) if ends else None,
    )


def _wealth(
    scoped: list[WealthLine],
    values: dict[UUID, dict[Month, Decimal]],
    rows: list[WealthCategory],
    period: core.AuditPeriod,
    labels: Labels,
    r: Rounding,
) -> tuple[out.AuditWealthOut, Decimal]:
    """The wealth at the end month (F-WLT-3), in the document's scope; returns the liquid
    wealth, exact, for the project."""
    end, start = period.end, period.start
    held = {ln.id: c for ln in scoped if (c := _value_at(ln, values, end)) is not None}
    kinds = {c.id: c.kind for c in rows}
    by_id = {ln.id: ln for ln in scoped}

    def split(at: dict[UUID, Decimal]) -> tuple[dict[UUID, Decimal], dict[UUID, Decimal]]:
        assets = {i: v for i, v in at.items() if kinds[by_id[i].category_id] is WealthKind.ASSET}
        debts = {i: v for i, v in at.items() if i not in assets}
        return assets, debts

    def rounded(at: dict[UUID, Decimal]) -> tuple[dict[UUID, Decimal], Decimal, Decimal]:
        assets, debts = split(at)
        if r.exact:
            parts = {**assets, **debts}
            return parts, sum(assets.values(), ZERO), sum(debts.values(), ZERO)
        w = core.rounded_wealth(assets, debts, core.WEALTH_STEP)
        return {**w.assets, **w.debts}, w.gross, w.owed

    shown, gross, owed = rounded({i: v for i, (v, _) in held.items()})
    opening = start.previous()  # the position the period opens with
    start_values = {
        ln.id: c[0] for ln in scoped if (c := _value_at(ln, values, opening)) is not None
    }
    _, start_gross, start_owed = rounded(start_values)

    illiquid_categories = {c.id for c in rows if projection.risk(c).illiquid}
    exact_liquid = sum(
        (
            v
            for i, (v, _) in held.items()
            if kinds[by_id[i].category_id] is WealthKind.ASSET
            and by_id[i].category_id not in illiquid_categories
        ),
        ZERO,
    )
    liquid = sum(
        (
            v
            for i, v in shown.items()
            if kinds[by_id[i].category_id] is WealthKind.ASSET
            and by_id[i].category_id not in illiquid_categories
        ),
        ZERO,
    )
    category_values: dict[UUID, Decimal] = defaultdict(Decimal)
    for i, v in shown.items():
        category_values[by_id[i].category_id] += v
    holders: dict[UUID | None, Decimal] = defaultdict(Decimal)
    for i, v in shown.items():
        line = by_id[i]
        key = None if line.visibility is Visibility.JOINT else line.owner_id
        holders[key] += -v if kinds[line.category_id] is WealthKind.DEBT else v

    ordered = sorted(
        (by_id[i] for i in shown),
        key=lambda ln: (ln.category.position, ln.name.lower()),
    )
    lines_out = []
    for line in ordered:
        kind = kinds[line.category_id]
        opened = line.opening_year
        lines_out.append(
            out.AuditWealthLineOut(
                label=labels.line(line),
                category=line.category.name,
                kind=kind,
                holder=labels.holder(line),
                value=shown[line.id],
                carried=held[line.id][1],
                envelope=line.tax_envelope,
                opening_year=opened,
                age=envelope_age(opened, current_year=end.year) if opened else None,
                milestone=(
                    milestone(line.tax_envelope, opened, current_year=end.year)
                    if line.tax_envelope is not None and opened
                    else None
                ),
                regulated=line.regulated_type,
                ceiling=CEILINGS[line.regulated_type] if line.regulated_type else None,
            )
        )
    debt_lines = [
        _debt(line, held[line.id][0], values, end, labels, r, shown=shown[line.id])
        for line in ordered
        if kinds[line.category_id] is WealthKind.DEBT and held[line.id][0] > 0
    ]
    return (
        out.AuditWealthOut(
            month=str(end),
            categories=[
                out.AuditWealthCategoryOut(
                    name=c.name,
                    kind=c.kind,
                    colour=c.colour,
                    value=category_values[c.id],
                    share=_pct(category_values[c.id] / gross)
                    if c.kind is WealthKind.ASSET and gross > 0
                    else None,
                    liquid=c.kind is WealthKind.ASSET and c.id not in illiquid_categories,
                )
                for c in rows
                if c.id in category_values
            ],
            lines=lines_out,
            gross=gross,
            debts=owed,
            net=gross - owed,
            liquid=liquid,
            illiquid=gross - liquid,
            start_month=str(opening),
            start_net=start_gross - start_owed,
            change=(gross - owed) - (start_gross - start_owed),
            holders=[
                out.AuditHolderOut(holder=labels.member(h) if h is not None else None, net=v)
                for h, v in holders.items()
            ],
            debt_lines=debt_lines,
            carried=any(c for _, c in held.values()),
        ),
        exact_liquid,
    )


def _goals(
    db: Session,
    viewer: User,
    scope: Scope,
    this_month: Month,
    labels: Labels,
    privacy: core.Privacy,
    fixed_monthly: Decimal,
    r: Rounding,
) -> tuple[out.AuditGoalsOut, Decimal]:
    """The open goals in scope, tracked to this month (F-GOAL-1), without archiving any: the
    document changes nothing."""
    kept = [
        g
        for g in goals.visible_goals(db, viewer)
        if in_scope(scope, owner_id=g.owner_id, visibility=g.visibility, viewer_id=viewer.id)
        and (g.closed_from is None or Month.of(g.closed_from) > this_month)
    ]
    env = goals.envelopes(db, viewer.household_id, this_month)
    tracked = [
        (g, goals.tier(g, this_month), goals.track(g, env, this_month, DEFAULT_BAND)) for g in kept
    ]
    order = list(Tier)
    tracked.sort(
        key=lambda gt: (
            order.index(gt[1]),
            gt[0].deadline or this_month.first_day(),
            gt[0].name.lower(),
        )
    )
    numbers = core.number_within([(g.id, t) for g, t, _ in tracked])
    precaution = sum((g.target for g, _, _ in tracked if g.precaution and g.fill_first), ZERO)
    months = core.months_of(precaution, fixed_monthly)
    return (
        out.AuditGoalsOut(
            goals=[
                out.AuditGoalOut(
                    label=out.AuditLabelOut(name=g.name)
                    if privacy.named_members
                    else out.AuditLabelOut(group="tier", key=t.value, number=numbers[g.id]),
                    tier=t,
                    target=r.wealth(g.target),
                    deadline=str(Month.of(g.deadline)) if g.deadline else None,
                    value=r.wealth(tr.value),
                    status=tr.status
                    if isinstance(tr.status, GoalStatus)
                    else GoalStatus(tr.status),
                    pro_type=g.pro_type,
                    cost=r.wealth(g.cost) if g.cost is not None else None,
                    aids=[
                        out.AuditAidOut(
                            source=a.source, amount=r.wealth(a.amount), received=a.received
                        )
                        for a in g.aids
                    ],
                )
                for g, t, tr in tracked
            ],
            precaution=r.wealth(precaution),
            precaution_months=(
                months.quantize(TENTH, rounding=ROUND_HALF_UP) if months is not None else None
            ),
        ),
        precaution,
    )


def _project(
    p: out.AuditProjectIn,
    *,
    ratio_income: Decimal,
    payments: Decimal,
    withholding: Decimal | None,
    liquid: Decimal,
    average_saved: Decimal,
    capacity: Decimal,
    precaution: Decimal,
    r: Rounding,
) -> out.AuditProjectOut:
    """F-AUD-5: the running loans go on next to the new one."""
    estimated = p.notary_fees is None
    project = core.Project(
        price=p.price,
        notary_fees=core.notary_fees(p.price, p.property_age)
        if p.notary_fees is None
        else p.notary_fees,
        agency_fees=p.agency_fees,
        guarantee_fees=p.guarantee_fees,
        down_payment=p.down_payment,
        loan=p.loan,
        years=p.years,
        rate=p.rate,
        insurance=p.insurance,
        rent=p.rent,
        rent_stops=p.rent_stops,
    )
    core.check_project(project)
    f = core.project_figures(
        project, ratio_income=ratio_income, running_payments=payments, liquid=liquid
    )
    after = payments + f.payment + project.insurance
    before = (
        core.debt_ratio(after, core.before_tax(ratio_income, withholding))
        if withholding is not None
        else None
    )
    return out.AuditProjectOut(
        price=r.wealth(project.price),
        notary_fees=r.wealth(project.notary_fees),
        notary_estimated=estimated,
        agency_fees=r.wealth(project.agency_fees),
        guarantee_fees=r.wealth(project.guarantee_fees),
        down_payment=r.wealth(project.down_payment),
        cost=r.wealth(f.cost),
        loan=r.wealth(f.loan),
        years=project.years,
        duration=core.duration_check(project.years),
        rate=(project.rate * 100).quantize(HUNDREDTH),
        payment=r.monthly(f.payment),
        insurance=r.monthly(project.insurance),
        ratio_after=_pct(f.ratio_after),
        above_ceiling=f.above_ceiling,
        before_tax_ratio_after=_pct(before),
        before_tax_above=before is not None and before > core.DEBT_CEILING,
        remaining_after_housing=r.monthly(f.remaining_after_housing),
        rent=r.monthly(project.rent),
        rent_stops=project.rent_stops,
        housing_change=r.monthly(f.housing_change),
        average_saved=r.monthly(average_saved),
        capacity=r.monthly(capacity),
        down_share=core.percent(f.down_share),
        liquid_left=r.wealth(f.liquid_left),
        precaution=r.wealth(precaution),
    )
