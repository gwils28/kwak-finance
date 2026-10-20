"""Financial goals funded by wealth lines (F-GOAL)."""

from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from kwak_api.models import User

from tests.api.conftest import Clock, csrf, log_in
from tests.api.wealth.test_wealth import _line, _value

TODAY = datetime(2026, 10, 20, 12, tzinfo=UTC)


@pytest.fixture
def owner_client(client: TestClient, clock: Clock, owner: User) -> TestClient:
    clock.now = TODAY
    log_in(client, clock)
    return client


def _post(client: TestClient, **fields: Any) -> Any:
    body = {
        "name": "Voyage au Japon",
        "tier": "medium",
        "target": "6000.00",
        "deadline": "2027-08",
        "visibility": "shared",
        "fundings": [],
    } | fields
    return client.post("/api/goals", json=body, headers=csrf(client))


def _goal(client: TestClient, **fields: Any) -> dict[str, Any]:
    response = _post(client, **fields)
    assert response.status_code == 201, response.text
    goal: dict[str, Any] = response.json()
    return goal


def _goals(client: TestClient, **params: str) -> dict[str, Any]:
    response = client.get("/api/goals", params=params)
    assert response.status_code == 200, response.text
    goals: dict[str, Any] = response.json()
    return goals


def _livret(client: TestClient, visibility: str = "shared") -> str:
    line = _line(client, "Savings accounts", "Livret A", visibility)
    for month, amount in (("2026-08", "800.00"), ("2026-09", "1000.00"), ("2026-10", "1200.00")):
        assert _value(client, line, month, amount).status_code == 204
    return line


def test_a_goal_follows_the_values_of_the_lines_that_fund_it(owner_client: TestClient) -> None:
    livret = _livret(owner_client)
    created = _goal(owner_client, start="2026-08", fundings=[{"line_id": livret, "share": 50}])
    assert created["fundings"] == [{"line_id": livret, "line_name": "Livret A", "share": 50}]

    [goal] = _goals(owner_client)["goals"]
    assert goal["start"] == "2026-08"
    assert (goal["value"], goal["remaining"], goal["months_left"]) == ("600.00", "5400.00", 10)
    # 400 to 600 over 2 months: 100 a month; 5400 / 10 months left = 540 required
    assert (goal["actual"], goal["required"]) == ("100.00", "540.00")
    assert (goal["estimated"], goal["never"], goal["months_early"]) == ("2031-04", False, -44)
    assert goal["status"] == "behind"
    assert goal["owner_name"] == "Owner"

    detail = owner_client.get(f"/api/goals/{goal['id']}").json()
    assert [(m["month"], m["value"], m["gained"]) for m in detail["months"]] == [
        ("2026-08", "400.00", None),
        ("2026-09", "500.00", "100.00"),
        ("2026-10", "600.00", "100.00"),
    ]
    assert detail["months"][0]["expected"] == "400.00"


def test_the_start_defaults_to_this_month(owner_client: TestClient) -> None:
    assert _goal(owner_client)["start"] == "2026-10"


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ({"deadline": None}, "deadline"),
        ({"deadline": "2026-09"}, "deadline"),
        ({"start": "2026-11"}, "start"),
        ({"target": "0"}, "target"),
    ],
)
def test_a_goal_breaking_a_rule_is_refused(
    owner_client: TestClient, fields: dict[str, Any], message: str
) -> None:
    response = _post(owner_client, **fields)
    assert response.status_code == 422
    assert message in response.text


def test_a_deadline_outside_the_tiers_horizon_is_flagged(owner_client: TestClient) -> None:
    assert _goal(owner_client, deadline="2027-03")["horizon_flagged"] is True
    assert _goal(owner_client, name="Voiture", deadline="2028-10")["horizon_flagged"] is False


def test_a_lines_shares_never_exceed_100_percent(owner_client: TestClient) -> None:
    livret = _livret(owner_client)
    first = _goal(owner_client, fundings=[{"line_id": livret, "share": 60}])
    response = _post(owner_client, name="Été", fundings=[{"line_id": livret, "share": 41}])
    assert response.status_code == 409
    # closing a goal frees its shares
    closed = owner_client.patch(
        f"/api/goals/{first['id']}",
        json={"closed_from": "2026-10", "closed_as": "abandoned"},
        headers=csrf(owner_client),
    )
    assert closed.status_code == 200, closed.text
    _goal(owner_client, name="Été", fundings=[{"line_id": livret, "share": 41}])
    reopened = owner_client.patch(
        f"/api/goals/{first['id']}", json={"closed_from": None}, headers=csrf(owner_client)
    )
    assert reopened.status_code == 409


def test_closed_goals_leave_the_pyramid(owner_client: TestClient) -> None:
    goal = _goal(owner_client)
    owner_client.patch(
        f"/api/goals/{goal['id']}",
        json={"closed_from": "2026-10", "closed_as": "reached"},
        headers=csrf(owner_client),
    )
    goals = _goals(owner_client)
    assert goals["goals"] == []
    [closed] = goals["closed"]
    assert (closed["closed_from"], closed["closed_as"]) == ("2026-10", "reached")
    medium = next(t for t in goals["pyramid"] if t["tier"] == "medium")
    assert (medium["target"], medium["progress"]) == ("0.00", None)


def test_a_goal_is_closed_with_how_it_ended(owner_client: TestClient) -> None:
    goal = _goal(owner_client)
    response = owner_client.patch(
        f"/api/goals/{goal['id']}", json={"closed_from": "2026-10"}, headers=csrf(owner_client)
    )
    assert response.status_code == 422


def test_a_goal_uses_its_owners_lines_and_joint_ones(
    client: TestClient, clock: Clock, member: User
) -> None:
    clock.now = TODAY
    log_in(client, clock, "member@example.com")
    theirs = _line(client, "Stocks", "PEA du membre")
    log_in(client, clock)
    loan = _line(client, "Debts", "Prêt")
    private = _line(client, "Savings accounts", "LDDS", "private")
    joint = _line(client, "Savings accounts", "Compte joint", "joint")

    def funded(line: str, **fields: Any) -> int:
        status: int = _post(client, fundings=[{"line_id": line, "share": 10}], **fields).status_code
        return status

    assert funded(theirs) == 422  # a member's line, even shared
    assert funded(loan) == 422  # a debt
    assert funded(private) == 422  # would show a private line's value to the household
    assert funded(private, visibility="private") == 201
    assert funded(joint, name="Commun", visibility="joint") == 201
    assert funded(theirs, name="Commun 2", visibility="joint") == 422


def test_a_line_funding_a_visible_goal_cannot_turn_private(owner_client: TestClient) -> None:
    livret = _livret(owner_client)
    _goal(owner_client, fundings=[{"line_id": livret, "share": 100}])
    response = owner_client.patch(
        f"/api/wealth/lines/{livret}", json={"visibility": "private"}, headers=csrf(owner_client)
    )
    assert response.status_code == 409


def test_one_open_precaution_per_member(owner_client: TestClient) -> None:
    body = {"name": "Précaution", "tier": "precaution", "deadline": None}
    assert _post(owner_client, **body).status_code == 201
    assert _post(owner_client, **body).status_code == 409
    assert _post(owner_client, **body | {"visibility": "joint"}).status_code == 201


def test_a_member_sees_shared_goals_not_private_ones(
    client: TestClient, clock: Clock, member: User
) -> None:
    clock.now = TODAY
    log_in(client, clock)
    private = _goal(client, name="Secret", visibility="private")
    _goal(client, name="Voyage")
    log_in(client, clock, "member@example.com")
    assert [g["name"] for g in _goals(client)["goals"]] == ["Voyage"]
    assert _goals(client, scope="mine")["goals"] == []
    assert client.get(f"/api/goals/{private['id']}").status_code == 404
    shared = _goals(client)["goals"][0]["id"]
    assert (
        client.patch(
            f"/api/goals/{shared}", json={"name": "Japon"}, headers=csrf(client)
        ).status_code
        == 200
    )
    assert client.delete(f"/api/goals/{shared}", headers=csrf(client)).status_code == 403


def test_deleting_a_goal_is_logged_and_keeps_its_lines(owner_client: TestClient) -> None:
    livret = _livret(owner_client)
    goal = _goal(owner_client, fundings=[{"line_id": livret, "share": 100}])
    response = owner_client.delete(f"/api/goals/{goal['id']}", headers=csrf(owner_client))
    assert response.status_code == 204
    assert _goals(owner_client)["goals"] == []
    assert [line["id"] for line in owner_client.get("/api/wealth/lines").json()] == [livret]
    entry = owner_client.get("/api/audit").json()["items"][0]
    assert (entry["action"], entry["details"]["name"]) == ("goal_deleted", "Voyage au Japon")


def test_the_effort_plan_fills_the_precaution_first(owner_client: TestClient) -> None:
    settings = owner_client.patch(
        "/api/household/settings",
        json={"goal_capacity": "1350.00", "precaution_share": "0.70"},
        headers=csrf(owner_client),
    )
    assert settings.status_code == 200, settings.text
    precaution = _goal(owner_client, name="Précaution", tier="precaution", target="2300.00")
    japan = _goal(owner_client, target="2900.00")  # 290 a month over 10 months
    plan = _goals(owner_client)["plan"]
    assert (plan["capacity"], plan["capacity_set"], plan["precaution_share"]) == (
        "1350.00",
        True,
        "0.70",
    )
    assert (plan["months_to_fill"], plan["unallocated"]) == (3, "0.00")
    # 945 first, then 1350 - 945 - 290 = 115 the others leave
    efforts = {g["id"]: g["effort"] for g in _goals(owner_client)["goals"]}
    assert efforts == {precaution["id"]: "1060.00", japan["id"]: "290.00"}
    assert plan["shortfall"] == "0.00"


def _checking(client: TestClient) -> str:
    body = {
        "name": "Courant",
        "institution_name": "SG",
        "type": "checking",
        "visibility": "shared",
        "opening_balance": "0",
        "opening_date": "2026-01-01",
    }
    response = client.post("/api/accounts", json=body, headers=csrf(client))
    assert response.status_code == 201, response.text
    account: str = response.json()["id"]
    return account


def test_the_capacity_is_the_average_net_cash_flow(owner_client: TestClient) -> None:
    account = _checking(owner_client)
    for day, amount in (("2026-09-02", "2000.00"), ("2026-09-10", "-800.00")):
        body = {"account_id": account, "booked_on": day, "amount": amount, "label": "x"}
        response = owner_client.post("/api/transactions", json=body, headers=csrf(owner_client))
        assert response.status_code == 201, response.text
    plan = _goals(owner_client)["plan"]
    assert (plan["capacity"], plan["capacity_set"]) == ("1200.00", False)


@pytest.mark.parametrize(
    "body", [{"precaution_share": "0.40"}, {"precaution_share": "1.10"}, {"goal_capacity": "-1"}]
)
def test_goal_settings_are_checked(owner_client: TestClient, body: dict[str, str]) -> None:
    response = owner_client.patch("/api/household/settings", json=body, headers=csrf(owner_client))
    assert response.status_code == 422


def test_the_precaution_proposal_counts_months_of_fixed_expenses(
    owner_client: TestClient,
) -> None:
    account = _checking(owner_client)
    for label, amount, frequency in (
        ("Loyer", "-900.00", "monthly"),
        ("Assurance", "-600.00", "yearly"),
        ("Salaire", "2500.00", "monthly"),
    ):
        body = {
            "account_id": account,
            "label": label,
            "amount": amount,
            "frequency": frequency,
            "day": 5,
            "start_on": "2026-01-05",
        }
        response = owner_client.post("/api/recurring", json=body, headers=csrf(owner_client))
        assert response.status_code == 201, response.text
    proposal = owner_client.get("/api/goals/precaution-proposal", params={"months": 6}).json()
    assert (proposal["monthly_fixed"], proposal["amount"]) == ("950.00", "5700.00")
    assert [(i["label"], i["monthly"]) for i in proposal["items"]] == [
        ("Assurance", "50.00"),
        ("Loyer", "900.00"),
    ]
    response = owner_client.get("/api/goals/precaution-proposal", params={"months": 13})
    assert response.status_code == 422
