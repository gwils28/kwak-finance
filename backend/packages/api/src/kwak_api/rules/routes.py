from datetime import date
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from kwak_core.money import require_cents
from kwak_core.rules import RuleError
from pydantic import AfterValidator, BaseModel

from kwak_api.auth.routes import CurrentSession, Db
from kwak_api.models import CategorizationRule, Category, User
from kwak_api.services import accounts as account_service
from kwak_api.services import categories as category_service
from kwak_api.services import rules as service

router = APIRouter(prefix="/api", tags=["rules"])

Cents = Annotated[Decimal, AfterValidator(require_cents)]
NOT_FOUND = HTTPException(status.HTTP_404_NOT_FOUND, "rule not found")


class RuleIn(BaseModel):
    category_id: UUID
    label_contains: str | None = None
    """Matched anywhere in the label, ignoring case, spacing and accents."""
    amount_min: Cents | None = None
    """Bounds apply to the absolute amount, inclusive."""
    amount_max: Cents | None = None
    account_id: UUID | None = None
    """Only transactions of this account."""


class RulePatch(BaseModel):
    """Only the fields present change; null clears a condition."""

    category_id: UUID | None = None
    label_contains: str | None = None
    amount_min: Cents | None = None
    amount_max: Cents | None = None
    account_id: UUID | None = None
    priority: int | None = None
    """Lower runs first."""


class RuleOut(BaseModel):
    id: UUID
    priority: int
    category_id: UUID
    category_name: str
    label_contains: str | None
    amount_min: Decimal | None
    amount_max: Decimal | None
    account_id: UUID | None

    @classmethod
    def of(cls, rule: CategorizationRule) -> "RuleOut":
        return cls(
            id=rule.id,
            priority=rule.priority,
            category_id=rule.category_id,
            category_name=rule.category.name,
            label_contains=rule.label_contains,
            amount_min=rule.amount_min,
            amount_max=rule.amount_max,
            account_id=rule.account_id,
        )


class ApplyRules(BaseModel):
    only_uncategorised: bool = True
    """False also re-categorises transactions that already have a category."""


class Applied(BaseModel):
    updated: int


class PreviewExample(BaseModel):
    id: UUID
    booked_on: date
    label: str
    amount: Decimal


class RulePreview(BaseModel):
    matching: int
    """Visible transactions the rule would catch."""
    uncategorised: int
    """Of those, the ones without a category yet."""
    examples: list[PreviewExample]
    """The 5 most recent."""


def _category(db: Db, user: User, category_id: UUID) -> Category:
    category = category_service.find(db, user.household_id, category_id)
    if category is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "unknown category")
    return category


def _check_account(db: Db, user: User, account_id: UUID | None) -> None:
    if account_id and account_service.find_visible_account(db, user, account_id) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "unknown account")


def _conditions(body: RuleIn | RulePatch) -> service.Conditions:
    return service.Conditions(
        body.label_contains, body.amount_min, body.amount_max, body.account_id
    )


def _invalid(exc: RuleError) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc))


@router.get("/rules")
def list_rules(user_session: CurrentSession, db: Db) -> list[RuleOut]:
    """In the order they run."""
    return [RuleOut.of(r) for r in service.list_rules(db, user_session.user.household_id)]


@router.post("/rules", status_code=status.HTTP_201_CREATED)
def create_rule(body: RuleIn, user_session: CurrentSession, db: Db) -> RuleOut:
    """New rules run after the existing ones."""
    user = user_session.user
    category = _category(db, user, body.category_id)
    _check_account(db, user, body.account_id)
    try:
        rule = service.create(db, user.household_id, category, _conditions(body))
    except RuleError as exc:
        raise _invalid(exc) from None
    return RuleOut.of(rule)


@router.patch("/rules/{rule_id}")
def update_rule(rule_id: UUID, body: RulePatch, user_session: CurrentSession, db: Db) -> RuleOut:
    user = user_session.user
    rule = db.get(CategorizationRule, rule_id)
    if rule is None or rule.household_id != user.household_id:
        raise NOT_FOUND
    given = body.model_fields_set
    merged = RulePatch(
        category_id=body.category_id if "category_id" in given else rule.category_id,
        label_contains=body.label_contains if "label_contains" in given else rule.label_contains,
        amount_min=body.amount_min if "amount_min" in given else rule.amount_min,
        amount_max=body.amount_max if "amount_max" in given else rule.amount_max,
        account_id=body.account_id if "account_id" in given else rule.account_id,
    )
    category = _category(db, user, merged.category_id or rule.category_id)
    _check_account(db, user, merged.account_id)
    priority = body.priority if body.priority is not None else rule.priority
    try:
        service.update(db, rule, category, _conditions(merged), priority)
    except RuleError as exc:
        raise _invalid(exc) from None
    return RuleOut.of(rule)


@router.delete("/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rule(rule_id: UUID, user_session: CurrentSession, db: Db) -> None:
    rule = db.get(CategorizationRule, rule_id)
    if rule is None or rule.household_id != user_session.user.household_id:
        raise NOT_FOUND
    db.delete(rule)


@router.post("/rules/apply")
def apply_rules(body: ApplyRules, user_session: CurrentSession, db: Db) -> Applied:
    """Re-run every rule on past transactions the user can see."""
    updated = service.apply(db, user_session.user, only_uncategorised=body.only_uncategorised)
    return Applied(updated=updated)


@router.post("/rules/preview")
def preview_rule(body: RuleIn, user_session: CurrentSession, db: Db) -> RulePreview:
    """What a rule with these conditions would catch, without saving it."""
    user = user_session.user
    category = _category(db, user, body.category_id)
    _check_account(db, user, body.account_id)
    try:
        result = service.preview(db, user, category, _conditions(body))
    except RuleError as exc:
        raise _invalid(exc) from None
    return RulePreview(
        matching=len(result.matching),
        uncategorised=result.uncategorised,
        examples=[
            PreviewExample(id=t.id, booked_on=t.booked_on, label=t.label_raw, amount=t.amount)
            for t in result.matching[:5]
        ],
    )
