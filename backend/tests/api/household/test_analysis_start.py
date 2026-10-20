from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from kwak_api.models import User

from tests.api.conftest import Clock, csrf, log_in
from tests.api.dashboard.test_dashboard import _setup
from tests.api.recurring.test_recurring import _account, _add


@pytest.fixture
def owner_client(client: TestClient, clock: Clock, owner: User) -> TestClient:
    clock.now = datetime(2026, 10, 14, 12, tzinfo=UTC)
    log_in(client, clock)
    return client


def _start(client: TestClient, month: str | None) -> Any:
    return client.patch(
        "/api/household/settings", json={"analysis_start": month}, headers=csrf(client)
    )


def test_the_owner_sets_and_clears_the_analysis_start(owner_client: TestClient) -> None:
    assert owner_client.get("/api/household/settings").json()["analysis_start"] is None
    response = _start(owner_client, "2026-04")
    assert response.status_code == 200, response.text
    assert response.json() == {
        "warn_at": "0.80",
        "analysis_start": "2026-04",
        "wealth_start": None,
        "precaution_share": "0.70",
        "goal_capacity": None,
    }
    # Changing the threshold alone keeps the start.
    owner_client.patch(
        "/api/household/settings", json={"warn_at": "0.9"}, headers=csrf(owner_client)
    )
    assert owner_client.get("/api/household/settings").json()["analysis_start"] == "2026-04"
    assert _start(owner_client, None).json()["analysis_start"] is None


@pytest.mark.parametrize("month", ["2026-13", "april", "1899-12", "٢٠٢٦-٠٤", "2026-11"])
def test_a_bad_or_future_start_is_rejected(owner_client: TestClient, month: str) -> None:
    assert _start(owner_client, month).status_code == 422


@pytest.mark.usefixtures("member")
def test_only_the_owner_sets_it(client: TestClient, clock: Clock) -> None:
    log_in(client, clock, "member@example.com")
    assert _start(client, "2026-04").status_code == 403


def test_the_overview_counts_nothing_before_the_start(owner_client: TestClient) -> None:
    _setup(owner_client)  # March 2026
    before = owner_client.get("/api/dashboard", params={"month": "2026-04"}).json()["kpis"]
    assert before["previous_spent"] == "1621.04"

    _start(owner_client, "2026-04")
    kpis = owner_client.get("/api/dashboard", params={"month": "2026-04"}).json()["kpis"]
    assert (kpis["previous_spent"], kpis["average_spent"]) == ("0.00", "0.00")
    # The month looked at itself stays whole: only the comparisons leave earlier months out.
    march = owner_client.get("/api/dashboard", params={"month": "2026-03"}).json()
    assert march["kpis"]["spent"] == "1621.04"
    assert march["to_categorise"]["count"] == 10


def test_reports_start_no_earlier_than_the_start(owner_client: TestClient) -> None:
    _setup(owner_client)
    _start(owner_client, "2026-04")

    report = owner_client.get("/api/reports", params={"start": "2026-01", "end": "2026-06"}).json()
    assert (report["start"], report["analysis_start"]) == ("2026-04", "2026-04")
    assert report["totals"]["spent"] == "0.00"
    response = owner_client.get("/api/reports", params={"start": "2026-03", "end": "2026-03"})
    assert response.status_code == 422


def test_recurring_items_are_detected_from_the_start_only(owner_client: TestClient) -> None:
    account = _account(owner_client)
    for day in ("2026-06-04", "2026-07-05", "2026-08-03", "2026-09-04"):
        _add(owner_client, account, day, "-15.99", "Netflix", "Streaming")
    assert len(owner_client.get("/api/recurring/suggestions").json()) == 1

    _start(owner_client, "2026-08")
    assert owner_client.get("/api/recurring/suggestions").json() == []


def test_the_change_is_in_the_activity_log(owner_client: TestClient) -> None:
    _start(owner_client, "2026-10")
    entry = owner_client.get("/api/audit", params={"kind": "household"}).json()["items"][0]
    assert (entry["action"], entry["details"]) == (
        "settings_changed",
        {"analysis_start": "2026-10"},
    )


def test_leaving_it_out_keeps_it_and_clearing_it_is_logged(owner_client: TestClient) -> None:
    _start(owner_client, "2026-10")
    owner_client.patch("/api/household/settings", json={}, headers=csrf(owner_client))
    assert owner_client.get("/api/household/settings").json()["analysis_start"] == "2026-10"
    _start(owner_client, None)
    entry = owner_client.get("/api/audit", params={"kind": "household"}).json()["items"][0]
    assert entry["details"] == {"analysis_start": ""}


@pytest.mark.usefixtures("owner")
def test_members_read_it_and_their_views_follow_it(
    client: TestClient, clock: Clock, member: User
) -> None:
    clock.now = datetime(2026, 10, 14, 12, tzinfo=UTC)
    log_in(client, clock)
    _setup(client)  # a shared account, March 2026
    _start(client, "2026-04")

    log_in(client, clock, "member@example.com")
    assert client.get("/api/household/settings").json()["analysis_start"] == "2026-04"
    kpis = client.get("/api/dashboard", params={"month": "2026-04"}).json()["kpis"]
    assert kpis["previous_spent"] == "0.00"
