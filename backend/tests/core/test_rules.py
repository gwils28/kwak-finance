from decimal import Decimal
from uuid import uuid4

import pytest
from hypothesis import given
from hypothesis import strategies as st
from kwak_core.categories import CategoryKind
from kwak_core.rules import Rule, RuleError, first_match, fold, validate_rule

GROCERIES, SALARY = uuid4(), uuid4()
CHECKING, SAVINGS = uuid4(), uuid4()


def _rule(category=GROCERIES, kind=CategoryKind.EXPENSE, priority=10, **conditions) -> Rule:  # type: ignore[no-untyped-def]
    return Rule(category_id=category, kind=kind, priority=priority, **conditions)


def _match(rules: list[Rule], label: str, amount: str, account=CHECKING):  # type: ignore[no-untyped-def]
    return first_match(rules, label=label, amount=Decimal(amount), account_id=account)


def test_fold_ignores_case_spacing_and_accents() -> None:
    assert fold("  Pharmacie de  l'Église ") == "PHARMACIE DE L'EGLISE"


def test_label_contains_matches_whatever_the_case_spacing_or_accents() -> None:
    rules = [_rule(label_contains="église")]
    assert _match(rules, "CARTE X0000 28/02 PHARMACIE DE L'EGLISE 1IOPD", "-12.30") == GROCERIES
    assert _match(rules, "CARTE X0000 BOULANGERIE", "-4.20") is None


def test_amount_bounds_use_the_absolute_value_and_are_inclusive() -> None:
    rules = [_rule(amount_min=Decimal("50"), amount_max=Decimal("100"))]
    assert _match(rules, "ANY", "-50.00") == GROCERIES
    assert _match(rules, "ANY", "-100.00") == GROCERIES
    assert _match(rules, "ANY", "-100.01") is None
    assert _match(rules, "ANY", "-49.99") is None


def test_a_rule_only_catches_money_moving_its_categorys_way() -> None:
    expense = [_rule(label_contains="REMBOURSEMENT")]
    income = [_rule(category=SALARY, kind=CategoryKind.INCOME, label_contains="REMBOURSEMENT")]
    assert _match(expense, "VIR REMBOURSEMENT", "25.00") is None
    assert _match(expense, "VIR REMBOURSEMENT", "-25.00") == GROCERIES
    assert _match(income, "VIR REMBOURSEMENT", "25.00") == SALARY
    assert _match(income, "VIR REMBOURSEMENT", "-25.00") is None


def test_a_rule_can_be_limited_to_one_account() -> None:
    rules = [_rule(label_contains="VIR", account_id=SAVINGS)]
    assert _match(rules, "VIR EUROPEEN", "-100.00", account=SAVINGS) == GROCERIES
    assert _match(rules, "VIR EUROPEEN", "-100.00", account=CHECKING) is None


def test_every_condition_must_hold() -> None:
    rules = [_rule(label_contains="CARTE", amount_max=Decimal("10"))]
    assert _match(rules, "CARTE CAFE", "-1.10") == GROCERIES
    assert _match(rules, "CARTE HIFI", "-450.00") is None


def test_the_lowest_priority_number_wins() -> None:
    specific = _rule(category=uuid4(), priority=1, label_contains="CAFE DE LA GARE")
    general = _rule(priority=5, label_contains="CAFE")
    assert _match([general, specific], "CARTE CAFE DE LA GARE", "-1.10") == specific.category_id
    assert _match([general, specific], "CARTE CAFE DU PORT", "-1.10") == general.category_id


@given(st.lists(st.integers(min_value=0, max_value=5), min_size=1, max_size=8))
def test_the_order_rules_are_given_in_does_not_matter(priorities: list[int]) -> None:
    rules = [_rule(category=uuid4(), priority=p, label_contains="CAFE") for p in priorities]
    # Ties go to the oldest rule: ids are UUIDv7, ordered by creation time.
    best = min(rules, key=lambda r: (r.priority, r.id))
    assert _match(rules, "CAFE", "-1.00") == best.category_id
    assert _match(list(reversed(rules)), "CAFE", "-1.00") == best.category_id


@pytest.mark.parametrize(
    ("conditions", "message"),
    [
        ({}, "at least one condition"),
        ({"label_contains": "   "}, "at least one condition"),
        ({"amount_min": Decimal("10"), "amount_max": Decimal("5")}, "minimum"),
        ({"amount_min": Decimal("-1")}, "positive"),
    ],
)
def test_invalid_rules_are_rejected(conditions: dict[str, object], message: str) -> None:
    with pytest.raises(RuleError, match=message):
        validate_rule(_rule(**conditions))
