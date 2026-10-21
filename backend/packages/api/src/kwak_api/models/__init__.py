"""All ORM models. Alembic's env.py imports this package so autogenerate sees every table."""

from kwak_api.models.account import Account, Institution
from kwak_api.models.audit import AuditEvent
from kwak_api.models.auth_failure import AuthFailure
from kwak_api.models.budget import BudgetPlan, BudgetPlanTarget
from kwak_api.models.category import Category
from kwak_api.models.goal import ClosedAs, Goal, GoalAdjustment, GoalFunding
from kwak_api.models.household import Household, Role, User
from kwak_api.models.invite import Invite
from kwak_api.models.recovery_code import RecoveryCode
from kwak_api.models.recurring import DismissedSuggestion, RecurringItem, RecurringSkip
from kwak_api.models.rule import CategorizationRule
from kwak_api.models.session import UserSession
from kwak_api.models.spending import (
    FixedExpense,
    FixedSkip,
    MonthlyIncome,
    SpendingCategory,
    SpendingLine,
    SpendingLinePart,
)
from kwak_api.models.transaction import ImportBatch, Transaction, TransactionPart
from kwak_api.models.wealth import WealthCategory, WealthLine, WealthValue

__all__ = [
    "Account",
    "AuditEvent",
    "AuthFailure",
    "BudgetPlan",
    "BudgetPlanTarget",
    "CategorizationRule",
    "Category",
    "ClosedAs",
    "DismissedSuggestion",
    "FixedExpense",
    "FixedSkip",
    "Goal",
    "GoalAdjustment",
    "GoalFunding",
    "Household",
    "ImportBatch",
    "Institution",
    "Invite",
    "MonthlyIncome",
    "RecoveryCode",
    "RecurringItem",
    "RecurringSkip",
    "Role",
    "SpendingCategory",
    "SpendingLine",
    "SpendingLinePart",
    "Transaction",
    "TransactionPart",
    "User",
    "UserSession",
    "WealthCategory",
    "WealthLine",
    "WealthValue",
]
