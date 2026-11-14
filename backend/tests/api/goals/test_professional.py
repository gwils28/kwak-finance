"""Professional goals: in their tier, their cost less what others pay, equipment renewed
(F-GOAL-11, invariants §8.51-52)."""

from datetime import UTC, datetime
from typing import Any

from fastapi.testclient import TestClient
from kwak_api.models import User

from tests.api.conftest import Clock, csrf, log_in
from tests.api.goals.test_goals import TODAY, _goal, _goals, _livret, _post, owner_client
from tests.api.wealth.test_wealth import _value

__all__ = ["owner_client"]

CPF = {"source": "cpf", "amount": "1500.00", "received": False}


def _pro(client: TestClient, **fields: Any) -> dict[str, Any]:
    body = {
        "name": "Certification cloud",
        "target": None,
        "pro_type": "training",
        "cost": "2400.00",
        "deadline": "2027-09",
    } | fields
    return _goal(client, **body)


def _patch(client: TestClient, goal: str, **fields: Any) -> Any:
    return client.patch(f"/api/goals/{goal}", json=fields, headers=csrf(client))


def test_a_professional_goals_target_is_its_cost_less_what_others_pay(
    owner_client: TestClient,
) -> None:
    goal = _pro(owner_client, aids=[CPF])
    assert (goal["pro_type"], goal["cost"], goal["target"]) == ("training", "2400.00", "900.00")
    assert goal["aids"] == [CPF]
    assert (goal["tier"], goal["renew_years"], goal["renewal_monthly"]) == ("short", None, None)
    changed = _patch(owner_client, goal["id"], cost="3000.00", target="1.00")
    assert changed.status_code == 200, changed.text
    assert changed.json()["target"] == "1500.00"  # the target follows the cost, never sent
    dropped = _patch(owner_client, goal["id"], aids=[]).json()
    assert dropped["target"] == "3000.00"


def test_what_others_pay_is_checked(owner_client: TestClient) -> None:
    too_much = _post(
        owner_client,
        target=None,
        pro_type="training",
        cost="1000.00",
        aids=[CPF | {"amount": "1000.00"}],
    )
    assert too_much.status_code == 422
    equipment_cpf = _post(
        owner_client,
        target=None,
        pro_type="equipment",
        cost="2000.00",
        aids=[CPF],
    )
    assert equipment_cpf.status_code == 422
    assert "CPF" in equipment_cpf.text
    no_cost = _post(owner_client, target=None, pro_type="training")
    assert no_cost.status_code == 422
    no_deadline = _post(owner_client, target=None, pro_type="move", cost="900.00", deadline=None)
    assert no_deadline.status_code == 422
    pleasure = _post(owner_client, pro_type="move", cost="900.00", pleasure=True, deadline=None)
    assert pleasure.status_code == 422
    renew_training = _post(owner_client, pro_type="training", cost="900.00", renew_years=4)
    assert renew_training.status_code == 422
    standard_without_target = _post(owner_client, target=None)
    assert standard_without_target.status_code == 422


def test_a_tiers_professional_part_is_shown(owner_client: TestClient) -> None:
    livret = _livret(owner_client)  # 1200 in October
    _pro(
        owner_client,
        name="PC",
        pro_type="equipment",
        cost="1800.00",
        fundings=[{"line_id": livret, "share": 50, "opening": "600.00"}],
    )
    _goal(owner_client, name="Vacances", target="1200.00", deadline="2027-06")
    tiers = {t["tier"]: t for t in _goals(owner_client)["pyramid"]}
    assert tiers["short"]["progress"] == "0.2000"
    assert tiers["short"]["professional"] == "0.2000"
    assert tiers["medium"]["professional"] is None


def test_turning_a_professional_goal_into_another_kind_drops_its_cost(
    owner_client: TestClient,
) -> None:
    goal = _pro(owner_client, aids=[CPF])
    plain = _patch(owner_client, goal["id"], pro_type=None).json()
    assert (plain["pro_type"], plain["cost"], plain["aids"], plain["target"]) == (
        None,
        None,
        [],
        "900.00",
    )


def _equipment(client: TestClient, livret: str, **fields: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "name": "PC portable",
        "pro_type": "equipment",
        "cost": "1000.00",
        "renew_years": 4,
        "deadline": "2027-03",
        "fundings": [{"line_id": livret, "share": 100, "opening": "1000.00"}],
    }
    return _pro(client, **(body | fields))


def test_equipment_to_renew_keeps_its_money_once_reached_until_bought(
    owner_client: TestClient, clock: Clock
) -> None:
    livret = _livret(owner_client)  # 1200 in October
    pc = _equipment(owner_client, livret)
    assert pc["renewal_monthly"] == "20.83"
    [kept] = _goals(owner_client)["goals"]
    # reached, it stays open and holds its money for the purchase
    assert (kept["status"], kept["closed_from"], kept["value"]) == ("reached", None, "1000.00")
    lines = {x["line_id"]: x for x in owner_client.get("/api/goals/lines").json()}
    assert lines[livret]["free"] == "200.00"

    # Bought in October: archived by hand from November, the next cycle starts then
    archived = _patch(owner_client, pc["id"], closed_from="2026-11", closed_as="archived")
    assert archived.status_code == 200, archived.text
    clock.now = datetime(2026, 11, 3, 12, tzinfo=UTC)
    log_in(owner_client, clock)
    assert _value(owner_client, livret, "2026-11", "300.00").status_code == 204
    goals = _goals(owner_client)
    [nxt] = goals["goals"]
    assert (nxt["name"], nxt["start"], nxt["deadline"]) == ("PC portable", "2026-11", "2031-03")
    assert (nxt["cost"], nxt["target"], nxt["aids"], nxt["renew_years"]) == (
        "1000.00",
        "1000.00",
        [],
        4,
    )
    assert nxt["fundings"][0]["opening"] == "0.00"
    assert nxt["value"] == "0.00"
    entry = owner_client.get("/api/audit").json()["items"][0]
    assert (entry["action"], entry["details"]) == (
        "goal_renewed",
        {"name": "PC portable", "deadline": "2031-03"},
    )
    # a cycle renews one goal at most, however often the page is read
    assert len(_goals(owner_client)["goals"]) == 1


def test_a_goal_to_renew_archives_itself_at_its_deadline(
    owner_client: TestClient, clock: Clock
) -> None:
    livret = _livret(owner_client)
    _equipment(owner_client, livret, deadline="2026-11")
    clock.now = datetime(2026, 11, 5, 12, tzinfo=UTC)
    log_in(owner_client, clock)
    [archived] = _goals(owner_client)["closed"]
    assert (archived["closed_as"], archived["closed_from"]) == ("archived", "2026-12")
    clock.now = datetime(2026, 12, 5, 12, tzinfo=UTC)
    log_in(owner_client, clock)
    [nxt] = _goals(owner_client)["goals"]
    assert (nxt["start"], nxt["deadline"]) == ("2026-12", "2030-11")


def test_archived_by_hand_without_a_next_cycle_or_cancelled_starts_none(
    owner_client: TestClient, clock: Clock
) -> None:
    livret = _livret(owner_client)
    pc = _equipment(owner_client, livret, name="PC")
    chair = _equipment(owner_client, livret, name="Fauteuil", fundings=[])
    _patch(owner_client, pc["id"], closed_from="2026-10", closed_as="archived", next_cycle=False)
    _patch(owner_client, chair["id"], closed_from="2026-10", closed_as="cancelled")
    clock.now = datetime(2026, 12, 5, 12, tzinfo=UTC)
    log_in(owner_client, clock)
    goals = _goals(owner_client)
    assert goals["goals"] == []
    # the setting is kept: only the next cycle is declined
    assert {g["name"]: g["renew_years"] for g in goals["closed"]} == {"PC": 4, "Fauteuil": 4}


def test_a_cycle_renewed_on_a_members_read_is_logged_for_its_owner(
    client: TestClient, clock: Clock, member: User, owner: User
) -> None:
    clock.now = TODAY
    log_in(client, clock)
    livret = _livret(client, "private")
    pc = _equipment(client, livret, visibility="private")
    _patch(client, pc["id"], closed_from="2026-11", closed_as="archived")
    clock.now = datetime(2026, 11, 3, 12, tzinfo=UTC)
    log_in(client, clock, "member@example.com")
    assert _goals(client)["goals"] == []  # the member's read starts the owner's cycle
    assert all(e["action"] != "goal_renewed" for e in client.get("/api/audit").json()["items"])
    log_in(client, clock)
    [nxt] = _goals(client)["goals"]
    assert (nxt["name"], nxt["visibility"], nxt["start"]) == ("PC portable", "private", "2026-11")
    [entry] = [e for e in client.get("/api/audit").json()["items"] if e["action"] == "goal_renewed"]
    assert entry["user_name"] == "Owner"


def test_a_next_cycle_never_funds_a_line_beyond_100_percent(
    owner_client: TestClient, clock: Clock
) -> None:
    livret = _livret(owner_client)
    pc = _equipment(owner_client, livret)
    _patch(owner_client, pc["id"], closed_from="2026-11", closed_as="archived")
    # the PC's share is free from November: another goal takes it all
    _goal(
        owner_client,
        name="Vacances",
        target="5000.00",
        fundings=[{"line_id": livret, "share": 100}],
    )
    clock.now = datetime(2026, 11, 3, 12, tzinfo=UTC)
    log_in(owner_client, clock)
    nxt = next(g for g in _goals(owner_client)["goals"] if g["name"] == "PC portable")
    assert nxt["fundings"] == []
    holiday = next(g for g in _goals(owner_client)["goals"] if g["name"] == "Vacances")
    assert _patch(owner_client, holiday["id"], name="Été").status_code == 200


def test_a_deleted_next_cycle_never_comes_back_and_its_goal_stays_closed(
    owner_client: TestClient, clock: Clock
) -> None:
    livret = _livret(owner_client)
    pc = _equipment(owner_client, livret)
    _patch(owner_client, pc["id"], closed_from="2026-11", closed_as="archived")
    clock.now = datetime(2026, 11, 3, 12, tzinfo=UTC)
    log_in(owner_client, clock)
    [nxt] = _goals(owner_client)["goals"]
    # a goal whose next cycle has started cannot be reopened
    refused = _patch(owner_client, pc["id"], closed_from=None)
    assert refused.status_code == 422
    assert "next cycle" in refused.text
    assert (
        owner_client.delete(f"/api/goals/{nxt['id']}", headers=csrf(owner_client)).status_code
        == 204
    )
    assert _goals(owner_client)["goals"] == []
    # nor once reopened and archived again: a goal starts one next cycle over its life
    assert _patch(owner_client, pc["id"], closed_from=None).status_code == 422
    assert _goals(owner_client)["goals"] == []
    renewals = [
        e for e in owner_client.get("/api/audit").json()["items"] if e["action"] == "goal_renewed"
    ]
    assert len(renewals) == 1


def test_a_goal_archived_with_no_next_cycle_renews_again_once_reopened(
    owner_client: TestClient, clock: Clock
) -> None:
    livret = _livret(owner_client)
    pc = _equipment(owner_client, livret, cost="5000.00")  # short of its target
    _patch(owner_client, pc["id"], closed_from="2026-11", closed_as="archived", next_cycle=False)
    reopened = _patch(owner_client, pc["id"], closed_from=None)
    assert reopened.status_code == 200, reopened.text
    _patch(owner_client, pc["id"], closed_from="2026-11", closed_as="archived")
    clock.now = datetime(2026, 11, 3, 12, tzinfo=UTC)
    log_in(owner_client, clock)
    assert [g["name"] for g in _goals(owner_client)["goals"]] == ["PC portable"]


def test_a_reached_professional_goal_reopens_with_a_higher_cost(owner_client: TestClient) -> None:
    livret = _livret(owner_client)
    goal = _pro(
        owner_client,
        pro_type="move",
        cost="600.00",
        fundings=[{"line_id": livret, "share": 50, "opening": "600.00"}],
    )
    [closed] = _goals(owner_client)["closed"]
    refused = _patch(owner_client, goal["id"], closed_from=None)
    assert refused.status_code == 422
    assert "cost" in refused.text
    reopened = _patch(owner_client, goal["id"], closed_from=None, cost="2000.00")
    assert reopened.status_code == 200, reopened.text
    assert closed["id"] == goal["id"]


def test_only_a_professional_goal_has_a_cost_aids_or_a_renewal(owner_client: TestClient) -> None:
    assert _post(owner_client, renew_years=4).status_code == 422
    assert _post(owner_client, cost="900.00").status_code == 422
    goal = _goal(owner_client)
    assert _patch(owner_client, goal["id"], aids=[CPF]).status_code == 422


def test_changing_a_professional_goals_type_keeps_its_rules(owner_client: TestClient) -> None:
    livret = _livret(owner_client)
    pc = _equipment(owner_client, livret, fundings=[])
    # renewal stays on: training is never renewed
    assert _patch(owner_client, pc["id"], pro_type="training").status_code == 422
    training = _pro(owner_client, aids=[CPF])
    assert _patch(owner_client, training["id"], pro_type="move").status_code == 422
    # the target follows the cost even when only a target is sent
    kept = _patch(owner_client, training["id"], target="50.00").json()
    assert (kept["cost"], kept["target"]) == ("2400.00", "900.00")


def test_a_next_cycle_leaves_out_a_line_that_can_no_longer_fund_it(
    owner_client: TestClient, clock: Clock
) -> None:
    livret = _livret(owner_client)
    pc = _equipment(owner_client, livret)
    _patch(owner_client, pc["id"], closed_from="2026-11", closed_as="archived")
    debts = next(
        c["id"] for c in owner_client.get("/api/wealth/categories").json() if c["kind"] == "debt"
    )
    moved = owner_client.patch(
        f"/api/wealth/lines/{livret}", json={"category_id": debts}, headers=csrf(owner_client)
    )
    assert moved.status_code == 200, moved.text
    clock.now = datetime(2026, 11, 3, 12, tzinfo=UTC)
    log_in(owner_client, clock)
    [nxt] = _goals(owner_client)["goals"]
    assert nxt["fundings"] == []


def test_a_members_private_cycle_stays_hidden_from_the_owner_who_starts_it(
    client: TestClient, clock: Clock, member: User, owner: User
) -> None:
    clock.now = TODAY
    log_in(client, clock, "member@example.com")
    livret = _livret(client, "private")
    pc = _equipment(client, livret, visibility="private")
    _patch(client, pc["id"], closed_from="2026-11", closed_as="archived")
    clock.now = datetime(2026, 11, 3, 12, tzinfo=UTC)
    log_in(client, clock)  # the household's owner reads first
    goals = _goals(client)
    assert goals["goals"] == []
    assert goals["closed"] == []
    assert all(t["target"] == "0.00" for t in goals["pyramid"])
    assert all(e["action"] != "goal_renewed" for e in client.get("/api/audit").json()["items"])
    log_in(client, clock, "member@example.com")
    [nxt] = _goals(client)["goals"]
    assert nxt["visibility"] == "private"
    log_in(client, clock)
    assert client.get(f"/api/goals/{nxt['id']}").status_code == 404
