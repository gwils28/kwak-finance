"""All ORM models. Alembic's env.py imports this package so autogenerate sees every table."""

from kwak_api.models.audit import AuditEvent
from kwak_api.models.auth_failure import AuthFailure
from kwak_api.models.goal import (
    ClosedAs,
    Goal,
    GoalAdjustment,
    GoalFunding,
    GoalNoticeDismissal,
)
from kwak_api.models.household import Household, Role, User
from kwak_api.models.invite import Invite
from kwak_api.models.recovery_code import RecoveryCode
from kwak_api.models.session import UserSession
from kwak_api.models.spending import (
    FixedExpense,
    FixedSkip,
    SpendingCategory,
    SpendingLine,
    SpendingLinePart,
    SpendingTarget,
)
from kwak_api.models.wealth import WealthCategory, WealthLine, WealthValue

__all__ = [
    "AuditEvent",
    "AuthFailure",
    "ClosedAs",
    "FixedExpense",
    "FixedSkip",
    "Goal",
    "GoalAdjustment",
    "GoalFunding",
    "GoalNoticeDismissal",
    "Household",
    "Invite",
    "RecoveryCode",
    "Role",
    "SpendingCategory",
    "SpendingLine",
    "SpendingLinePart",
    "SpendingTarget",
    "User",
    "UserSession",
    "WealthCategory",
    "WealthLine",
    "WealthValue",
]
