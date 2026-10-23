"""The goals' Analysis tab (spec §4.12)."""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from kwak_api.models import User

from tests.api.conftest import Clock, csrf, log_in
from tests.api.goals.test_goals import TODAY, _goal
from tests.api.wealth.test_wealth import _line, _value


@pytest.fixture
def owner_client(client: TestClient, clock: Clock, owner: User) -> TestClient:
    clock.now = TODAY
    log_in(client, clock)
    return client


def _analysis(client: TestClient, **params: str) -> dict[str, Any]:
    response = client.get("/api/goals/analysis", params=params)
    assert response.status_code == 200, response.text
    out: dict[str, Any] = response.json()
    return out


def _points(client: TestClient, **params: str) -> list[tuple[str, str | None]]:
    points = _analysis(client, **params)["points"]
    return [(p["rule"], p["goal_name"]) for p in [*points["shown"], *points["more"]]]


def _capacity(client: TestClient, amount: str) -> None:
    response = client.patch(
        "/api/household/settings", json={"goal_capacity": amount}, headers=csrf(client)
    )
    assert response.status_code == 200, response.text


def _livret(client: TestClient, months: tuple[str, ...], name: str = "Livret A") -> str:
    line = _line(client, "Savings accounts", name)
    for k, month in enumerate(months):
        assert _value(client, line, month, f"{1000 + 100 * k}.00").status_code == 204
    return line


def _hide(client: TestClient, action: str, **key: str) -> int:
    response = client.post(
        "/api/goals/analysis/hidden", json={"action": action, **key}, headers=csrf(client)
    )
    status: int = response.status_code
    return status


def test_an_empty_household_is_asked_for_a_precaution_and_more_history(
    owner_client: TestClient,
) -> None:
    out = _analysis(owner_client)
    assert (out["month"], out["reference"], out["capacity_months"]) == ("2026-10", None, 0)
    assert [(p["rule"], p["lines"], p["hideable"]) for p in out["points"]["shown"]] == [
        ("data", [], False),
        ("precaution_none", [], False),
    ]
    assert out["forward"]["months"][:2] == ["2026-10", "2026-11"]
    assert len(out["forward"]["months"]) == 24
    assert out["timeline"] == out["statuses"] == []


def test_the_reference_month_waits_for_every_funding_line(owner_client: TestClient) -> None:
    _capacity(owner_client, "300.00")
    full = _livret(owner_client, ("2026-08", "2026-09", "2026-10"))
    late = _livret(owner_client, ("2026-08", "2026-09"), "LDDS")
    _goal(
        owner_client,
        name="Japon",
        start="2026-08",
        fundings=[{"line_id": full, "share": 50}, {"line_id": late, "share": 50}],
    )
    out = _analysis(owner_client)
    assert out["reference"] == "2026-09"
    [row] = out["statuses"]
    assert [m["month"] for m in row["months"]] == ["2026-08", "2026-09"]
    assert ("data", None) not in _points(owner_client)  # September is entered

    assert _value(owner_client, late, "2026-10", "1300.00").status_code == 204
    assert _analysis(owner_client)["reference"] == "2026-10"


def test_a_line_left_behind_is_a_point_to_update(owner_client: TestClient) -> None:
    _capacity(owner_client, "300.00")
    line = _livret(owner_client, ("2026-07", "2026-08"))
    _goal(owner_client, start="2026-08", fundings=[{"line_id": line, "share": 100}])
    [data] = [p for p in _analysis(owner_client)["points"]["shown"] if p["rule"] == "data"]
    assert data["lines"] == [{"line_id": line, "name": "Livret A"}]


def test_required_efforts_against_the_capacity(owner_client: TestClient) -> None:
    _capacity(owner_client, "250.00")
    line = _livret(owner_client, ("2026-09", "2026-10"))
    near = _goal(owner_client, name="Été", target="1200.00", deadline="2027-10", fundings=[])
    far = _goal(
        owner_client,
        name="Voiture",
        target="6000.00",
        deadline="2029-04",
        fundings=[{"line_id": line, "share": 100}],
        start="2026-10",
    )
    out = _analysis(owner_client, horizon="36")
    forward = out["forward"]
    assert [(b["name"], b["amount"], b["months"]) for b in forward["bands"]] == [
        ("Été", "100.00", 12),
        ("Voiture", "200.00", 30),
    ]
    assert forward["totals"][0] == "300.00"
    assert (forward["over"], forward["peak"]) == (12, "50.00")
    [over] = [p for p in out["points"]["shown"] if p["rule"] == "overcommitted"]
    assert over["severity"] == "warning"
    assert over["amount"] == "50.00"
    first = over["postponements"][0]
    assert (first["goal_id"], first["months"], first["deadline"]) == (far["id"], 10, "2030-02")
    assert near["id"] in {p["goal_id"] for p in over["postponements"]}
    [unfunded] = [p for p in _analysis(owner_client)["points"]["shown"] if p["rule"] == "unfunded"]
    assert unfunded["goal_name"] == "Été"


def test_the_horizon_is_12_to_60_months(owner_client: TestClient) -> None:
    assert owner_client.get("/api/goals/analysis", params={"horizon": 6}).status_code == 422


def test_the_timeline_dates_a_goal_at_its_pace_and_at_the_plan(owner_client: TestClient) -> None:
    _capacity(owner_client, "300.00")
    line = _livret(owner_client, ("2026-07", "2026-08", "2026-09", "2026-10"))
    _goal(
        owner_client,
        name="Japon",
        target="2000.00",
        start="2026-07",
        deadline="2027-07",
        fundings=[{"line_id": line, "share": 100}],
    )
    [bar] = _analysis(owner_client)["timeline"]
    # It took the rises only: 300 in 3 months, 1700 left; 17 months at 100 a month, while the
    # plan gives it its required 188.89 a month, which keeps the deadline.
    assert (bar["start"], bar["deadline"], bar["estimated"]) == ("2026-07", "2027-07", "2028-03")
    assert (bar["enough_history"], bar["never"], bar["at_plan"]) == (True, False, "2027-07")


def test_a_snoozed_point_is_the_viewers_own(
    client: TestClient, clock: Clock, owner: User, member: User
) -> None:
    clock.now = TODAY
    log_in(client, clock)
    _capacity(client, "300.00")
    goal = _goal(client, name="Été", deadline="2027-06", fundings=[])
    key = {"rule": "unfunded", "goal_id": goal["id"]}
    assert _hide(client, "snooze", **key) == 204
    assert ("unfunded", "Été") not in _points(client)
    assert _hide(client, "snooze", **key) == 204  # again: still one choice

    log_in(client, clock, "member@example.com")
    assert ("unfunded", "Été") in _points(client)

    log_in(client, clock)
    clock.now = TODAY.replace(month=11)
    log_in(client, clock)
    assert ("unfunded", "Été") in _points(client)  # back the next reference month


def test_a_dismissed_point_stays_hidden_until_restored(owner_client: TestClient) -> None:
    _capacity(owner_client, "300.00")
    goal = _goal(owner_client, name="Été", deadline="2027-06", fundings=[])
    assert _hide(owner_client, "dismiss", rule="unfunded", goal_id=goal["id"]) == 204
    assert ("unfunded", "Été") not in _points(owner_client)
    response = owner_client.delete("/api/goals/analysis/hidden", headers=csrf(owner_client))
    assert response.status_code == 204
    assert ("unfunded", "Été") in _points(owner_client)


def test_only_a_point_shown_and_hideable_can_be_hidden(owner_client: TestClient) -> None:
    assert _hide(owner_client, "dismiss", rule="precaution_none") == 404  # never hidden
    assert _hide(owner_client, "dismiss", rule="behind") == 404  # not there


def test_a_member_never_sees_a_private_goal_in_the_analysis(
    client: TestClient, clock: Clock, owner: User, member: User
) -> None:
    clock.now = TODAY
    log_in(client, clock)
    secret = _goal(client, name="Secret", visibility="private", deadline="2027-06", fundings=[])
    log_in(client, clock, "member@example.com")
    out = _analysis(client)
    assert out["timeline"] == []
    assert all(b["goal_id"] != secret["id"] for b in out["forward"]["bands"])
    assert _hide(client, "dismiss", rule="unfunded", goal_id=secret["id"]) == 404


def test_a_private_funded_goal_changes_nothing_another_member_sees(
    client: TestClient, clock: Clock, owner: User, member: User
) -> None:
    clock.now = TODAY
    log_in(client, clock, "member@example.com")
    before = _analysis(client)
    log_in(client, clock)
    _capacity(client, "50.00")
    secret = _line(client, "Savings accounts", "LDDS", "private")
    assert _value(client, secret, "2026-08", "100.00").status_code == 204  # stale in October
    _goal(
        client,
        name="Secret",
        visibility="private",
        target="9000.00",
        deadline="2027-06",
        start="2026-08",
        fundings=[{"line_id": secret, "share": 100}],
    )
    assert ("overcommitted", None) in _points(client)

    log_in(client, clock, "member@example.com")
    after = _analysis(client)
    assert after["reference"] == before["reference"]
    assert after["forward"]["totals"] == before["forward"]["totals"]
    assert (after["forward"]["over"], after["forward"]["peak"]) == (0, "0.00")
    points = [*after["points"]["shown"], *after["points"]["more"]]
    assert all(p["rule"] != "overcommitted" and p["lines"] == [] for p in points)


def test_hiding_a_point_needs_the_csrf_token(owner_client: TestClient) -> None:
    goal = _goal(owner_client, name="Été", deadline="2027-06", fundings=[])
    body = {"action": "dismiss", "rule": "unfunded", "goal_id": goal["id"]}
    assert owner_client.post("/api/goals/analysis/hidden", json=body).status_code == 403
    assert owner_client.delete("/api/goals/analysis/hidden").status_code == 403


def test_showing_hidden_points_again_is_the_viewers_own(
    client: TestClient, clock: Clock, owner: User, member: User
) -> None:
    clock.now = TODAY
    log_in(client, clock)
    _capacity(client, "300.00")
    goal = _goal(client, name="Été", deadline="2027-06", fundings=[])
    assert _hide(client, "dismiss", rule="unfunded", goal_id=goal["id"]) == 204
    log_in(client, clock, "member@example.com")
    assert client.delete("/api/goals/analysis/hidden", headers=csrf(client)).status_code == 204
    log_in(client, clock)
    assert ("unfunded", "Été") not in _points(client)


def test_a_goal_created_this_month_keeps_last_months_reference(owner_client: TestClient) -> None:
    _capacity(owner_client, "300.00")
    line = _livret(owner_client, ("2026-08", "2026-09"))
    _goal(owner_client, name="Neuf", deadline="2027-10", fundings=[{"line_id": line, "share": 100}])
    out = _analysis(owner_client)
    assert out["reference"] == "2026-09"  # October is not entered yet: no stale point
    assert ("data", None) not in _points(owner_client)
    [bar] = out["timeline"]
    assert (bar["start"], bar["enough_history"]) == ("2026-10", False)
    [row] = out["statuses"]
    assert [m["month"] for m in row["months"]] == ["2026-10"]  # judged at its start


def test_a_pleasure_goal_has_no_date_at_the_plan(owner_client: TestClient) -> None:
    _capacity(owner_client, "300.00")
    line = _livret(owner_client, ("2026-09", "2026-10"))
    _goal(
        owner_client,
        name="Rhum",
        pleasure=True,
        deadline=None,
        target="120.00",
        fundings=[{"line_id": line, "share": 10}],
    )
    [bar] = _analysis(owner_client)["timeline"]
    assert (bar["name"], bar["at_plan"]) == ("Rhum", None)


def test_the_capacity_views_take_the_households_goals_in_every_scope(
    owner_client: TestClient,
) -> None:
    _capacity(owner_client, "100.00")
    mine = _livret(owner_client, ("2026-09", "2026-10"))
    joint = _line(owner_client, "Savings accounts", "Compte joint", "joint")
    assert _value(owner_client, joint, "2026-09", "500.00").status_code == 204  # not October
    _goal(owner_client, name="Été", deadline="2027-10", fundings=[{"line_id": mine, "share": 100}])
    _goal(
        owner_client,
        name="Maison",
        visibility="joint",
        target="2400.00",
        deadline="2028-10",
        fundings=[{"line_id": joint, "share": 100}],
    )
    for scope in ("household", "mine", "joint"):
        out = _analysis(owner_client, scope=scope)
        assert out["forward"]["reference"] == "2026-09"
        assert [b["name"] for b in out["forward"]["bands"]] == ["Été", "Maison"]
    mine_only = _analysis(owner_client, scope="mine")
    assert mine_only["reference"] == "2026-10"
    assert [b["name"] for b in mine_only["timeline"]] == ["Été"]
    assert _analysis(owner_client, scope="joint")["reference"] == "2026-09"
