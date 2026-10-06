"""Categorisation rules (F-CAT-2): the first matching rule, by priority, sets the category."""

import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass, field
from decimal import Decimal
from uuid import UUID, uuid4

from kwak_core.categories import CategoryKind


class RuleError(ValueError):
    pass


def fold(text: str) -> str:
    """Comparison form: upper case, single spaces, no accents ("Église" -> "EGLISE")."""
    decomposed = unicodedata.normalize("NFKD", text)
    bare = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(bare.upper().split())


@dataclass(frozen=True)
class Rule:
    category_id: UUID
    kind: CategoryKind
    """The category's kind: an expense rule only catches outflows, an income rule inflows."""
    priority: int
    """Lower runs first."""
    label_contains: str | None = None
    amount_min: Decimal | None = None
    """Bounds apply to the absolute amount, inclusive."""
    amount_max: Decimal | None = None
    account_id: UUID | None = None
    id: UUID = field(default_factory=uuid4)
    """Breaks priority ties: with UUIDv7 ids, the oldest rule wins."""


def validate_rule(rule: Rule) -> None:
    has_label = bool(rule.label_contains and rule.label_contains.strip())
    bounds = (rule.amount_min, rule.amount_max)
    if not has_label and all(b is None for b in bounds) and rule.account_id is None:
        raise RuleError("a rule needs at least one condition")
    if any(b is not None and b < 0 for b in bounds):
        raise RuleError("amount bounds are positive: they apply to the absolute amount")
    low, high = bounds
    if low is not None and high is not None and low > high:
        raise RuleError("the minimum amount is above the maximum")


def _matches(rule: Rule, needle: str, *, haystack: str, amount: Decimal, account_id: UUID) -> bool:
    if (amount < 0) != (rule.kind is CategoryKind.EXPENSE):
        return False
    if rule.account_id is not None and rule.account_id != account_id:
        return False
    if rule.amount_min is not None and abs(amount) < rule.amount_min:
        return False
    if rule.amount_max is not None and abs(amount) > rule.amount_max:
        return False
    return needle in haystack


def matches(rule: Rule, *, label: str, amount: Decimal, account_id: UUID) -> bool:
    needle = fold(rule.label_contains or "")
    return _matches(rule, needle, haystack=fold(label), amount=amount, account_id=account_id)


class RuleSet:
    """Rules sorted and folded once, to categorise many transactions."""

    def __init__(self, rules: Iterable[Rule]) -> None:
        ordered = sorted(rules, key=lambda r: (r.priority, r.id))
        self._rules = [(r, fold(r.label_contains or "")) for r in ordered]

    def category_for(self, *, label: str, amount: Decimal, account_id: UUID) -> UUID | None:
        haystack = fold(label)
        for rule, needle in self._rules:
            if _matches(rule, needle, haystack=haystack, amount=amount, account_id=account_id):
                return rule.category_id
        return None


def first_match(
    rules: Iterable[Rule], *, label: str, amount: Decimal, account_id: UUID
) -> UUID | None:
    """The category of the first matching rule, or None."""
    return RuleSet(rules).category_for(label=label, amount=amount, account_id=account_id)
