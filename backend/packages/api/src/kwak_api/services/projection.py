"""The wealth projection's assumptions (spec §4.11 F-SIM-1), saved per household: each asset
category's return and volatility, the inflation, and each debt line's repayment."""

from decimal import Decimal

from kwak_core import goal_analysis as ga
from kwak_core.budget import Month
from kwak_core.projection import DEFAULT_INFLATION, Assumption, DebtTerms, assumption_of
from kwak_core.wealth import WealthKind, line_cell
from sqlalchemy.orm import Session

from kwak_api.models import Household, User, WealthCategory, WealthLine
from kwak_api.services import goals, wealth


def assumption(category: WealthCategory) -> Assumption:
    """The household's own, else the default of its preset (0 % ± 0 for one added later)."""
    if category.expected_return is None or category.volatility is None:
        return assumption_of(category.preset)
    return Assumption(category.expected_return, category.volatility)


def risk(category: WealthCategory) -> ga.LineRisk:
    """How the goals analysis judges a line of this category (F-ANA-1)."""
    own = category.expected_return is not None
    return ga.risk_of(category.preset, assumption(category) if own else None)


def inflation(household: Household) -> Decimal:
    return DEFAULT_INFLATION if household.inflation is None else household.inflation


def debt_terms(line: WealthLine) -> DebtTerms:
    return DebtTerms(line.debt_payment, line.debt_rate, line.debt_insurance)


def debts(db: Session, viewer: User, month: Month) -> list[tuple[WealthLine, Decimal | None]]:
    """The debt lines the viewer sees, open in `month`, with what they owe then (carried
    forward; None before their first value)."""
    lines = [
        line
        for line in wealth.visible_lines(db, viewer)
        if line.category.kind is WealthKind.DEBT
        and (line.closed_from is None or Month.of(line.closed_from) > month)
    ]
    values = goals.line_values(db, {line.id for line in lines})
    out: list[tuple[WealthLine, Decimal | None]] = []
    for line in lines:
        cell = line_cell(values.get(line.id, {}), month)
        out.append((line, cell.amount if cell else None))
    return out
