"""The projection's inputs read from the household, and the runs (spec §4.11 F-SIM-2 to 4)."""

from decimal import Decimal
from typing import Any
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

    outcome = projection.run(_basis(session, owner), years=1).outcome
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
    run = projection.run(basis, years=1, what_if=flat)
    # Repaid in two months, then 500 a month joins the savings for ten months.
    assert run.outcome.percentiles()[-1][50] == D("15000.00")
    assert run.debts()[:4] == [D("1000.00"), D("500.00"), D(0), D(0)]


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
    outcome = projection.run(basis, years=1, what_if=what_if).outcome
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


# F-SIM-5: the simulator's run


def _run(client: TestClient, **body: Any) -> Any:
    return client.post("/api/projection/run", json=body, headers=csrf(client))


def _ok(client: TestClient, **body: Any) -> dict[str, Any]:
    response = _run(client, **body)
    assert response.status_code == 200, response.text
    out: dict[str, Any] = response.json()
    return out


def _livret(client: TestClient, amount: str = "10000.00") -> str:
    _capacity(client, "0.00")
    livret = _line(client, "Savings accounts", "Livret A")
    _value(client, livret, "2026-12", amount)
    return str(_categories(client)["Savings accounts"]["id"])


def test_the_run_uses_the_contributions_being_typed_without_saving_them(
    owner_client: TestClient,
) -> None:
    savings = _livret(owner_client)
    out = _ok(
        owner_client,
        years=1,
        today=False,
        contributions=[{"category_id": savings, "amount": "100.00", "indexed": False}],
        returns=[{"category_id": savings, "ret": "0"}],
        amount="11000.00",
        reach_month="2027-12",
    )
    assert out["start_month"] == "2026-12"
    assert len(out["months"]) == 13
    last = out["months"][12]
    assert (last["month"], last["p10"], last["p50"], last["p90"]) == (
        "2027-12",
        "11200.00",
        "11200.00",
        "11200.00",
    )
    assert (last["today"], last["contributed"], last["repaid"], last["gains"]) == (
        "10000.00",
        "1200.00",
        "0.00",
        "0.00",
    )
    assert out["savings"]["mode"] == "contributions"
    assert out["savings"]["monthly"] == "100.00"
    assert out["horizon"]["income_median"] == "37.33"  # 11,200 x 4 % / 12
    assert out["horizon"]["income_low"] == "37.33"
    reach = out["reach"]
    assert (reach["chance"], reach["half"], reach["ninety"]) == ("1.0000", "2027-10", "2027-10")
    assert out["ceiling_note"] is False
    # Nothing was saved.
    assert all(
        c["contribution"] is None
        for c in owner_client.get("/api/projection/assumptions").json()["categories"]
    )


def test_without_contributions_the_run_saves_the_capacity(owner_client: TestClient) -> None:
    _livret(owner_client)
    _capacity(owner_client, "250.00")
    out = _ok(owner_client, years=2)
    assert (out["savings"]["mode"], out["savings"]["monthly"]) == ("capacity", "250.00")
    assert out["savings"]["capacity"] == "250.00"
    assert out["savings"]["capacity_set"] is True
    assert len(out["months"]) == 25
    assert out["reach"] is None


def test_a_what_if_scales_the_contributions_and_shows_its_median(
    owner_client: TestClient,
) -> None:
    savings = _livret(owner_client)
    flat = [{"category_id": savings, "ret": "0"}]
    item = {"category_id": savings, "amount": "100.00", "indexed": False}
    out = _ok(
        owner_client,
        years=1,
        today=False,
        contributions=[item],
        returns=flat,
        what_ifs=[{"savings": "200.00"}, {"inflation": "0.05"}],
    )
    first, second = out["what_ifs"]
    assert first["median"] == "12400.00"
    assert len(first["medians"]) == 13
    assert second["median"] == "11200.00"  # current euros: the inflation changes nothing


def test_the_income_follows_the_withdrawal_rate_from_2_to_5_percent(
    owner_client: TestClient,
) -> None:
    _livret(owner_client, "12000.00")
    out = _ok(
        owner_client,
        years=1,
        today=False,
        withdrawal_rate="0.05",
        returns=[{"category_id": _categories(owner_client)["Savings accounts"]["id"], "ret": "0"}],
    )
    assert out["horizon"]["income_median"] == "50.00"
    for rate in ("0.019", "0.051"):
        assert _run(owner_client, years=1, withdrawal_rate=rate).status_code == 422


def test_savings_beyond_the_regulated_ceilings_are_noted(owner_client: TestClient) -> None:
    """Compared in current euros: the ceilings are not indexed."""
    savings = _livret(owner_client, "30000.00")
    item = {"category_id": savings, "amount": "1000.00"}
    assert _ok(owner_client, years=1, contributions=[item])["ceiling_note"] is True
    small = {"category_id": savings, "amount": "100.00"}
    assert _ok(owner_client, years=1, contributions=[small])["ceiling_note"] is False


@pytest.mark.parametrize(
    "body",
    [
        {"years": 0},
        {"years": 41},
        {"years": 1, "what_ifs": [{}, {}, {}]},
        {"years": 1, "contributions": [{"category_id": "x", "amount": "1.00"}]},
    ],
)
def test_impossible_runs_are_refused(owner_client: TestClient, body: dict[str, Any]) -> None:
    _livret(owner_client)
    assert _run(owner_client, **body).status_code == 422


def test_a_contribution_to_a_debt_cannot_be_run(owner_client: TestClient) -> None:
    _livret(owner_client)
    debts = _categories(owner_client)["Debts"]["id"]
    body = [{"category_id": debts, "amount": "10.00"}]
    assert _run(owner_client, years=1, contributions=body).status_code == 422


def test_without_a_wealth_line_there_is_nothing_to_run(owner_client: TestClient) -> None:
    assert _run(owner_client, years=1).status_code == 404


def test_with_no_volatility_the_gains_are_nothing_but_the_returns(
    owner_client: TestClient,
) -> None:
    """Invariant §8.46 on the engine: at 0 % ± 0 with a debt repaid and its payment freed, the
    four parts add up to the median; in current euros the gains are 0, in today's euros they
    are the inflation's toll, below 0."""
    savings = _livret(owner_client)
    stocks = _line(owner_client, "Stocks", "PEA")
    _value(owner_client, stocks, "2026-12", "5000.00")
    loan = _line(owner_client, "Debts", "Prêt auto")
    _value(owner_client, loan, "2026-12", "1000.00")
    owner_client.put(
        f"/api/projection/debts/{loan}",
        json={"payment": "300.00", "rate": "0", "insurance": "0"},
        headers=csrf(owner_client),
    )
    stocks_id = _categories(owner_client)["Stocks"]["id"]
    flat = [{"category_id": savings, "ret": "0"}, {"category_id": stocks_id, "ret": "0"}]
    owner_client.put(
        f"/api/projection/categories/{stocks_id}",
        json={"ret": "0", "volatility": "0"},
        headers=csrf(owner_client),
    )
    item = {"category_id": savings, "amount": "100.00"}
    for today in (False, True):
        out = _ok(owner_client, years=1, today=today, contributions=[item], returns=flat)
        for m in out["months"]:
            parts = D(m["today"]) + D(m["contributed"]) + D(m["repaid"]) + D(m["gains"])
            assert parts == D(m["p50"])
            if today:  # after inflation: holdings at 0 % lose to prices
                assert D(m["gains"]) <= 0
            else:
                assert abs(D(m["gains"])) <= D("0.05"), m
        last = out["months"][12]
        assert last["debts"] == "0.00"
        if not today:
            assert last["repaid"] == "1000.00"
            # Stocks get no contribution: they stay as they are.
            held = next(c for c in out["categories"] if c["id"] == stocks_id)["medians"]
            assert held[0] == held[12] == "5000.00"


def test_a_what_if_on_the_return_alone_keeps_the_volatility(owner_client: TestClient) -> None:
    _livret(owner_client)
    stocks = _line(owner_client, "Stocks", "PEA")
    _value(owner_client, stocks, "2026-12", "50000.00")
    stocks_id = _categories(owner_client)["Stocks"]["id"]
    out = _ok(owner_client, years=5, what_ifs=[{"category_id": stocks_id, "ret": "0.03"}])
    (w,) = out["what_ifs"]
    assert D(w["p10"]) < D(w["median"]) < D(w["p90"])  # 3 % ± 16 %, not ± 0


@pytest.mark.parametrize("savings", ["0.00", "-100.00"])
def test_with_contributions_a_what_if_keeps_the_savings_above_zero(
    owner_client: TestClient, savings: str
) -> None:
    category = _livret(owner_client)
    item = {"category_id": category, "amount": "100.00"}
    body = {"years": 1, "contributions": [item], "what_ifs": [{"savings": savings}]}
    assert _run(owner_client, **body).status_code == 422


def test_an_absurd_contribution_is_refused_not_an_error(owner_client: TestClient) -> None:
    category = _livret(owner_client)
    for amount in ("1e30", "100000.01"):
        body = [{"category_id": category, "amount": amount}]
        assert _run(owner_client, years=1, contributions=body).status_code == 422


def test_the_run_needs_the_csrf_token(owner_client: TestClient) -> None:
    _livret(owner_client)
    assert owner_client.post("/api/projection/run", json={"years": 1}).status_code == 403


def test_another_member_s_private_line_is_never_run(
    owner_client: TestClient, clock: Clock, member: User
) -> None:
    _livret(owner_client)
    private = _line(owner_client, "Stocks", "Mon PEA", visibility="private")
    _value(owner_client, private, "2026-12", "99000.00")
    log_in(owner_client, clock, "member@example.com")
    out = _ok(owner_client, years=1, today=False)
    assert out["months"][0]["p50"] == "10000.00"
    assert "Stocks" not in {c["name"] for c in out["categories"]}


# F-SIM-3: where the monthly savings come from


def test_declared_without_a_contribution_saves_nothing(owner_client: TestClient) -> None:
    """A month of exceptional savings must not drive the projection: declared, only the
    contributions count."""
    _livret(owner_client)
    _capacity(owner_client, "4850.00")
    out = _ok(owner_client, years=1, today=False, savings_source="declared")
    assert out["savings"]["source"] == "declared"
    assert out["savings"]["monthly"] == "0.00"
    assert out["savings"]["capacity"] == "4850.00", "still given, for comparison"
    assert out["months"][12]["contributed"] == "0.00"


def test_measured_saves_the_capacity_split_like_the_contributions(
    owner_client: TestClient,
) -> None:
    savings = _livret(owner_client)
    stocks = str(_categories(owner_client)["Stocks"]["id"])
    _capacity(owner_client, "600.00")
    out = _ok(
        owner_client,
        years=1,
        today=False,
        savings_source="measured",
        contributions=[
            {"category_id": savings, "amount": "100.00"},
            {"category_id": stocks, "amount": "200.00"},
        ],
    )
    assert (out["savings"]["source"], out["savings"]["mode"]) == ("measured", "capacity")
    assert out["savings"]["monthly"] == "600.00"
    assert out["savings"]["share_of_capacity"] is None
    medians = {c["id"]: c["medians"] for c in out["categories"]}
    assert D(medians[stocks][12]) > 3000, "two thirds of 7,200 into stocks, from nothing"
    assert D("7200.00") < D(out["months"][12]["contributed"]) < D("7300.00"), "indexed, 2 %"


def test_unset_the_source_is_declared_once_a_contribution_exists(
    owner_client: TestClient,
) -> None:
    savings = _livret(owner_client)
    _capacity(owner_client, "600.00")
    assert _ok(owner_client, years=1)["savings"]["source"] == "measured"
    with_one = _ok(
        owner_client, years=1, contributions=[{"category_id": savings, "amount": "50.00"}]
    )
    assert with_one["savings"]["source"] == "declared"
    assert with_one["savings"]["monthly"] == "50.00"
