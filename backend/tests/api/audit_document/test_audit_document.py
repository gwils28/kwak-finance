"""The audit document for a chosen reader (§4.15, invariants §8.47 to §8.49)."""

import json
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from kwak_api.models import AuditEvent, User
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tests.api.conftest import Clock, csrf, log_in
from tests.api.wealth.test_wealth import _line, _value

TODAY = datetime(2026, 11, 14, 12, tzinfo=UTC)


@pytest.fixture
def owner_client(client: TestClient, clock: Clock, owner: User) -> TestClient:
    clock.now = TODAY
    log_in(client, clock)
    return client


def _spending_categories(client: TestClient) -> dict[str, str]:
    return {c["name"]: c["id"] for c in client.get("/api/spending/categories").json()}


def _spend(client: TestClient, category: str, amount: str, day: str, label: str = "x") -> None:
    body = {
        "day": day,
        "label": label,
        "amount": amount,
        "category_id": _spending_categories(client)[category],
    }
    response = client.post("/api/spending/lines", json=body, headers=csrf(client))
    assert response.status_code == 201, response.text


def _document(client: TestClient, **fields: Any) -> Any:
    response = client.post("/api/audit-document", json=fields, headers=csrf(client))
    assert response.status_code == 200, response.text
    return response.json()


def _history(client: TestClient) -> None:
    """Two months of income and spending: September and October 2026."""
    for month in ("2026-09", "2026-10"):
        _spend(client, "Salaries", "3000.00", f"{month}-01")
        _spend(client, "Groceries", "-455.00", f"{month}-05", label="Carrefour rue Pasteur")
        _spend(client, "Housing", "-900.00", f"{month}-03")
    _spend(client, "Refunds", "300.00", "2026-10-10")


def _debt(client: TestClient, name: str = "Crédit auto", visibility: str = "shared") -> str:
    line = _line(client, "Debts", name, visibility)
    assert _value(client, line, "2026-10", "12000.00").status_code == 204
    terms = {"payment": "290.00", "rate": "0.04", "insurance": "10.00"}
    response = client.put(f"/api/projection/debts/{line}", json=terms, headers=csrf(client))
    assert response.status_code == 200, response.text
    return line


def test_the_default_period_starts_at_the_first_month_with_a_line(
    owner_client: TestClient,
) -> None:
    _history(owner_client)
    doc = _document(owner_client, audience="banker")
    assert doc["period"] == {"start": "2026-09", "end": "2026-10", "months": 2, "shortened": True}
    money = doc["money"]
    assert [m["month"] for m in money["months"]] == ["2026-09", "2026-10"]
    assert money["income"]["total"] == "6300.00"
    assert money["spent"]["average"] == "1355.00"
    assert money["income"]["highest_month"] == "2026-10"
    # (6300 - 2710) / 6300 = 57.0 %
    assert money["savings_rate"] == "57.0"
    assert money["no_income"] == []
    assert [y["year"] for y in money["years"]] == [2026]


def test_a_period_is_complete_months_only(owner_client: TestClient) -> None:
    response = owner_client.post(
        "/api/audit-document",
        json={"audience": "banker", "start": "2026-01", "end": "2026-11"},
        headers=csrf(owner_client),
    )
    assert response.status_code == 422


def test_the_debt_ratio_leaves_refunds_out_and_lists_debts_without_payment(
    owner_client: TestClient,
) -> None:
    _history(owner_client)
    _debt(owner_client)
    unknown = _line(owner_client, "Debts", "Prêt familial")
    assert _value(owner_client, unknown, "2026-10", "2000.00").status_code == 204
    doc = _document(owner_client, audience="banker", withholding="0.09")
    ratio = doc["ratio"]
    assert ratio["income"] == "3000.00"  # Refunds left out
    assert ratio["left_out"] == ["Refunds"]
    assert ratio["payments"] == "300.00"
    assert ratio["ratio"] == "10.0"
    assert ratio["above_ceiling"] is False
    # 300 / (3000 / 0.91) = 9.1 %
    assert ratio["before_tax_ratio"] == "9.1"
    assert ratio["remaining"] == "2700.00"
    assert [d["label"]["name"] for d in ratio["debts"]] == ["Crédit auto"]
    assert ratio["debts"][0]["ends"] is not None
    assert ratio["left_out_debts"] == [
        {"name": "Prêt familial", "group": None, "key": None, "number": None}
    ]
    refunds = _spending_categories(owner_client)["Refunds"]
    salaries = _spending_categories(owner_client)["Salaries"]
    counted = _document(owner_client, audience="banker", counted=[salaries, refunds])
    assert counted["ratio"]["income"] == "3150.00"


def test_the_property_project(owner_client: TestClient) -> None:
    _history(owner_client)
    livret = _line(owner_client, "Savings accounts", "Livret A")
    assert _value(owner_client, livret, "2026-10", "40000.00").status_code == 204
    project = {
        "price": "200000.00",
        "property_age": "old",
        "down_payment": "20000.00",
        "years": 25,
        "rate": "0.035",
        "insurance": "40.00",
        "rent": "900.00",
    }
    doc = _document(owner_client, audience="banker", project=project)
    p = doc["project"]
    assert p["notary_fees"] == "16000.00"
    assert p["notary_estimated"] is True
    assert p["loan"] == "196000.00"
    assert p["payment"] == "981.22"
    assert p["duration"] == "within"
    # (981.22 + 40) / 3000 = 34.0 %
    assert p["ratio_after"] == "34.0"
    assert p["above_ceiling"] is False
    assert p["housing_change"] == "121.22"
    assert p["liquid_left"] == "20000.00"
    assert _document(owner_client, audience="advisor", project=project)["project"] is None


def test_the_ai_document_is_anonymised_by_default(owner_client: TestClient, member: User) -> None:
    _history(owner_client)
    pea = _line(owner_client, "Stocks", "PEA Fortuneo")
    response = owner_client.patch(
        f"/api/wealth/lines/{pea}",
        json={"tax_envelope": "pea", "opening_year": 2019},
        headers=csrf(owner_client),
    )
    assert response.status_code == 200, response.text
    assert _value(owner_client, pea, "2026-10", "15000.00").status_code == 204
    livret = _line(owner_client, "Savings accounts", "Livret A Boursorama")
    assert _value(owner_client, livret, "2026-10", "5000.00").status_code == 204
    goal = {
        "name": "Voyage au Japon",
        "target": "6000.00",
        "deadline": "2027-08",
        "visibility": "shared",
        "fundings": [],
    }
    assert owner_client.post("/api/goals", json=goal, headers=csrf(owner_client)).status_code == 201

    doc = _document(owner_client, audience="ai")
    assert doc["privacy"] == {"named_members": False, "named_lines": False, "exact_amounts": True}
    text = json.dumps(doc)
    for secret in (
        "Home",
        "Owner",
        "Member",
        "owner@example.com",
        "PEA Fortuneo",
        "Livret A Boursorama",
        "Voyage au Japon",
        "Carrefour",
    ):
        assert secret not in text, secret
    lines = {(ln["label"]["group"], ln["label"]["key"]) for ln in doc["wealth"]["lines"]}
    assert ("envelope", "pea") in lines
    assert ("category", "Savings accounts") in lines
    [stocks] = [ln for ln in doc["wealth"]["lines"] if ln["envelope"] == "pea"]
    assert (stocks["opening_year"], stocks["age"], stocks["milestone"]) == (2019, 7, "reached")
    assert doc["goals"]["goals"][0]["label"] == {
        "name": None,
        "group": "tier",
        "key": "short",
        "number": 1,
    }
    assert doc["household"]["name"] is None
    assert {m["label"]["key"] for m in doc["household"]["members"]} == {"A", "B"}


def test_rounded_amounts_still_add_up(owner_client: TestClient) -> None:
    _history(owner_client)
    for name, amount in (("Livret A", "1400.00"), ("LDDS", "1400.00"), ("LEP", "1400.00")):
        line = _line(owner_client, "Savings accounts", name)
        assert _value(owner_client, line, "2026-10", amount).status_code == 204
    _debt(owner_client)
    privacy = {"named_members": True, "named_lines": True, "exact_amounts": False}
    doc = _document(owner_client, audience="notary", privacy=privacy)
    wealth = doc["wealth"]
    assets = [Decimal(ln["value"]) for ln in wealth["lines"] if ln["kind"] == "asset"]
    assert sum(assets) == Decimal(wealth["gross"]) == Decimal(4000)
    assert Decimal(wealth["net"]) == Decimal(wealth["gross"]) - Decimal(wealth["debts"])
    assert sum(Decimal(h["net"]) for h in wealth["holders"]) == Decimal(wealth["net"])
    money = doc["money"]
    assert Decimal(money["income"]["total"]) == Decimal(6300)
    parts = sum(Decimal(c["amount"]) for c in money["spending_by_category"])
    assert parts + Decimal(money["spending_rest"]) == Decimal(money["spent"]["total"])


def test_a_private_line_never_reaches_another_members_document(
    client: TestClient, clock: Clock, owner: User, member: User
) -> None:
    clock.now = TODAY
    log_in(client, clock)
    private = _line(client, "Stocks", "Mon CTO secret", "private")
    assert _value(client, private, "2026-10", "9000.00").status_code == 204
    _debt(client, "Prêt perso secret", "private")
    log_in(client, clock, "member@example.com")
    doc = _document(client, audience="advisor")
    text = json.dumps(doc)
    assert "Mon CTO secret" not in text
    assert "Prêt perso secret" not in text
    assert doc["wealth"]["gross"] == "0"
    assert doc["ratio"]["debts"] == []


def test_building_a_document_stores_nothing_and_issuing_one_is_logged_without_figures(
    owner_client: TestClient, session: Session
) -> None:
    _history(owner_client)
    before = session.scalar(select(func.count()).select_from(AuditEvent))
    _document(owner_client, audience="banker")
    assert session.scalar(select(func.count()).select_from(AuditEvent)) == before
    issued = {
        "audience": "banker",
        "scope": "household",
        "start": "2026-09",
        "end": "2026-10",
        "how": "print",
    }
    response = owner_client.post(
        "/api/audit-document/issued", json=issued, headers=csrf(owner_client)
    )
    assert response.status_code == 204, response.text
    entry = session.scalars(
        select(AuditEvent).where(AuditEvent.action == "audit_document_issued")
    ).one_or_none()
    assert entry is not None
    assert entry.action == "audit_document_issued"
    assert entry.details == {
        "audience": "banker",
        "scope": "household",
        "start": "2026-09",
        "end": "2026-10",
        "how": "print",
    }


def test_a_line_takes_an_envelope_only_when_it_can(owner_client: TestClient) -> None:
    debt = _line(owner_client, "Debts", "Crédit")
    refused = owner_client.patch(
        f"/api/wealth/lines/{debt}", json={"tax_envelope": "pea"}, headers=csrf(owner_client)
    )
    assert refused.status_code == 422
    stocks = _line(owner_client, "Stocks", "PEA")
    future = owner_client.patch(
        f"/api/wealth/lines/{stocks}", json={"opening_year": 2027}, headers=csrf(owner_client)
    )
    assert future.status_code == 422


def test_privacy_defaults(owner_client: TestClient) -> None:
    assert owner_client.get("/api/audit-document/privacy/ai").json() == {
        "named_members": False,
        "named_lines": False,
        "exact_amounts": True,
    }


def test_a_period_before_1900_or_a_bad_issued_period_is_refused(owner_client: TestClient) -> None:
    year_zero = {"audience": "banker", "start": "0000-01", "end": "0000-12"}
    response = owner_client.post("/api/audit-document", json=year_zero, headers=csrf(owner_client))
    assert response.status_code == 422
    backwards = {
        "audience": "banker",
        "scope": "household",
        "start": "2026-10",
        "end": "2026-09",
        "how": "copy",
    }
    response = owner_client.post(
        "/api/audit-document/issued", json=backwards, headers=csrf(owner_client)
    )
    assert response.status_code == 422


def test_mine_leaves_out_another_members_shared_lines_and_goals(
    client: TestClient, clock: Clock, owner: User, member: User
) -> None:
    clock.now = TODAY
    log_in(client, clock)
    shared = _line(client, "Stocks", "CTO du foyer")
    assert _value(client, shared, "2026-10", "3000.00").status_code == 204
    goal = {
        "name": "Cuisine",
        "target": "8000.00",
        "deadline": "2028-08",
        "visibility": "shared",
        "fundings": [],
    }
    assert client.post("/api/goals", json=goal, headers=csrf(client)).status_code == 201
    log_in(client, clock, "member@example.com")
    everything = _document(client, audience="advisor")
    assert [ln["label"]["name"] for ln in everything["wealth"]["lines"]] == ["CTO du foyer"]
    assert [g["label"]["name"] for g in everything["goals"]["goals"]] == ["Cuisine"]
    # The viewer is member A, whatever the names' order.
    anonymous = _document(client, audience="ai")
    [a, b] = anonymous["household"]["members"]
    assert (a["label"]["key"], b["label"]["key"]) == ("A", "B")
    mine = _document(client, audience="advisor", scope="mine")
    assert mine["wealth"]["lines"] == []
    assert mine["goals"]["goals"] == []
    assert [m["label"]["name"] for m in mine["household"]["members"]] == ["Member"]


def test_a_regulated_line_takes_no_envelope(owner_client: TestClient) -> None:
    livret = _line(owner_client, "Savings accounts", "Livret A")
    response = owner_client.patch(
        f"/api/wealth/lines/{livret}",
        json={"regulated_type": "livret_a", "tax_envelope": "life_insurance"},
        headers=csrf(owner_client),
    )
    assert response.status_code == 422


def test_a_net_refund_in_a_category_still_adds_up_and_rounded_months_sum_to_the_total(
    owner_client: TestClient,
) -> None:
    _history(owner_client)
    # Shopping nets a refund: an item sold back counts as negative spending.
    _spend(owner_client, "Shopping", "-100.00", "2026-09-12")
    _spend(owner_client, "Shopping", "-5.00", "2026-10-12")
    exact = _document(owner_client, audience="advisor")["money"]
    parts = sum(Decimal(c["amount"]) for c in exact["spending_by_category"])
    assert parts + Decimal(exact["spending_rest"]) == Decimal(exact["spent"]["total"])
    privacy = {"named_members": True, "named_lines": True, "exact_amounts": False}
    money = _document(owner_client, audience="advisor", privacy=privacy)["money"]
    for measure in ("income", "spent", "saved", "rest"):
        total = sum(Decimal(m[measure]) for m in money["months"])
        assert total == Decimal(money[measure]["total"]), measure
    years = sum(Decimal(y["spent"]) for y in money["years"])
    assert years == Decimal(money["spent"]["total"])


def test_an_earlier_period_starts_at_the_first_month_with_a_line(
    owner_client: TestClient,
) -> None:
    _history(owner_client)
    doc = _document(owner_client, audience="banker", start="2025-01", end="2026-10")
    assert doc["period"] == {"start": "2026-09", "end": "2026-10", "months": 2, "shortened": True}
    assert doc["money"]["no_income"] == []


def test_a_loan_entered_this_month_is_counted_and_one_without_value_is_listed(
    owner_client: TestClient,
) -> None:
    _history(owner_client)
    car = _line(owner_client, "Debts", "Crédit auto")
    assert _value(owner_client, car, "2026-11", "15000.00").status_code == 204
    terms = {"payment": "300.00", "rate": "0.03", "insurance": "0.00"}
    owner_client.put(f"/api/projection/debts/{car}", json=terms, headers=csrf(owner_client))
    _line(owner_client, "Debts", "Prêt sans valeur")
    ratio = _document(owner_client, audience="banker")["ratio"]
    assert ratio["payments"] == "300.00"
    assert [d["name"] for d in ratio["left_out_debts"]] == ["Prêt sans valeur"]


def test_the_fixed_expenses_and_net_worth_change_match_the_app(owner_client: TestClient) -> None:
    _history(owner_client)
    for day in ("2026-01-10", "2026-02-10", "2026-03-10"):
        body = {
            "label": f"Assurance {day}",
            "category_id": _spending_categories(owner_client)["Housing"],
            "amount": "-100.00",
            "frequency": "quarterly",
            "day": 10,
            "first_month": day[:7],
        }
        response = owner_client.post("/api/spending/fixed", json=body, headers=csrf(owner_client))
        assert response.status_code == 201, response.text
    proposal = owner_client.get("/api/goals/precaution-proposal", params={"months": 1}).json()
    doc = _document(owner_client, audience="advisor")
    assert doc["money"]["fixed_monthly"] == proposal["monthly_fixed"]
    assert "Assurance" not in json.dumps(doc)
    livret = _line(owner_client, "Savings accounts", "Livret A")
    assert _value(owner_client, livret, "2026-08", "1000.00").status_code == 204
    assert _value(owner_client, livret, "2026-10", "1500.00").status_code == 204
    wealth = _document(owner_client, audience="advisor")["wealth"]
    assert (wealth["start_month"], wealth["start_net"], wealth["change"]) == (
        "2026-08",
        "1000.00",
        "500.00",
    )
