"""Categorisation rules: CRUD, application on import and entry, re-application (F-CAT-2)."""

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from kwak_core.rules import Rule, RuleSet, validate_rule
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from kwak_api.models import CategorizationRule, Category, Transaction, User
from kwak_api.services.accounts import visible_accounts


@dataclass
class Conditions:
    label_contains: str | None
    amount_min: Decimal | None
    amount_max: Decimal | None
    account_id: UUID | None


def _core(rule: CategorizationRule) -> Rule:
    return Rule(
        id=rule.id,
        category_id=rule.category_id,
        kind=rule.category.kind,
        priority=rule.priority,
        label_contains=rule.label_contains,
        amount_min=rule.amount_min,
        amount_max=rule.amount_max,
        account_id=rule.account_id,
    )


def _draft(category: Category, conditions: Conditions) -> Rule:
    label = conditions.label_contains.strip() if conditions.label_contains else None
    rule = Rule(
        category_id=category.id,
        kind=category.kind,
        priority=0,
        label_contains=label or None,
        amount_min=conditions.amount_min,
        amount_max=conditions.amount_max,
        account_id=conditions.account_id,
    )
    validate_rule(rule)
    return rule


def list_rules(db: Session, household_id: UUID) -> list[CategorizationRule]:
    return list(
        db.scalars(
            select(CategorizationRule)
            .where(CategorizationRule.household_id == household_id)
            .options(joinedload(CategorizationRule.category))
            .order_by(CategorizationRule.priority, CategorizationRule.id)
        )
    )


def rule_set(db: Session, household_id: UUID) -> RuleSet:
    return RuleSet(_core(r) for r in list_rules(db, household_id))


def create(
    db: Session, household_id: UUID, category: Category, conditions: Conditions
) -> CategorizationRule:
    draft = _draft(category, conditions)
    last = db.scalar(
        select(func.max(CategorizationRule.priority)).where(
            CategorizationRule.household_id == household_id
        )
    )
    rule = CategorizationRule(
        household_id=household_id,
        category=category,
        priority=(last or 0) + 10,
        label_contains=draft.label_contains,
        amount_min=draft.amount_min,
        amount_max=draft.amount_max,
        account_id=draft.account_id,
    )
    db.add(rule)
    db.flush()
    return rule


def update(
    db: Session,
    rule: CategorizationRule,
    category: Category,
    conditions: Conditions,
    priority: int,
) -> None:
    draft = _draft(category, conditions)
    rule.category = category
    rule.priority = priority
    rule.label_contains = draft.label_contains
    rule.amount_min = draft.amount_min
    rule.amount_max = draft.amount_max
    rule.account_id = draft.account_id
    db.flush()


def categorise_new(db: Session, household_id: UUID, transactions: list[Transaction]) -> None:
    """Categorise fresh transactions (an import, a manual entry) that have no category yet."""
    rules = rule_set(db, household_id)
    for t in transactions:
        if t.category_id is None:
            t.category_id = rules.category_for(
                label=t.label_raw, amount=t.amount, account_id=t.account_id
            )


def _visible_transactions(db: Session, viewer: User) -> list[Transaction]:
    accounts = [a.id for a in visible_accounts(db, viewer, include_closed=True)]
    return list(db.scalars(select(Transaction).where(Transaction.account_id.in_(accounts))))


def apply(db: Session, viewer: User, *, only_uncategorised: bool) -> int:
    """Re-run the rules on the viewer's transactions; returns how many changed category.

    A transaction no rule matches keeps its category: rules add, they never erase.
    """
    rules = rule_set(db, viewer.household_id)
    changed = 0
    for t in _visible_transactions(db, viewer):
        if t.transfer_group_id is not None or (only_uncategorised and t.category_id is not None):
            continue
        category = rules.category_for(label=t.label_raw, amount=t.amount, account_id=t.account_id)
        if category is not None and category != t.category_id:
            t.category_id = category
            changed += 1
    db.flush()
    return changed


@dataclass
class Preview:
    matching: list[Transaction]
    uncategorised: int


def preview(db: Session, viewer: User, category: Category, conditions: Conditions) -> Preview:
    rules = RuleSet([_draft(category, conditions)])
    hits = [
        t
        for t in _visible_transactions(db, viewer)
        if rules.category_for(label=t.label_raw, amount=t.amount, account_id=t.account_id)
    ]
    hits.sort(key=lambda t: (t.booked_on, t.id), reverse=True)
    return Preview(matching=hits, uncategorised=sum(1 for t in hits if t.category_id is None))
