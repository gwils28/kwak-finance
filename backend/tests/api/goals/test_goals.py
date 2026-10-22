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
    # 400 of the 800 there in August, then half of each rise
    funding = {"line_id": livret, "share": 50, "opening": "400.00"}
    created = _goal(owner_client, start="2026-08", fundings=[funding])
    assert created["fundings"] == [
        {
            "line_id": livret,
            "line_name": "Livret A",
            "share": 50,
            "opening": "400.00",
            "held": "600.00",
            "adjustments": [],
        }
    ]

    [goal] = _goals(owner_client)["goals"]
    assert goal["start"] == "2026-08"
    assert (goal["value"], goal["remaining"], goal["months_left"]) == ("600.00", "5400.00", 10)
    # 400 to 600 over 2 months: 100 a month; 5400 / 10 months left = 540 required
    assert (goal["actual"], goal["required"]) == ("100.00", "540.00")
    assert (goal["estimated"], goal["never"], goal["months_early"]) == ("2031-04", False, -44)
    assert goal["status"] == "behind"
    assert goal["expected"] == "1333.33"  # 400 + 5600 x 2 / 12: where the gauge's marker sits
    assert goal["owner_name"] == "Owner"

    detail = owner_client.get(f"/api/goals/{goal['id']}").json()
    assert [(m["month"], m["value"], m["gained"]) for m in detail["months"]] == [
        ("2026-08", "400.00", None),
        ("2026-09", "500.00", "100.00"),
        ("2026-10", "600.00", "100.00"),
    ]
    assert detail["months"][0]["expected"] == "400.00"


def test_a_goal_keeps_a_line_while_its_envelope_changes(owner_client: TestClient) -> None:
    livret = _livret(owner_client)
    goal = _goal(owner_client, fundings=[{"line_id": livret, "share": 100}])
    response = owner_client.patch(
        f"/api/goals/{goal['id']}",
        json={"fundings": [{"line_id": livret, "share": 40, "opening": "100.00"}]},
        headers=csrf(owner_client),
    )
    assert response.status_code == 200, response.text
    [funding] = response.json()["fundings"]
    assert (funding["share"], funding["opening"]) == (40, "100.00")


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


def test_the_tier_follows_the_deadline(owner_client: TestClient, clock: Clock) -> None:
    trip = _goal(owner_client, name="Été", deadline="2027-03")
    assert (trip["tier"], trip["precaution"]) == ("short", False)
    car = _goal(owner_client, name="Voiture", deadline="2028-10")
    assert car["tier"] == "medium"
    house = _goal(owner_client, name="Maison", deadline="2032-01")
    assert house["tier"] == "long"
    # a later deadline moves the goal up a tier
    moved = owner_client.patch(
        f"/api/goals/{car['id']}", json={"deadline": "2033-01"}, headers=csrf(owner_client)
    )
    assert moved.json()["tier"] == "long"
    # and time brings it down
    clock.now = TODAY.replace(year=2027, month=2)  # 59 months before the deadline
    log_in(owner_client, clock)
    assert owner_client.get(f"/api/goals/{house['id']}").json()["goal"]["tier"] == "medium"


def test_a_lines_shares_never_exceed_100_percent(owner_client: TestClient) -> None:
    livret = _livret(owner_client)
    first = _goal(owner_client, fundings=[{"line_id": livret, "share": 60}])
    response = _post(owner_client, name="Été", fundings=[{"line_id": livret, "share": 41}])
    assert response.status_code == 409
    # it says how much is left to share out
    assert response.json()["detail"] == (
        "Livret A would fund open goals beyond 100 %: 40 % of its rises left"
    )
    # closing a goal frees its shares
    closed = owner_client.patch(
        f"/api/goals/{first['id']}",
        json={"closed_from": "2026-10", "closed_as": "cancelled"},
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
        json={"closed_from": "2026-10", "closed_as": "archived"},
        headers=csrf(owner_client),
    )
    goals = _goals(owner_client)
    assert goals["goals"] == []
    [closed] = goals["closed"]
    assert (closed["closed_from"], closed["closed_as"]) == ("2026-10", "archived")
    medium = next(t for t in goals["pyramid"] if t["tier"] == "medium")
    assert (medium["target"], medium["progress"]) == ("0.00", None)


def test_a_goal_archives_itself_once_reached_unless_permanent(owner_client: TestClient) -> None:
    livret = _livret(owner_client)  # 1200 in October
    trip = _goal(owner_client, name="Été", target="500.00", deadline="2027-06")
    fund = _goal(
        owner_client, name="Fonds travaux", target="1000.00", permanent=True, deadline=None
    )
    for goal in (trip, fund):
        owner_client.patch(
            f"/api/goals/{goal['id']}",
            json={"fundings": [{"line_id": livret, "share": 50, "opening": "600.00"}]},
            headers=csrf(owner_client),
        )
    assert [g["name"] for g in _goals(owner_client)["goals"]] == ["Fonds travaux"]
    owner_client.patch(
        f"/api/goals/{fund['id']}", json={"target": "600.00"}, headers=csrf(owner_client)
    )
    goals = _goals(owner_client)
    # the permanent goal stays in view at 100 %
    [kept] = goals["goals"]
    assert (kept["name"], kept["permanent"], kept["status"]) == ("Fonds travaux", True, "reached")
    # the other is archived from next month, so this month still counts
    [archived] = goals["closed"]
    assert (archived["name"], archived["closed_as"], archived["closed_from"]) == (
        "Été",
        "archived",
        "2026-11",
    )
    assert archived["value"] == "500.00"  # never beyond its target
    # reopened as it is, it would archive itself again
    url = f"/api/goals/{archived['id']}"
    refused = owner_client.patch(url, json={"closed_from": None}, headers=csrf(owner_client))
    assert refused.status_code == 422
    assert "target" in refused.text
    reopened = owner_client.patch(
        url, json={"closed_from": None, "target": "2000.00"}, headers=csrf(owner_client)
    )
    assert reopened.status_code == 200, reopened.text
    assert reopened.json()["closed_as"] is None


def test_each_line_shows_what_the_goals_set_aside(owner_client: TestClient) -> None:
    livret = _livret(owner_client)  # 1200 in October
    _goal(owner_client, fundings=[{"line_id": livret, "share": 100, "opening": "300.00"}])
    response = owner_client.get("/api/goals/lines")
    assert response.status_code == 200, response.text
    assert response.json() == [
        {
            "line_id": livret,
            "line_name": "Livret A",
            "worth": "1200.00",
            "set_aside": "300.00",
            "free": "900.00",
        }
    ]


def test_a_permanent_goal_needs_no_deadline_and_the_precaution_is_one(
    owner_client: TestClient,
) -> None:
    fund = _goal(owner_client, name="Fonds travaux", permanent=True, deadline=None)
    assert (fund["tier"], fund["status"], fund["deadline"]) == ("short", "open", None)
    precaution = _goal(owner_client, name="Précaution", precaution=True, deadline=None)
    assert (precaution["permanent"], precaution["tier"]) == (True, "precaution")
    # the foundation of the pyramid, under its three tiers
    tiers = [t["tier"] for t in _goals(owner_client)["pyramid"]]
    assert tiers == ["precaution", "short", "medium", "long"]
    response = owner_client.patch(
        f"/api/goals/{precaution['id']}", json={"permanent": False}, headers=csrf(owner_client)
    )
    assert response.status_code == 422


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
    body = {"name": "Précaution", "precaution": True, "deadline": None}
    assert _post(owner_client, **body).status_code == 201
    assert _post(owner_client, **body).status_code == 409
    # other short-term goals are not the precaution
    assert _post(owner_client, name="Été", deadline="2027-06").status_code == 201
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
    precaution = _goal(
        owner_client,
        name="Précaution",
        precaution=True,
        deadline=None,
        target="2300.00",
    )
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


def _spending_categories(client: TestClient) -> dict[str, str]:
    return {c["name"]: c["id"] for c in client.get("/api/spending/categories").json()}


def test_the_capacity_is_the_average_income_minus_spending(owner_client: TestClient) -> None:
    categories = _spending_categories(owner_client)
    response = owner_client.put(
        "/api/spending/income/2026-09", json={"amount": "2000.00"}, headers=csrf(owner_client)
    )
    assert response.status_code == 200, response.text
    for category, amount in (("Groceries", "-800.00"), ("Savings", "-500.00")):
        body = {
            "day": "2026-09-10",
            "label": "x",
            "amount": amount,
            "category_id": categories[category],
        }
        response = owner_client.post("/api/spending/lines", json=body, headers=csrf(owner_client))
        assert response.status_code == 201, response.text
    plan = _goals(owner_client)["plan"]
    # Savings lines stay in: they are what goals are funded from.
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
    categories = _spending_categories(owner_client)
    for label, category, amount, frequency, paused in (
        ("Loyer", "Housing", "-900.00", "monthly", False),
        ("Assurance", "Home", "-600.00", "yearly", False),
        ("Livret", "Savings", "-200.00", "monthly", False),  # put aside, not spent
        ("Salle", "Leisure", "-30.00", "monthly", True),  # paused
    ):
        body = {
            "label": label,
            "category_id": categories[category],
            "amount": amount,
            "frequency": frequency,
            "day": 5,
            "first_month": "2026-01",
            "paused": paused,
        }
        response = owner_client.post("/api/spending/fixed", json=body, headers=csrf(owner_client))
        assert response.status_code == 201, response.text
    proposal = owner_client.get("/api/goals/precaution-proposal", params={"months": 6}).json()
    assert (proposal["monthly_fixed"], proposal["amount"]) == ("950.00", "5700.00")
    assert [(i["label"], i["monthly"]) for i in proposal["items"]] == [
        ("Assurance", "50.00"),
        ("Loyer", "900.00"),
    ]
    response = owner_client.get("/api/goals/precaution-proposal", params={"months": 13})
    assert response.status_code == 422


def test_an_envelope_is_adjusted_by_hand_and_the_adjustment_removed(
    owner_client: TestClient,
) -> None:
    livret = _livret(owner_client)  # 800, 1000, 1200 from August
    goal = _goal(owner_client, start="2026-08", fundings=[{"line_id": livret, "share": 100}])
    assert goal["value"] == "400.00"  # both rises
    url = f"/api/goals/{goal['id']}/envelopes/{livret}/2026-09"
    response = owner_client.put(url, json={"amount": "50.00"}, headers=csrf(owner_client))
    assert response.status_code == 200, response.text
    adjusted = response.json()
    # 50 from September, then October's rise of 200
    assert adjusted["goal"]["value"] == "250.00"
    [funding] = adjusted["goal"]["fundings"]
    assert funding["adjustments"] == [{"month": "2026-09", "amount": "50.00"}]
    # it survives an edit of the goal's fundings
    owner_client.patch(
        f"/api/goals/{goal['id']}",
        json={"fundings": [{"line_id": livret, "share": 100}]},
        headers=csrf(owner_client),
    )
    assert owner_client.get(f"/api/goals/{goal['id']}").json()["goal"]["value"] == "250.00"
    assert owner_client.delete(url, headers=csrf(owner_client)).status_code == 204
    assert owner_client.get(f"/api/goals/{goal['id']}").json()["goal"]["value"] == "400.00"


@pytest.mark.parametrize(
    ("path", "status"),
    [
        ("{line}/2026-07", 422),  # before the goal's start
        ("{line}/2026-11", 422),  # a month to come
        ("{other}/2026-09", 404),  # a line that does not fund it
    ],
)
def test_an_adjustment_stays_within_the_goals_months_and_lines(
    owner_client: TestClient, path: str, status: int
) -> None:
    livret = _livret(owner_client)
    other = _line(owner_client, "Savings accounts", "LDDS")
    goal = _goal(owner_client, start="2026-08", fundings=[{"line_id": livret, "share": 100}])
    url = f"/api/goals/{goal['id']}/envelopes/" + path.format(line=livret, other=other)
    response = owner_client.put(url, json={"amount": "50.00"}, headers=csrf(owner_client))
    assert response.status_code == status
