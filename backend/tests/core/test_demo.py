"""The demo household (spec §4.9 F-ADM-5, invariant §8.40): fictitious, seeded, dated from the
day it is made, and true to every rule the real data follows."""

from collections import Counter, defaultdict
from datetime import date, timedelta
from decimal import Decimal
from uuid import NAMESPACE_URL, UUID, uuid5

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from kwak_core.budget import Month, month_range
from kwak_core.categories import DEFAULT_SPENDING_CATEGORIES, CategoryKind
from kwak_core.demo import HISTORY_MONTHS, Demo, generate
from kwak_core.fixed import FixedExpense, FixedStatus, LineRef, occurrences
from kwak_core.goals import (
    Envelope,
    FundedGoal,
    GoalStatus,
    Line,
    Tier,
    check_funding_line,
    check_goal,
    check_line_shares,
    envelopes,
    tier_of,
    track,
)
from kwak_core.money import quantize
from kwak_core.retirement import Member, check_member
from kwak_core.spending import check_line_kinds
from kwak_core.users import Language
from kwak_core.visibility import Visibility
from kwak_core.wealth import DEFAULT_WEALTH_CATEGORIES, WealthKind, check_regulated, check_value

TODAY = date(2026, 10, 25)
KINDS = {c.names.en: c.kind for c in DEFAULT_SPENDING_CATEGORIES}
WEALTH_KINDS = {c.colour: c.kind for c in DEFAULT_WEALTH_CATEGORIES}

days = st.dates(date(2026, 1, 1), date(2040, 12, 31))
languages = st.sampled_from(Language)


def uid(key: str) -> UUID:
    return uuid5(NAMESPACE_URL, key)


def check_lines(demo: Demo) -> None:
    for line in demo.lines:
        assert demo.start.first_day() <= line.day <= demo.today
        assert line.day <= line.entered_on <= demo.today
        assert line.amount != 0
        assert line.amount == quantize(line.amount)
        assert 1 <= len(line.label) <= 100
        if line.parts:
            assert line.category is None
            assert len(line.parts) >= 2
            assert sum(p.amount for p in line.parts) == line.amount
            assert all((p.amount < 0) == (line.amount < 0) and p.amount != 0 for p in line.parts)
            check_line_kinds(line.amount, [KINDS[p.category] for p in line.parts])
        else:
            assert line.category is not None
            check_line_kinds(line.amount, [KINDS[line.category]])
        assert line.entered_by in {m.key for m in demo.members}


def check_fixed(demo: Demo) -> None:
    items = {
        f.key: FixedExpense(
            uid(f.key), f.label, uid(f.category), f.amount, f.frequency, f.day, f.first, f.last
        )
        for f in demo.fixed
    }
    for f in demo.fixed:
        assert KINDS[f.category] is not CategoryKind.INCOME
        assert all(f.first <= s <= demo.this_month for s in f.skips)
    for month in month_range(demo.start, demo.this_month):
        refs = [
            LineRef(
                uid(f"line{i}"),
                ln.label,
                uid(ln.category) if ln.category else None,
                ln.day,
                uid(ln.fixed) if ln.fixed else None,
            )
            for i, ln in enumerate(demo.lines)
            if Month.of(ln.day) == month
        ]
        skipped = {uid(f.key) for f in demo.fixed if month in f.skips}
        found = occurrences(list(items.values()), month, refs, skipped)
        waiting = [o for o in found if o.status is FixedStatus.TO_CONFIRM]
        if month < demo.this_month:
            assert waiting == [], f"{month}: every past occurrence is confirmed or skipped"
        else:
            assert any(o.due <= demo.today for o in waiting), "one is late this month"


def check_wealth(demo: Demo) -> None:
    keys = {w.key for w in demo.wealth_lines}
    assert len(keys) == len(demo.wealth_lines)
    for w in demo.wealth_lines:
        assert w.category in WEALTH_KINDS
        check_regulated(w.regulated, preset=w.category, visibility=w.visibility)
        assert w.values, w.key
        for month, amount in w.values.items():
            check_value(amount)
            assert demo.wealth_start <= month <= demo.this_month
            assert w.closed_from is None or month < w.closed_from
        if WEALTH_KINDS[w.category] is WealthKind.DEBT:
            assert w.debt_payment is not None
            assert w.debt_payment > 0


def check_goals(demo: Demo) -> None:
    lines = {w.key: w for w in demo.wealth_lines}
    owners = {m.key: uid(m.key) for m in demo.members}
    for g in demo.goals:
        check_goal(
            g.target,
            precaution=g.precaution,
            permanent=g.permanent,
            pleasure=g.pleasure,
            deadline=g.deadline,
            start=g.start,
            this_month=g.start if g.closed_from else demo.this_month,
        )
        for f in g.fundings:
            w = lines[f.line]
            check_funding_line(
                goal_owner_id=owners[g.owner],
                goal_visibility=g.visibility,
                line_owner_id=owners[w.owner],
                line_visibility=w.visibility,
                line_kind=WEALTH_KINDS[w.category],
            )
    for month in month_range(demo.start, demo.this_month):
        shares: dict[str, list[int]] = {}
        for g in demo.goals:
            if g.start <= month and (g.closed_from is None or month < g.closed_from):
                for f in g.fundings:
                    shares.setdefault(f.line, []).append(f.share)
        for line_shares in shares.values():
            check_line_shares(line_shares)


def statuses(demo: Demo) -> dict[str, GoalStatus]:
    """Each open goal's status this month, as the goals page computes it."""
    owners = {m.key: uid(m.key) for m in demo.members}
    lines = {
        uid(w.key): Line(dict(w.values), w.closed_from)
        for w in demo.wealth_lines
        if WEALTH_KINDS[w.category] is WealthKind.ASSET
    }
    funded = [
        FundedGoal(
            uid(g.key),
            g.target,
            g.start,
            [Envelope(uid(f.line), f.share, f.opening) for f in g.fundings],
            deadline=g.deadline,
            precaution=g.precaution,
            closed_from=g.closed_from,
            pleasure=g.pleasure,
            owner=owners[g.owner],
            visibility=g.visibility,
        )
        for g in demo.goals
    ]
    months = month_range(min(g.start for g in demo.goals), demo.this_month)
    env = envelopes(lines, funded, months)
    out = {}
    for g in demo.goals:
        if g.closed_from is not None:
            continue
        values = env.value(uid(g.key))[months.index(g.start) :]
        locked = g.pleasure and not env.gates(uid(g.key))[-1].unlocked
        out[g.key] = track(
            g.target,
            g.start,
            g.deadline,
            values,
            this_month=demo.this_month,
            precaution=g.precaution,
            locked=locked,
        ).status
    return out


# The same seed and day, the same demo


def test_the_same_day_gives_the_same_demo() -> None:
    assert generate(TODAY, Language.FR) == generate(TODAY, Language.FR)


def test_the_history_ends_today_and_goes_back_three_years() -> None:
    demo = generate(TODAY, Language.EN)
    assert demo.this_month == Month(2026, 10)
    assert demo.start == Month(2023, 10)
    assert len(month_range(demo.start, demo.this_month)) == HISTORY_MONTHS + 1
    assert max(ln.day for ln in demo.lines) <= TODAY
    assert {Month.of(ln.day) for ln in demo.lines} == set(month_range(demo.start, demo.this_month))


def test_the_labels_follow_the_language() -> None:
    en = {ln.label for ln in generate(TODAY, Language.EN).lines}
    fr = {ln.label for ln in generate(TODAY, Language.FR).lines}
    assert "Pharmacy" in en
    assert "Pharmacie" in fr


# Every rule the real data follows


def test_the_lines_follow_the_spending_rules() -> None:
    check_lines(generate(TODAY, Language.FR))


def test_every_default_category_has_lines_and_some_lines_are_split() -> None:
    demo = generate(TODAY, Language.FR)
    used = {ln.category for ln in demo.lines if ln.category} | {
        p.category for ln in demo.lines for p in ln.parts
    }
    assert used == set(KINDS)
    assert sum(1 for ln in demo.lines if ln.parts) >= 12


def test_a_savings_withdrawal_and_one_off_months() -> None:
    demo = generate(TODAY, Language.FR)
    assert any(ln.category == "Savings" and ln.amount > 0 for ln in demo.lines)
    spent: defaultdict[Month, Decimal] = defaultdict(Decimal)
    for ln in demo.lines:
        if ln.category and KINDS[ln.category] is CategoryKind.EXPENSE:
            spent[Month.of(ln.day)] -= ln.amount
    complete = [m for m in month_range(demo.start, demo.this_month.previous())]
    usual = sorted(spent[m] for m in complete)[len(complete) // 2]
    assert sum(1 for m in complete if spent[m] > usual * Decimal("1.3")) >= 3


def test_both_members_enter_lines() -> None:
    demo = generate(TODAY, Language.FR)
    assert {ln.entered_by for ln in demo.lines} == {m.key for m in demo.members}


def test_the_fixed_expenses_are_confirmed_or_skipped_but_one_this_month() -> None:
    demo = generate(TODAY, Language.FR)
    check_fixed(demo)
    assert any(f.skips for f in demo.fixed)
    assert any(f.last is not None for f in demo.fixed)


def test_the_targets_change_over_time() -> None:
    demo = generate(TODAY, Language.FR)
    for t in demo.targets:
        assert KINDS[t.category] is not CategoryKind.INCOME
        assert t.start.first_day() <= demo.today
        assert t.amount is None or t.amount >= 0
    starts = Counter(t.category for t in demo.targets)
    assert sum(1 for n in starts.values() if n > 1) >= 3
    assert "Savings" in starts


def test_the_wealth_follows_the_matrix_rules() -> None:
    demo = generate(TODAY, Language.FR)
    check_wealth(demo)
    assert demo.wealth_start == demo.start
    visibilities = {(w.owner, w.visibility) for w in demo.wealth_lines}
    for member in demo.members:
        assert (member.key, Visibility.PRIVATE) in visibilities
        assert (member.key, Visibility.SHARED) in visibilities
    assert any(w.visibility is Visibility.JOINT for w in demo.wealth_lines)
    assert any(w.regulated for w in demo.wealth_lines)
    assert any(w.closed_from for w in demo.wealth_lines)
    assert {"savings", "current", "stocks", "bonds", "real-estate", "debts"} <= {
        w.category for w in demo.wealth_lines
    }
    debts = [w for w in demo.wealth_lines if w.category == "debts"]
    assert len(debts) >= 2


def test_a_month_left_to_update_shows_values_carried() -> None:
    demo = generate(TODAY, Language.FR)
    open_lines = [w for w in demo.wealth_lines if w.closed_from is None]
    carried = [w for w in open_lines if demo.this_month not in w.values]
    assert 0 < len(carried) < len(open_lines)


def test_the_goals_follow_the_goal_rules() -> None:
    check_goals(generate(TODAY, Language.FR))


def test_the_pyramid_has_every_tier_and_the_statuses_to_show() -> None:
    demo = generate(TODAY, Language.FR)
    tiers = {
        tier_of(
            g.deadline, this_month=demo.this_month, precaution=g.precaution, pleasure=g.pleasure
        )
        for g in demo.goals
        if g.closed_from is None
    }
    assert tiers == set(Tier)
    assert any(g.closed_from is not None for g in demo.goals)
    found = Counter(statuses(demo).values())
    assert found[GoalStatus.REACHED] >= 1
    assert found[GoalStatus.BEHIND] >= 1
    assert found[GoalStatus.AHEAD] >= 1
    assert found[GoalStatus.LOCKED] == 1
    pleasure = [g.key for g in demo.goals if g.pleasure]
    assert sum(statuses(demo)[k] is not GoalStatus.LOCKED for k in pleasure) == 1


def test_the_members_retirement_is_valid_and_matches_their_salary() -> None:
    demo = generate(TODAY, Language.FR)
    assert len(demo.members) == 2
    assert sum(m.owner for m in demo.members) == 1
    for m in demo.members:
        member = Member(uid(m.key), m.birth, m.retirement, m.earnings, m.pension_month, m.pension)
        check_member(member)
        assert m.retirement > demo.this_month
        salaries = [ln for ln in demo.lines if ln.category == "Salaries" and ln.entered_by == m.key]
        assert salaries[-1].amount == m.earnings


def test_the_assumptions_name_wealth_categories() -> None:
    demo = generate(TODAY, Language.FR)
    assert demo.assumptions
    assert set(demo.assumptions) <= set(WEALTH_KINDS)


# Any day, either language


@settings(max_examples=12, deadline=None)
@given(days, languages)
def test_any_day_gives_a_demo_true_to_the_rules(today: date, language: Language) -> None:
    demo = generate(today, language)
    assert demo.today == today
    check_lines(demo)
    check_fixed(demo)
    check_wealth(demo)
    check_goals(demo)


@pytest.mark.parametrize("today", [date(2026, 1, 1), date(2027, 6, 30), date(2031, 12, 31)])
def test_the_statuses_hold_whatever_the_day(today: date) -> None:
    found = statuses(generate(today, Language.EN))
    assert {GoalStatus.REACHED, GoalStatus.BEHIND, GoalStatus.AHEAD, GoalStatus.LOCKED} <= set(
        found.values()
    )


def test_the_first_of_a_month_still_has_lines() -> None:
    demo = generate(date(2027, 3, 1), Language.EN)
    assert any(ln.day == demo.today for ln in demo.lines)
    assert demo.today - timedelta(days=1) >= demo.start.first_day()
