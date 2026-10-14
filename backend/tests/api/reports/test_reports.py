from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from kwak_api.models import User

from tests.api.conftest import Clock, csrf, log_in
from tests.api.dashboard.test_dashboard import _category, _setup

TODAY = datetime(2026, 10, 14, 12, tzinfo=UTC)


@pytest.fixture
def owner_client(client: TestClient, clock: Clock, owner: User) -> TestClient:
    clock.now = TODAY
    log_in(client, clock)
    return client


def _report(client: TestClient, start: str = "2026-03", end: str = "2026-03", **params: str) -> Any:
    response = client.get("/api/reports", params={"start": start, "end": end, **params})
    assert response.status_code == 200, response.text
    return response.json()


def test_the_totals_of_a_month_are_the_home_pages(owner_client: TestClient) -> None:
    _setup(owner_client)
    report = _report(owner_client)
    kpis = owner_client.get("/api/dashboard", params={"month": "2026-03"}).json()["kpis"]

    totals = report["totals"]
    assert (totals["spent"], totals["income"], totals["net"]) == ("1621.04", "2518.65", "897.61")
    assert totals == {k: kpis[k] for k in totals}
    assert report["months"] == 1


def test_a_longer_period_adds_up_its_months_and_compares_with_the_one_before(
    owner_client: TestClient,
) -> None:
    _setup(owner_client)
    report = _report(owner_client, "2026-02", "2026-04")

    assert report["months"] == 3
    assert (report["previous_start"], report["previous_end"]) == ("2025-11", "2026-01")
    assert report["totals"]["spent"] == "1621.04"  # only March has transactions
    assert report["previous"]["spent"] == "0.00"
    assert [m["month"] for m in report["monthly"]] == ["2026-02", "2026-03", "2026-04"]
    assert report["monthly"][1] == {
        "month": "2026-03",
        "income": "2518.65",
        "spent": "1621.04",
        "net": "897.61",
    }


def test_categories_by_section_with_their_subcategories(owner_client: TestClient) -> None:
    _setup(owner_client)
    rows = _report(owner_client, "2026-02", "2026-04")["rows"]

    food = next(r for r in rows if r["name"] == "Food")
    assert food["section"] == "spending"
    assert (food["amount"], food["monthly_average"], food["share"]) == ("6.40", "2.13", "0.0039")
    sections = {x["section"]: x for x in _report(owner_client, "2026-02", "2026-04")["sections"]}
    assert sections["spending"] == {
        "section": "spending",
        "amount": "1621.04",
        "monthly_average": "540.35",
        "previous": "0.00",
        "change": None,
    }
    assert food["change"] is None  # nothing the period before
    assert [(c["name"], c["amount"]) for c in food["children"]] == [("Bakery and coffee", "6.40")]

    spending = [r for r in rows if r["section"] == "spending"]
    assert spending[-1]["category_id"] is None  # to categorise comes last
    assert spending[-1]["amount"] == "1614.64"
    assert sum(Decimal(r["amount"]) for r in spending) == Decimal("1621.04")
    income = [r for r in rows if r["section"] == "income"]
    assert income[0]["name"] == "Income"
    assert income[0]["children"][0]["category_id"] == _category(owner_client, "Salary")


def test_the_money_flows_of_the_period_balance(owner_client: TestClient) -> None:
    _setup(owner_client)
    flows = _report(owner_client)["flows"]

    def side(s: str) -> Decimal:
        return sum((Decimal(f["amount"]) for f in flows if f["side"] == s), Decimal(0))

    assert side("in") == side("out") == Decimal("2518.65")
    assert any(f["kind"] == "unallocated" and f["amount"] == "897.61" for f in flows)


def test_a_scope_narrows_the_report(owner_client: TestClient) -> None:
    _setup(owner_client)  # a shared account: the owner's, so not joint
    report = _report(owner_client, scope="joint")
    assert report["totals"]["spent"] == "0.00"
    assert report["rows"] == []


@pytest.mark.parametrize(
    ("start", "end"),
    [
        ("2026-13", "2026-12"),
        ("2026-04", "2026-03"),
        ("2016-01", "2026-01"),
        ("2026-11", "2026-12"),  # not started yet
        ("0001-01", "0001-01"),
        ("9999-12", "9999-12"),
    ],
)
def test_a_bad_period_is_rejected(owner_client: TestClient, start: str, end: str) -> None:
    response = owner_client.get("/api/reports", params={"start": start, "end": end})
    assert response.status_code == 422


def test_a_running_year_stops_at_this_month_against_the_same_months_last_year(
    owner_client: TestClient,
) -> None:
    _setup(owner_client)
    report = _report(owner_client, "2026-01", "2026-12")

    assert (report["start"], report["end"], report["months"]) == ("2026-01", "2026-10", 10)
    assert report["to_date"] is True
    assert (report["previous_start"], report["previous_end"]) == ("2025-01", "2025-10")
    food = next(r for r in report["rows"] if r["name"] == "Food")
    assert food["monthly_average"] == "0.64"  # over the 10 months so far, not 12
    assert len(report["monthly"]) == 10


def test_changes_keep_their_direction_from_a_negative_period(owner_client: TestClient) -> None:
    _setup(owner_client)
    entry = {
        "account_id": _account_id(owner_client),
        "booked_on": "2026-04-05",
        "amount": "-100.00",
        "label": "X",
    }
    owner_client.post("/api/transactions", json=entry, headers=csrf(owner_client))
    # April: -100 net, May: nothing. From -100 to 0 is an improvement.
    assert _report(owner_client, "2026-05", "2026-05")["changes"]["net"] == "1.0000"


def _account_id(client: TestClient) -> str:
    account: str = client.get("/api/accounts").json()[0]["id"]
    return account


def test_reports_require_a_full_sign_in(client: TestClient) -> None:
    assert (
        client.get("/api/reports", params={"start": "2026-01", "end": "2026-01"}).status_code == 401
    )


def test_a_member_sees_nothing_of_the_owners_private_accounts(
    client: TestClient, clock: Clock, owner: User, member: User
) -> None:
    clock.now = TODAY
    log_in(client, clock)
    body = {
        "name": "Perso",
        "institution_name": "SG",
        "type": "checking",
        "visibility": "private",
        "opening_balance": "0",
        "opening_date": "2026-03-01",
    }
    account = client.post("/api/accounts", json=body, headers=csrf(client)).json()["id"]
    entry = {"account_id": account, "booked_on": "2026-03-05", "amount": "-50.00", "label": "X"}
    assert client.post("/api/transactions", json=entry, headers=csrf(client)).status_code == 201

    log_in(client, clock, "member@example.com")
    assert _report(client)["totals"]["spent"] == "0.00"


def test_the_owner_sees_nothing_of_a_members_private_accounts(
    client: TestClient, clock: Clock, owner: User, member: User
) -> None:
    clock.now = TODAY
    log_in(client, clock, "member@example.com")
    body = {
        "name": "Perso",
        "institution_name": "SG",
        "type": "checking",
        "visibility": "private",
        "opening_balance": "0",
        "opening_date": "2026-03-01",
    }
    account = client.post("/api/accounts", json=body, headers=csrf(client)).json()["id"]
    entry = {"account_id": account, "booked_on": "2026-03-05", "amount": "-50.00", "label": "X"}
    assert client.post("/api/transactions", json=entry, headers=csrf(client)).status_code == 201
    assert _report(client, scope="mine")["totals"]["spent"] == "50.00"

    log_in(client, clock)
    for scope in ("household", "mine", "joint"):
        report = _report(client, scope=scope)
        assert report["totals"]["spent"] == "0.00"
        assert report["flows"] == []
