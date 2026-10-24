"""The goals' Analysis tab (spec §4.12)."""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from kwak_api.models import User

from tests.api.conftest import Clock, csrf, log_in
from tests.api.goals.test_goals import TODAY, _goal
from tests.api.wealth.test_wealth import _categories, _line, _value


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


def _stocks(client: TestClient) -> str:
    line = _line(client, "Stocks", "PEA")
    for month, amount in (("2026-09", "3000.00"), ("2026-10", "3000.00")):
        assert _value(client, line, month, amount).status_code == 204
    return line


def test_a_near_goal_on_stocks_sits_in_the_red_zone(owner_client: TestClient) -> None:
    _capacity(owner_client, "300.00")
    pea = _stocks(owner_client)
    _goal(
        owner_client,
        name="Voiture",
        target="6000.00",
        deadline="2027-10",
        start="2026-09",
        fundings=[{"line_id": pea, "share": 100, "opening": "3000.00"}],
    )
    out = _analysis(owner_client)
    [point] = out["risk"]
    assert (point["name"], point["months_left"], point["zone"]) == ("Voiture", 12, "red_short")
    assert (point["volatility"], point["risky_share"]) == ("0.1600", "1.0000")
    assert point["real_return"] == "0.0500"  # 7 % less the 2 % inflation
    assert -0.2 < float(point["loss"]) < -0.05
    assert out["inflation"] == "0.0200"
    [risk] = [
        p for p in [*out["points"]["shown"], *out["points"]["more"]] if p["rule"] == "short_risk"
    ]
    assert (risk["severity"], risk["amount"]) == ("warning", "3000.00")
    assert float(risk["figures"]["loss"]) > 0


def test_idle_money_names_the_goal_behind(owner_client: TestClient) -> None:
    categories = {c["name"]: c["id"] for c in owner_client.get("/api/spending/categories").json()}
    for month in ("2026-07", "2026-08", "2026-09"):
        for category, amount in (("Salaries", "2000.00"), ("Groceries", "-1000.00")):
            body = {
                "day": f"{month}-10",
                "label": "x",
                "amount": amount,
                "category_id": categories[category],
            }
            response = owner_client.post(
                "/api/spending/lines", json=body, headers=csrf(owner_client)
            )
            assert response.status_code == 201, response.text
    current = _line(owner_client, "Current accounts", "Compte courant")
    for month in ("2026-09", "2026-10"):
        assert _value(owner_client, current, month, "5000.00").status_code == 204
    livret = _livret(owner_client, ("2026-09", "2026-10"))
    _goal(
        owner_client,
        name="Été",
        target="1200.00",
        deadline="2027-06",
        start="2026-09",
        fundings=[{"line_id": livret, "share": 100}],
    )
    points = [
        *_analysis(owner_client)["points"]["shown"],
        *_analysis(owner_client)["points"]["more"],
    ]
    [idle] = [p for p in points if p["rule"] == "idle"]
    # 5,000 free on the current account, against 2,000 + 1,000 a month
    assert idle["amount"] == "2000.00"


def test_a_far_target_is_indexed_and_capacity_left_over_is_good_news(
    owner_client: TestClient,
) -> None:
    _capacity(owner_client, "2000.00")
    livret = _livret(owner_client, ("2026-09", "2026-10"))
    _goal(
        owner_client,
        name="Études",
        target="30000.00",
        deadline="2036-10",
        start="2026-10",
        fundings=[{"line_id": livret, "share": 100}],
    )
    points = _analysis(owner_client)["points"]
    rules = {p["rule"]: p for p in [*points["shown"], *points["more"]]}
    assert rules["not_indexed"]["figures"]["indexed"] == "36569.83"
    assert rules["left_over"]["severity"] == "good"


def _spending(client: TestClient) -> None:
    categories = {c["name"]: c["id"] for c in client.get("/api/spending/categories").json()}
    for month in ("2026-07", "2026-08", "2026-09"):
        for category, amount in (("Salaries", "2000.00"), ("Groceries", "-1000.00")):
            body = {
                "day": f"{month}-10",
                "label": "x",
                "amount": amount,
                "category_id": categories[category],
            }
            response = client.post("/api/spending/lines", json=body, headers=csrf(client))
            assert response.status_code == 201, response.text


def test_idle_money_never_shows_another_members_private_goal(
    client: TestClient, clock: Clock, owner: User, member: User
) -> None:
    clock.now = TODAY
    log_in(client, clock)
    _spending(client)
    joint = _line(client, "Current accounts", "Compte joint", "joint")
    for month in ("2026-09", "2026-10"):
        assert _value(client, joint, month, "9000.00").status_code == 204
    log_in(client, clock, "member@example.com")
    [before] = [p for p in _all_points(client) if p["rule"] == "idle"]
    log_in(client, clock)
    _goal(
        client,
        name="Secret",
        visibility="private",
        target="5000.00",
        deadline="2027-06",
        start="2026-09",
        fundings=[{"line_id": joint, "share": 100, "opening": "4000.00"}],
    )
    [mine] = [p for p in _all_points(client) if p["rule"] == "idle"]
    assert mine["amount"] == "2000.00"  # 9,000 - 4,000 set aside - 3,000 a month
    log_in(client, clock, "member@example.com")
    [after] = [p for p in _all_points(client) if p["rule"] == "idle"]
    assert after["amount"] == before["amount"] == "6000.00"


def _all_points(client: TestClient) -> list[dict[str, Any]]:
    points = _analysis(client)["points"]
    return [*points["shown"], *points["more"]]


def _regulated(
    client: TestClient, kind: str, amount: str, name: str = "Livret A", visibility: str = "shared"
) -> str:
    body = {
        "category_id": _categories(client)["Savings accounts"]["id"],
        "name": name,
        "visibility": visibility,
        "regulated_type": kind,
    }
    response = client.post("/api/wealth/lines", json=body, headers=csrf(client))
    assert response.status_code == 201, response.text
    line: str = response.json()["id"]
    for month in ("2026-09", "2026-10"):
        assert _value(client, line, month, amount).status_code == 204
    return line


def test_a_livret_near_its_ceiling_is_a_point(owner_client: TestClient) -> None:
    _capacity(owner_client, "300.00")
    full = _regulated(owner_client, "livret_a", "22600.00")
    roomy = _regulated(owner_client, "ldds", "9000.00", "LDDS")
    _goal(
        owner_client,
        name="Japon",
        target="5000.00",
        deadline="2028-10",
        start="2026-09",
        fundings=[{"line_id": full, "share": 50}, {"line_id": roomy, "share": 50}],
    )
    [point] = [p for p in _all_points(owner_client) if p["rule"] == "ceiling"]
    assert (point["severity"], point["line_id"], point["line_name"]) == ("info", full, "Livret A")
    assert (point["goal_id"], point["subject_name"], point["amount"]) == (
        None,
        "Japon",
        "22600.00",
    )
    assert point["figures"] == {"ceiling": "22950.00", "room": "350.00", "regulated": "livret_a"}
    assert _hide(owner_client, "dismiss", rule="ceiling", line_id=full) == 204
    assert "ceiling" not in {p["rule"] for p in _all_points(owner_client)}


def _held_lines(client: TestClient) -> dict[str, str]:
    lines = {}
    for category, name, amount in (
        ("Savings accounts", "Livret", "5000.00"),
        ("Real estate", "Maison", "200000.00"),
        ("Debts", "Crédit", "50000.00"),
    ):
        lines[name] = _line(client, category, name)
        for month in ("2026-09", "2026-10"):
            assert _value(client, lines[name], month, amount).status_code == 204
    lines["PEA"] = _stocks(client)
    return lines


def test_where_the_goals_money_sits(owner_client: TestClient) -> None:
    lines = _held_lines(owner_client)
    japon = _goal(
        owner_client,
        name="Japon",
        start="2026-09",
        fundings=[{"line_id": lines["Livret"], "share": 100, "opening": "2000.00"}],
    )
    _goal(
        owner_client,
        name="Toit",
        start="2026-09",
        target="20000.00",
        fundings=[
            {"line_id": lines["PEA"], "share": 100, "opening": "1000.00"},
            {"line_id": lines["Maison"], "share": 100, "opening": "4000.00"},
        ],
    )
    sankey = _analysis(owner_client)["sankey"]
    assert (sankey["month"], sankey["all_assets"]) == ("2026-10", False)
    assert [(c["name"], c["amount"], c["colour"]) for c in sankey["categories"]] == [
        ("Savings accounts", "5000.00", "savings"),
        ("Stocks", "3000.00", "stocks"),
    ]
    assert [(x["name"], x["amount"], x["free"]) for x in sankey["lines"]] == [
        ("Livret", "5000.00", "3000.00"),
        ("PEA", "3000.00", "2000.00"),
    ]
    assert [(f["name"], f["line_id"], f["amount"]) for f in sankey["flows"]] == [
        ("Japon", lines["Livret"], "2000.00"),
        ("Toit", lines["PEA"], "1000.00"),
    ]
    assert sankey["flows"][0]["goal_id"] == japon["id"]
    assert [(e["name"], e["amount"]) for e in sankey["elsewhere"]] == [("Toit", "4000.00")]

    every = _analysis(owner_client, all_assets="true")["sankey"]
    assert every["all_assets"] is True
    assert [c["name"] for c in every["categories"]] == ["Savings accounts", "Stocks", "Real estate"]
    assert every["elsewhere"] == []
    assert ("Toit", lines["Maison"], "4000.00") in [
        (f["name"], f["line_id"], f["amount"]) for f in every["flows"]
    ]


def test_the_sankey_keeps_another_members_private_goal_in_the_free_part(
    client: TestClient, clock: Clock, owner: User, member: User
) -> None:
    clock.now = TODAY
    log_in(client, clock)
    lines = _held_lines(client)
    hidden_line = _line(client, "Stocks", "Mon CTO", "private")
    for month in ("2026-09", "2026-10"):
        assert _value(client, hidden_line, month, "700.00").status_code == 204
    _goal(
        client,
        name="Secret",
        visibility="private",
        start="2026-09",
        fundings=[{"line_id": lines["Livret"], "share": 100, "opening": "1500.00"}],
    )
    mine = _analysis(client)["sankey"]
    assert [f["name"] for f in mine["flows"]] == ["Secret"]
    log_in(client, clock, "member@example.com")
    theirs = _analysis(client)["sankey"]
    assert theirs["flows"] == theirs["elsewhere"] == []
    assert [(c["name"], c["amount"]) for c in theirs["categories"]] == [
        ("Savings accounts", "5000.00"),
        ("Stocks", "3000.00"),
    ]
    assert [(x["name"], x["free"]) for x in theirs["lines"]] == [
        ("Livret", "5000.00"),
        ("PEA", "3000.00"),
    ]


def test_a_private_livret_near_its_ceiling_stays_its_owners(
    client: TestClient, clock: Clock, owner: User, member: User
) -> None:
    clock.now = TODAY
    log_in(client, clock)
    line = _regulated(client, "livret_a", "22800.00", "Mon livret", "private")
    _goal(
        client,
        name="Secret",
        visibility="private",
        target="30000.00",
        start="2026-09",
        fundings=[{"line_id": line, "share": 100}],
    )
    assert "ceiling" in {p["rule"] for p in _all_points(client)}
    log_in(client, clock, "member@example.com")
    assert "ceiling" not in {p["rule"] for p in _all_points(client)}
    assert "Mon livret" not in client.get("/api/goals/analysis").text


def test_a_goal_across_scopes_adds_up_in_each(owner_client: TestClient) -> None:
    livret = _line(owner_client, "Savings accounts", "Livret")
    joint = _line(owner_client, "Current accounts", "Compte joint", "joint")
    for line in (livret, joint):
        for month in ("2026-09", "2026-10"):
            assert _value(owner_client, line, month, "5000.00").status_code == 204
    _goal(
        owner_client,
        name="Japon",
        start="2026-09",
        fundings=[
            {"line_id": livret, "share": 50, "opening": "2000.00"},
            {"line_id": joint, "share": 50, "opening": "1000.00"},
        ],
    )
    mine = _analysis(owner_client, scope="mine")["sankey"]
    assert [(f["name"], f["amount"]) for f in mine["flows"]] == [("Japon", "2000.00")]
    assert [(e["name"], e["amount"]) for e in mine["elsewhere"]] == [("Japon", "1000.00")]
    joint_view = _analysis(owner_client, scope="joint")["sankey"]
    assert [(f["name"], f["amount"]) for f in joint_view["flows"]] == [("Japon", "1000.00")]
    assert [(e["name"], e["amount"]) for e in joint_view["elsewhere"]] == [("Japon", "2000.00")]


def test_the_sankey_without_goals_and_with_a_closed_line(owner_client: TestClient) -> None:
    livret = _line(owner_client, "Savings accounts", "Livret")
    old = _line(owner_client, "Stocks", "Ancien PEA")
    for line in (livret, old):
        assert _value(owner_client, line, "2026-09", "1000.00").status_code == 204
    response = owner_client.patch(
        f"/api/wealth/lines/{old}", json={"closed_from": "2026-10"}, headers=csrf(owner_client)
    )
    assert response.status_code == 200, response.text
    sankey = _analysis(owner_client)["sankey"]
    assert sankey["month"] == "2026-10"
    assert [(x["name"], x["amount"], x["free"]) for x in sankey["lines"]] == [
        ("Livret", "1000.00", "1000.00")
    ]
    assert sankey["flows"] == sankey["elsewhere"] == []
