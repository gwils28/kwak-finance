"""The projection's inputs read from the household, and the runs (spec §4.11 F-SIM-2 to 4)."""

from decimal import Decimal
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from kwak_api.models import User
from kwak_api.services import projection
from kwak_core.budget import Month
from kwak_core.projection import Assumption, ProjectionError
from kwak_core.visibility import Scope
from sqlalchemy.orm import Session

from tests.api.conftest import Clock, csrf, log_in
from tests.api.wealth.test_wealth import TODAY, _categories, _line, _value

D = Decimal

FLAT = Assumption(D(0), D(0))


@pytest.fixture
def owner_client(client: TestClient, clock: Clock, owner: User) -> TestClient:
    clock.now = TODAY
    log_in(client, clock)
    return client


def _capacity(client: TestClient, amount: str) -> None:
    response = client.patch(
        "/api/household/settings", json={"goal_capacity": amount}, headers=csrf(client)
    )
    assert response.status_code == 200, response.text


def _basis(session: Session, owner: User, scope: Scope = Scope.HOUSEHOLD) -> projection.Basis:
    basis = projection.basis(session, owner, scope, TODAY.date())
    assert basis is not None
    return basis


def test_without_a_wealth_line_there_is_nothing_to_project(
    owner_client: TestClient, session: Session, owner: User
) -> None:
    assert projection.basis(session, owner, Scope.HOUSEHOLD, TODAY.date()) is None


def test_the_basis_starts_from_this_months_wealth(
    owner_client: TestClient, session: Session, owner: User
) -> None:
    _capacity(owner_client, "500.00")
    livret = _line(owner_client, "Savings accounts", "Livret A")
    _value(owner_client, livret, "2026-10", "6000.00")
    pea = _line(owner_client, "Stocks", "PEA")
    _value(owner_client, pea, "2026-11", "4000.00")
    _value(owner_client, pea, "2027-01", "9000.00")  # after the start: never read
    loan = _line(owner_client, "Debts", "Prêt auto")
    _value(owner_client, loan, "2026-12", "2000.00")

    basis = _basis(session, owner)
    cats = _categories(owner_client)
    savings, stocks = UUID(cats["Savings accounts"]["id"]), UUID(cats["Stocks"]["id"])
    assert basis.start.month == Month(2026, 12)
    assert basis.start.assets == {savings: D("6000.00"), stocks: D("4000.00")}
    assert basis.start.net == D("8000.00")
    assert basis.allocation == {savings: D("0.6"), stocks: D("0.4")}
    assert (basis.savings, basis.savings_set) == (D("500.00"), True)
    assert basis.inflation == D("0.02")
    assert basis.assumptions[stocks] == Assumption(D("0.07"), D("0.16"))
    assert [c.name for c in basis.categories][:3] == [
        "Savings accounts",
        "Current accounts",
        "Stocks",
    ]


def test_with_no_volatility_every_outcome_is_the_compounded_path(
    owner_client: TestClient, session: Session, owner: User
) -> None:
    _capacity(owner_client, "0.00")
    livret = _line(owner_client, "Savings accounts", "Livret A")
    _value(owner_client, livret, "2026-12", "10000.00")

    outcome = projection.run(_basis(session, owner), years=1)
    assert outcome.months == 12
    [last] = outcome.percentiles(today=False)[-1:]
    assert set(last.values()) == {D("10170.00")}  # 1.7 % a year, all percentiles equal
    assert outcome.percentiles()[-1][50] == D("9970.59")  # in today's euros, 2 % inflation


def test_a_repaid_debt_frees_its_payment_for_the_savings(
    owner_client: TestClient, session: Session, owner: User
) -> None:
    _capacity(owner_client, "0.00")
    livret = _line(owner_client, "Savings accounts", "Livret A")
    _value(owner_client, livret, "2026-12", "10000.00")
    loan = _line(owner_client, "Debts", "Prêt auto")
    _value(owner_client, loan, "2026-12", "1000.00")
    response = owner_client.put(
        f"/api/projection/debts/{loan}",
        json={"payment": "500.00", "rate": "0", "insurance": "0"},
        headers=csrf(owner_client),
    )
    assert response.status_code == 200, response.text

    basis = _basis(session, owner)
    assert basis.start.net == D("9000.00")
    savings = next(iter(basis.start.assets))
    flat = projection.WhatIf(assumptions={savings: FLAT}, inflation=D(0))
    outcome = projection.run(basis, years=1, what_if=flat)
    # Repaid in two months, then 500 a month joins the savings for ten months.
    assert outcome.percentiles()[-1][50] == D("15000.00")


def test_a_what_if_changes_the_savings_and_the_allocation(
    owner_client: TestClient, session: Session, owner: User
) -> None:
    _capacity(owner_client, "0.00")
    livret = _line(owner_client, "Savings accounts", "Livret A")
    _value(owner_client, livret, "2026-12", "1000.00")
    basis = _basis(session, owner)
    gold = UUID(_categories(owner_client)["Gold"]["id"])
    what_if = projection.WhatIf(
        savings=D("100.00"),
        allocation={gold: 100},
        assumptions={gold: FLAT},
        inflation=D(0),
    )
    outcome = projection.run(basis, years=1, what_if=what_if)
    ids = [c.id for c in basis.categories]
    assert dict(zip(ids, outcome.medians_by_category()[-1], strict=True))[gold] == D("1200.00")


def test_with_nothing_to_share_by_a_what_if_must_set_the_allocation(
    owner_client: TestClient, session: Session, owner: User
) -> None:
    house = _line(owner_client, "Real estate", "Maison")
    _value(owner_client, house, "2026-12", "200000.00")
    basis = _basis(session, owner)
    # Savings accounts exist: the savings go there by default.
    assert basis.allocation is not None
    presets = {c.id: c.preset for c in basis.categories}
    assert [presets[k] for k in basis.allocation] == ["savings"]
    with pytest.raises(ProjectionError, match="sum to 100"):
        projection.run(basis, years=1, what_if=projection.WhatIf(allocation={}))


def test_the_mine_scope_leaves_out_a_joint_line(
    owner_client: TestClient, session: Session, owner: User
) -> None:
    mine = _line(owner_client, "Savings accounts", "Livret A")
    _value(owner_client, mine, "2026-12", "1000.00")
    joint = _line(owner_client, "Current accounts", "Compte joint", "joint")
    _value(owner_client, joint, "2026-12", "3000.00")
    assert _basis(session, owner, Scope.MINE).start.net == D("1000.00")
    assert _basis(session, owner, Scope.JOINT).start.net == D("3000.00")
    assert _basis(session, owner).start.net == D("4000.00")
