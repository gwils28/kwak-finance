from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from kwak_api.auth.passwords import hash_password
from kwak_api.models import Household, Role, SpendingCategory, SpendingLine, User
from kwak_core.categories import CategoryKind
from sqlalchemy.orm import Session

from tests.api.conftest import PASSWORD, Clock, csrf, log_in

TODAY = datetime(2026, 10, 21, 12, tzinfo=UTC)


@pytest.fixture
def owner_client(client: TestClient, clock: Clock, owner: User) -> TestClient:
    clock.now = TODAY
    log_in(client, clock)
    return client


def _categories(client: TestClient) -> dict[str, str]:
    return {c["name"]: c["id"] for c in client.get("/api/spending/categories").json()}


def _line(client: TestClient, category: str, amount: str, day: str) -> None:
    body = {
        "day": day,
        "label": "x",
        "amount": amount,
        "category_id": _categories(client)[category],
    }
    response = client.post("/api/spending/lines", json=body, headers=csrf(client))
    assert response.status_code == 201, response.text


def _income(client: TestClient, month: str, amount: str) -> None:
    response = client.put(
        f"/api/spending/income/{month}", json={"amount": amount}, headers=csrf(client)
    )
    assert response.status_code == 200, response.text


def _report(client: TestClient, start: str, end: str) -> Any:
    response = client.get("/api/spending/report", params={"start": start, "end": end})
    assert response.status_code == 200, response.text
    return response.json()


def _two_months(client: TestClient) -> None:
    """September: income 2000, groceries 200. October: income carried, groceries 300, home 100,
    savings 500 put aside and 100 taken back; groceries' target 250 from October."""
    _income(client, "2026-09", "2000.00")
    _line(client, "Groceries", "-200.00", "2026-09-10")
    _line(client, "Groceries", "-300.00", "2026-10-05")
    _line(client, "Home", "-100.00", "2026-10-06")
    _line(client, "Savings", "-500.00", "2026-10-07")
    _line(client, "Savings", "100.00", "2026-10-08")
    target = client.put(
        f"/api/spending/targets/{_categories(client)['Groceries']}/2026-10",
        json={"amount": "250.00"},
        headers=csrf(client),
    )
    assert target.status_code == 200, target.text


def test_a_month_against_the_one_before(owner_client: TestClient) -> None:
    _two_months(owner_client)
    report = _report(owner_client, "2026-10", "2026-10")

    assert report["start"] == report["end"] == "2026-10"
    assert report["previous_start"] == report["previous_end"] == "2026-09"
    assert report["to_date"] is False
    assert report["totals"] == {
        "income": "2000.00",
        "spent": "400.00",
        "saved": "400.00",
        "rest": "1200.00",
        "savings_rate": "0.8000",
    }
    assert report["previous"]["spent"] == "200.00"
    assert report["changes"]["spent"] == "1.0000"

    rows = [(r["section"], r["name"], r["amount"], r["share"]) for r in report["rows"]]
    assert rows == [
        ("spending", "Groceries", "300.00", "0.7500"),
        ("spending", "Home", "100.00", "0.2500"),
        ("savings", "Savings", "400.00", "1.0000"),
    ]
    groceries = report["rows"][0]
    assert groceries["previous"] == "200.00"
    assert groceries["change"] == "0.5000"
    assert groceries["monthly_average"] == "300.00"
    sections = {s["section"]: s["amount"] for s in report["sections"]}
    assert sections == {"spending": "400.00", "savings": "400.00"}


def test_the_flows_balance_and_mark_the_spending_over_its_targets(
    owner_client: TestClient,
) -> None:
    _two_months(owner_client)
    flows = _report(owner_client, "2026-10", "2026-10")["flows"]

    by_kind = {(f["kind"], f["name"]): (f["side"], f["amount"], f["over"]) for f in flows}
    assert by_kind[("income", None)] == ("in", "2000.00", False)
    assert by_kind[("spending", "Groceries")] == ("out", "300.00", True)
    assert by_kind[("spending", "Home")] == ("out", "100.00", False)
    assert by_kind[("saved", None)] == ("out", "400.00", False)
    assert by_kind[("unallocated", None)] == ("out", "1200.00", False)
    total_in = sum(float(f["amount"]) for f in flows if f["side"] == "in")
    total_out = sum(float(f["amount"]) for f in flows if f["side"] == "out")
    assert total_in == total_out


def test_a_running_year_stops_this_month_and_leaves_out_the_months_before_any_data(
    owner_client: TestClient,
) -> None:
    _two_months(owner_client)
    report = _report(owner_client, "2026-01", "2026-12")

    assert report["start"] == "2026-09"
    assert report["end"] == "2026-10"
    assert report["to_date"] is True
    assert report["months"] == 2
    assert report["first_month"] == "2026-09"
    monthly = [(m["month"], m["income"], m["spent"]) for m in report["monthly"]]
    assert monthly == [("2026-09", "2000.00", "200.00"), ("2026-10", "2000.00", "400.00")]
    october = report["monthly"][1]
    assert {c["name"]: c["spent"] for c in october["by_category"]} == {
        "Groceries": "300.00",
        "Home": "100.00",
    }
    # The months before September are not months of zero: nothing is compared.
    assert report["compared"] is False
    assert report["changes"]["spent"] is None


def test_a_report_counts_only_the_household_lines(
    owner_client: TestClient, session: Session
) -> None:
    _two_months(owner_client)
    # One household per instance: the other one is built by hand.
    elsewhere = Household(name="Elsewhere")
    session.add(elsewhere)
    session.flush()
    stranger = User(
        household_id=elsewhere.id,
        email="stranger@example.com",
        display_name="Stranger",
        password_hash=hash_password(PASSWORD),
        role=Role.OWNER,
    )
    groceries = SpendingCategory(
        household_id=elsewhere.id, name="Groceries", kind=CategoryKind.EXPENSE, position=0
    )
    session.add_all([stranger, groceries])
    session.flush()
    session.add(
        SpendingLine(
            household_id=elsewhere.id,
            day=date(2026, 10, 9),
            label="theirs",
            amount=Decimal("-999.00"),
            category_id=groceries.id,
            entered_by_id=stranger.id,
        )
    )
    session.commit()
    assert _report(owner_client, "2026-10", "2026-10")["totals"]["spent"] == "400.00"


@pytest.mark.parametrize(
    ("start", "end"),
    [
        ("2026-10", "2026-09"),
        ("2016-01", "2026-10"),
        ("2026-13", "2026-10"),
        ("2027-01", "2027-02"),
    ],
)
def test_an_impossible_period_is_refused(owner_client: TestClient, start: str, end: str) -> None:
    response = owner_client.get("/api/spending/report", params={"start": start, "end": end})
    assert response.status_code == 422


def test_a_report_never_disagrees_with_the_months(owner_client: TestClient) -> None:
    """Invariant 18: a period's figures are the sums of its months', its rows its sections'."""
    _two_months(owner_client)
    report = _report(owner_client, "2026-09", "2026-10")
    months = [
        owner_client.get("/api/spending/month", params={"month": m}).json()["figures"]
        for m in ("2026-09", "2026-10")
    ]
    for key in ("income", "spent", "saved", "rest"):
        assert Decimal(report["totals"][key]) == sum(Decimal(m[key]) for m in months)
    for section in report["sections"]:
        rows = [Decimal(r["amount"]) for r in report["rows"] if r["section"] == section["section"]]
        assert sum(rows) == Decimal(section["amount"])
