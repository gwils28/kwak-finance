from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from kwak_api.models import User

from tests.api.conftest import Clock, csrf, log_in

TODAY = datetime(2026, 12, 10, 12, tzinfo=UTC)


@pytest.fixture
def owner_client(client: TestClient, clock: Clock, owner: User) -> TestClient:
    clock.now = TODAY
    log_in(client, clock)
    return client


def _categories(client: TestClient) -> dict[str, Any]:
    return {c["name"]: c for c in client.get("/api/wealth/categories").json()}


def _line(client: TestClient, category: str, name: str, visibility: str = "shared") -> str:
    body = {
        "category_id": _categories(client)[category]["id"],
        "name": name,
        "visibility": visibility,
    }
    response = client.post("/api/wealth/lines", json=body, headers=csrf(client))
    assert response.status_code == 201, response.text
    line: str = response.json()["id"]
    return line


def _value(client: TestClient, line: str, month: str, amount: str) -> Any:
    return client.put(
        f"/api/wealth/lines/{line}/values/{month}", json={"amount": amount}, headers=csrf(client)
    )


def _matrix(client: TestClient, **params: str) -> Any:
    response = client.get("/api/wealth/matrix", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def test_a_new_household_has_the_default_categories(owner_client: TestClient) -> None:
    categories = owner_client.get("/api/wealth/categories").json()
    assert [c["name"] for c in categories][:3] == ["Savings accounts", "Current accounts", "Stocks"]
    assert categories[-1] | {"id": None} == {
        "id": None,
        "name": "Debts",
        "kind": "debt",
        "colour": "debts",
        "position": 10,
        "preset": "debts",
    }


def test_values_carry_forward_into_the_matrix(owner_client: TestClient) -> None:
    pea = _line(owner_client, "Stocks", "PEA Fortuneo")
    assert _value(owner_client, pea, "2026-10", "10000.00").status_code == 204
    _value(owner_client, pea, "2026-12", "10600.00")
    loan = _line(owner_client, "Debts", "Prêt auto")
    _value(owner_client, loan, "2026-10", "3000.00")

    m = _matrix(owner_client, start="2026-10", end="2026-12")
    assert m["months"] == ["2026-10", "2026-11", "2026-12"]
    stocks = next(c for c in m["categories"] if c["name"] == "Stocks")
    assert stocks["subtotals"] == ["10000.00", "10000.00", "10600.00"]
    line = stocks["lines"][0]
    assert (line["name"], line["owner_name"]) == ("PEA Fortuneo", "Owner")
    assert set(line) == {
        "id",
        "name",
        "owner_id",
        "owner_name",
        "visibility",
        "closed_from",
        "cells",
        "share",
    }
    assert line["cells"][1] == {"amount": "10000.00", "carried": True}
    assert (m["gross"], m["debts"], m["net"]) == (
        ["10000.00", "10000.00", "10600.00"],
        ["3000.00", "3000.00", "3000.00"],
        ["7000.00", "7000.00", "7600.00"],
    )
    assert m["change"] == [None, "0.00", "600.00"]
    assert stocks["share"] == "1.0000"


def test_bank_accounts_are_lines_entered_by_hand_like_any_other(
    owner_client: TestClient,
) -> None:
    # The categories stay empty until lines are added.
    m = _matrix(owner_client, start="2026-11", end="2026-11")
    assert m["gross"] == ["0.00"]

    livret = _line(owner_client, "Savings accounts", "Livret A")
    _value(owner_client, livret, "2026-11", "5200.00")
    current = _line(owner_client, "Current accounts", "Compte courant")
    _value(owner_client, current, "2026-11", "800.00")
    lines = owner_client.get("/api/wealth/update", params={"month": "2026-12"}).json()
    assert [(x["name"], x["last_value"]) for x in lines] == [
        ("Livret A", "5200.00"),
        ("Compte courant", "800.00"),
    ]
    m = _matrix(owner_client, start="2026-11", end="2026-11")
    subtotals = {c["name"]: c["subtotals"] for c in m["categories"]}
    assert (subtotals["Savings accounts"], subtotals["Current accounts"]) == (
        ["5200.00"],
        ["800.00"],
    )


def test_values_are_positive_cents(owner_client: TestClient) -> None:
    pea = _line(owner_client, "Stocks", "PEA")
    assert _value(owner_client, pea, "2026-11", "-5.00").status_code == 422
    assert _value(owner_client, pea, "2026-11", "1.005").status_code == 422
    assert _value(owner_client, pea, "2026-13", "1.00").status_code == 422


def test_a_value_can_be_removed(owner_client: TestClient) -> None:
    pea = _line(owner_client, "Stocks", "PEA")
    _value(owner_client, pea, "2026-11", "100.00")
    response = owner_client.delete(
        f"/api/wealth/lines/{pea}/values/2026-11", headers=csrf(owner_client)
    )
    assert response.status_code == 204
    m = _matrix(owner_client, start="2026-11", end="2026-11")
    assert m["net"] == ["0.00"]


def test_a_closed_line_leaves_the_later_months(owner_client: TestClient) -> None:
    gold = _line(owner_client, "Gold", "Napoléons")
    _value(owner_client, gold, "2026-10", "800.00")
    response = owner_client.patch(
        f"/api/wealth/lines/{gold}", json={"closed_from": "2026-12"}, headers=csrf(owner_client)
    )
    assert response.status_code == 200, response.text
    m = _matrix(owner_client, start="2026-10", end="2026-12")
    assert m["gross"] == ["800.00", "800.00", "0.00"]
    gold_row = next(c for c in m["categories"] if c["name"] == "Gold")["lines"][0]
    assert gold_row["closed_from"] == "2026-12"


def test_update_this_month_lists_the_open_lines_and_saves_them_at_once(
    owner_client: TestClient,
) -> None:
    pea = _line(owner_client, "Stocks", "PEA")
    _value(owner_client, pea, "2026-11", "1000.00")
    btc = _line(owner_client, "Crypto", "Kraken")

    lines = owner_client.get("/api/wealth/update", params={"month": "2026-12"}).json()
    assert [(x["name"], x["last_value"]) for x in lines] == [("PEA", "1000.00"), ("Kraken", None)]

    body = {
        "month": "2026-12",
        "values": [{"line_id": pea, "amount": "1100.00"}, {"line_id": btc, "amount": "250.00"}],
    }
    response = owner_client.post("/api/wealth/update", json=body, headers=csrf(owner_client))
    assert response.status_code == 204, response.text
    assert _matrix(owner_client, start="2026-12", end="2026-12")["gross"] == ["1350.00"]


def _wealth_start(client: TestClient, month: str | None) -> Any:
    return client.patch(
        "/api/household/settings", json={"wealth_start": month}, headers=csrf(client)
    )


def test_the_default_window_is_the_last_12_months_from_the_wealth_start(
    owner_client: TestClient,
) -> None:
    assert len(_matrix(owner_client)["months"]) == 12
    _wealth_start(owner_client, "2026-10")
    assert _matrix(owner_client)["months"] == ["2026-10", "2026-11", "2026-12"]


def test_the_wealth_start_is_set_logged_and_cleared(owner_client: TestClient) -> None:
    response = _wealth_start(owner_client, "2026-01")
    assert response.status_code == 200, response.text
    assert response.json()["wealth_start"] == "2026-01"
    months = _matrix(owner_client)["months"]
    assert (months[0], months[-1], len(months)) == ("2026-01", "2026-12", 12)
    entry = owner_client.get("/api/audit", params={"kind": "household"}).json()["items"]
    assert {"wealth_start": "2026-01"} in [e["details"] for e in entry]

    # Without a start, the last 12 months.
    assert _wealth_start(owner_client, None).json()["wealth_start"] is None
    assert len(_matrix(owner_client)["months"]) == 12
    # Any window can still be asked for, earlier months included.
    assert _matrix(owner_client, start="2025-06", end="2025-07")["months"] == [
        "2025-06",
        "2025-07",
    ]


@pytest.mark.parametrize("month", ["2027-01", "2026-13", "1899-12"])
def test_a_bad_or_future_wealth_start_is_rejected(owner_client: TestClient, month: str) -> None:
    assert _wealth_start(owner_client, month).status_code == 422


def test_only_the_owner_sets_the_wealth_start(
    client: TestClient, clock: Clock, owner: User, member: User
) -> None:
    clock.now = TODAY
    log_in(client, clock, "member@example.com")
    assert _wealth_start(client, "2026-01").status_code == 403


def test_categories_are_managed(owner_client: TestClient) -> None:
    response = owner_client.post(
        "/api/wealth/categories",
        json={"name": "Montres", "kind": "asset", "colour": "exotic"},
        headers=csrf(owner_client),
    )
    assert response.status_code == 201, response.text
    watches = response.json()
    assert watches["position"] == 11
    owner_client.patch(
        f"/api/wealth/categories/{watches['id']}", json={"position": 0}, headers=csrf(owner_client)
    )
    assert [c["name"] for c in owner_client.get("/api/wealth/categories").json()][:2] == [
        "Montres",
        "Savings accounts",
    ]

    _line(owner_client, "Montres", "Rolex")
    response = owner_client.delete(
        f"/api/wealth/categories/{watches['id']}", headers=csrf(owner_client)
    )
    assert response.status_code == 409  # it holds a line
    dup = owner_client.post(
        "/api/wealth/categories",
        json={"name": "montres", "colour": "gold"},
        headers=csrf(owner_client),
    )
    assert dup.status_code == 409


def test_a_line_and_its_values_can_be_deleted_by_its_owner_and_it_is_logged(
    owner_client: TestClient,
) -> None:
    pea = _line(owner_client, "Stocks", "PEA")
    _value(owner_client, pea, "2026-11", "100.00")
    assert (
        owner_client.delete(f"/api/wealth/lines/{pea}", headers=csrf(owner_client)).status_code
        == 204
    )
    entry = owner_client.get("/api/audit", params={"kind": "deletion"}).json()["items"][0]
    assert (entry["action"], entry["details"]) == (
        "wealth_line_deleted",
        {"name": "PEA", "category": "Stocks"},
    )


def test_scopes_and_private_lines(
    client: TestClient, clock: Clock, owner: User, member: User
) -> None:
    clock.now = TODAY
    log_in(client, clock, "member@example.com")
    private = _line(client, "Stocks", "PEA perso", "private")
    _value(client, private, "2026-12", "100.00")
    shared = _line(client, "Gold", "Or", "shared")
    _value(client, shared, "2026-12", "10.00")
    joint = _line(client, "Real estate", "Maison", "joint")
    _value(client, joint, "2026-12", "1000.00")
    assert _matrix(client, start="2026-12", end="2026-12", scope="mine")["gross"] == ["110.00"]
    assert _matrix(client, start="2026-12", end="2026-12", scope="joint")["gross"] == ["1000.00"]

    log_in(client, clock)
    assert _matrix(client, start="2026-12", end="2026-12")["gross"] == ["1010.00"]
    assert _value(client, private, "2026-12", "1.00").status_code == 404
    # Anyone who sees a line updates its value; only its owner changes who sees it.
    assert _value(client, shared, "2026-12", "12.00").status_code == 204
    response = client.patch(
        f"/api/wealth/lines/{shared}", json={"visibility": "private"}, headers=csrf(client)
    )
    assert response.status_code == 403
    assert client.delete(f"/api/wealth/lines/{shared}", headers=csrf(client)).status_code == 403


@pytest.mark.parametrize(
    ("start", "end"), [("2026-12", "2026-10"), ("2010-01", "2026-12"), ("2026-13", "2026-13")]
)
def test_a_bad_window_is_rejected(owner_client: TestClient, start: str, end: str) -> None:
    assert (
        owner_client.get("/api/wealth/matrix", params={"start": start, "end": end}).status_code
        == 422
    )


def test_wealth_requires_a_full_sign_in(client: TestClient) -> None:
    assert client.get("/api/wealth/matrix").status_code == 401


def test_deleting_a_private_line_is_logged_for_its_owner_only(
    client: TestClient, clock: Clock, owner: User, member: User
) -> None:
    clock.now = TODAY
    log_in(client, clock, "member@example.com")
    private = _line(client, "Stocks", "Assurance-vie X", "private")
    client.delete(f"/api/wealth/lines/{private}", headers=csrf(client))
    assert client.get("/api/audit", params={"kind": "deletion"}).json()["total"] == 1

    log_in(client, clock)
    assert client.get("/api/audit", params={"kind": "deletion"}).json()["total"] == 0


def test_a_private_line_is_hidden_from_other_members_everywhere(
    client: TestClient, clock: Clock, owner: User, member: User
) -> None:
    clock.now = TODAY
    log_in(client, clock, "member@example.com")
    private = _line(client, "Stocks", "Perso", "private")
    _value(client, private, "2026-12", "100.00")

    log_in(client, clock)
    mine = _line(client, "Gold", "Or")
    h = csrf(client)
    assert (
        client.patch(f"/api/wealth/lines/{private}", json={"name": "x"}, headers=h).status_code
        == 404
    )
    assert (
        client.delete(f"/api/wealth/lines/{private}/values/2026-12", headers=h).status_code == 404
    )
    assert client.delete(f"/api/wealth/lines/{private}", headers=h).status_code == 404
    assert private not in [x["id"] for x in client.get("/api/wealth/lines").json()]
    assert private not in [x["line_id"] for x in client.get("/api/wealth/update").json()]
    lines = [ln["id"] for c in _matrix(client)["categories"] for ln in c["lines"]]
    assert private not in lines
    # A batch touching a hidden line saves nothing.
    body = {
        "month": "2026-12",
        "values": [{"line_id": mine, "amount": "5.00"}, {"line_id": private, "amount": "1.00"}],
    }
    assert client.post("/api/wealth/update", json=body, headers=h).status_code == 404
    assert _matrix(client, start="2026-12", end="2026-12")["gross"] == ["0.00"]


@pytest.mark.parametrize("amount", ["1e100000", "1e20", "-0.01"])
def test_an_impossible_amount_is_rejected(owner_client: TestClient, amount: str) -> None:
    pea = _line(owner_client, "Stocks", "PEA")
    assert _value(owner_client, pea, "2026-11", amount).status_code == 422
    body = {"month": "2026-11", "values": [{"line_id": pea, "amount": amount}]}
    response = owner_client.post("/api/wealth/update", json=body, headers=csrf(owner_client))
    assert response.status_code == 422


def test_blank_names_and_unknown_colours_are_rejected(owner_client: TestClient) -> None:
    stocks = _categories(owner_client)["Stocks"]["id"]
    h = csrf(owner_client)
    body = {"category_id": stocks, "name": "   "}
    assert owner_client.post("/api/wealth/lines", json=body, headers=h).status_code == 422
    assert (
        owner_client.patch(
            f"/api/wealth/categories/{stocks}", json={"name": " "}, headers=h
        ).status_code
        == 422
    )
    body = {"name": "Montres", "colour": "fuchsia"}
    assert owner_client.post("/api/wealth/categories", json=body, headers=h).status_code == 422


def test_a_category_holding_someone_elses_private_line_stays(
    client: TestClient, clock: Clock, owner: User, member: User
) -> None:
    clock.now = TODAY
    log_in(client, clock, "member@example.com")
    _line(client, "Crypto", "Ledger", "private")
    log_in(client, clock)
    crypto = _categories(client)["Crypto"]["id"]
    assert (
        client.delete(f"/api/wealth/categories/{crypto}", headers=csrf(client)).status_code == 409
    )


def test_lines_live_in_categories_of_this_household(owner_client: TestClient) -> None:
    h = csrf(owner_client)
    body = {"category_id": "00000000-0000-0000-0000-000000000000", "name": "X"}
    assert owner_client.post("/api/wealth/lines", json=body, headers=h).status_code == 422
    pea = _line(owner_client, "Stocks", "PEA")
    move = {"category_id": "00000000-0000-0000-0000-000000000000"}
    assert owner_client.patch(f"/api/wealth/lines/{pea}", json=move, headers=h).status_code == 422
    unknown = "/api/wealth/categories/00000000-0000-0000-0000-000000000000"
    assert owner_client.patch(unknown, json={"name": "X"}, headers=h).status_code == 404
    assert owner_client.delete(unknown, headers=h).status_code == 404


def test_renaming_to_a_taken_name_and_moving_past_the_end(owner_client: TestClient) -> None:
    h = csrf(owner_client)
    gold = _categories(owner_client)["Gold"]["id"]
    response = owner_client.patch(
        f"/api/wealth/categories/{gold}", json={"name": "STOCKS"}, headers=h
    )
    assert response.status_code == 409
    owner_client.patch(f"/api/wealth/categories/{gold}", json={"position": 99}, headers=h)
    names = [c["name"] for c in owner_client.get("/api/wealth/categories").json()]
    assert names[-1] == "Gold"
    assert [c["position"] for c in owner_client.get("/api/wealth/categories").json()] == list(
        range(11)
    )


def test_deleting_an_empty_category_is_logged(owner_client: TestClient) -> None:
    exotic = _categories(owner_client)["Exotic"]["id"]
    assert (
        owner_client.delete(
            f"/api/wealth/categories/{exotic}", headers=csrf(owner_client)
        ).status_code
        == 204
    )
    entry = owner_client.get("/api/audit", params={"kind": "deletion"}).json()["items"][0]
    assert (entry["action"], entry["details"]) == ("wealth_category_deleted", {"name": "Exotic"})


def test_a_debt_counts_against_net_worth_and_shares_are_of_gross_assets(
    owner_client: TestClient,
) -> None:
    pea, gold, loan = (
        _line(owner_client, c, n) for c, n in (("Stocks", "PEA"), ("Gold", "Or"), ("Debts", "Prêt"))
    )
    for line, nov, dec in (
        (pea, "600.00", "750.00"),
        (gold, "200.00", "250.00"),
        (loan, "300.00", "200.00"),
    ):
        _value(owner_client, line, "2026-11", nov)
        _value(owner_client, line, "2026-12", dec)
    m = _matrix(owner_client, start="2026-11", end="2026-12")
    assert m["net"] == ["500.00", "800.00"]
    assert (m["change"], m["change_ratio"]) == ([None, "300.00"], [None, "0.6000"])
    shares = {c["name"]: c["share"] for c in m["categories"]}
    assert (shares["Stocks"], shares["Gold"], shares["Debts"]) == ("0.7500", "0.2500", None)


def test_a_closed_month_takes_no_value_and_the_matrix_stops_this_month(
    owner_client: TestClient,
) -> None:
    gold = _line(owner_client, "Gold", "Or")
    owner_client.patch(
        f"/api/wealth/lines/{gold}", json={"closed_from": "2026-11"}, headers=csrf(owner_client)
    )
    assert _value(owner_client, gold, "2026-11", "1.00").status_code == 422
    assert (
        owner_client.get(
            "/api/wealth/matrix", params={"start": "2026-12", "end": "2027-01"}
        ).status_code
        == 422
    )


def test_a_batch_with_a_bad_amount_saves_nothing(owner_client: TestClient) -> None:
    pea, gold = _line(owner_client, "Stocks", "PEA"), _line(owner_client, "Gold", "Or")
    body = {
        "month": "2026-12",
        "values": [{"line_id": pea, "amount": "5.00"}, {"line_id": gold, "amount": "-1"}],
    }
    assert (
        owner_client.post("/api/wealth/update", json=body, headers=csrf(owner_client)).status_code
        == 422
    )
    assert _matrix(owner_client, start="2026-12", end="2026-12")["gross"] == ["0.00"]


def _patch_line(client: TestClient, line: str, **fields: Any) -> Any:
    return client.patch(f"/api/wealth/lines/{line}", json=fields, headers=csrf(client))


def test_a_savings_line_can_have_a_regulated_type(owner_client: TestClient) -> None:
    body = {
        "category_id": _categories(owner_client)["Savings accounts"]["id"],
        "name": "Livret A",
        "visibility": "private",
        "regulated_type": "livret_a",
    }
    response = owner_client.post("/api/wealth/lines", json=body, headers=csrf(owner_client))
    assert response.status_code == 201, response.text
    line = response.json()
    assert line["regulated_type"] == "livret_a"
    changed = _patch_line(owner_client, line["id"], regulated_type="ldds")
    assert changed.json()["regulated_type"] == "ldds"
    cleared = _patch_line(owner_client, line["id"], regulated_type=None)
    assert cleared.json()["regulated_type"] is None
    plain = _line(owner_client, "Savings accounts", "Livret bancaire")
    assert (
        next(x for x in owner_client.get("/api/wealth/lines").json() if x["id"] == plain)[
            "regulated_type"
        ]
        is None
    )


def test_a_regulated_type_needs_a_personal_savings_line(owner_client: TestClient) -> None:
    categories = _categories(owner_client)

    def create(category: str, visibility: str) -> int:
        body = {
            "category_id": categories[category]["id"],
            "name": "x",
            "visibility": visibility,
            "regulated_type": "lep",
        }
        status: int = owner_client.post(
            "/api/wealth/lines", json=body, headers=csrf(owner_client)
        ).status_code
        return status

    assert create("Savings accounts", "joint") == 422
    assert create("Stocks", "shared") == 422
    line = _line(owner_client, "Savings accounts", "LDDS")
    assert _patch_line(owner_client, line, regulated_type="ldds").status_code == 200
    joint = _patch_line(owner_client, line, visibility="joint")
    assert joint.status_code == 422
    assert "joint" in joint.json()["detail"]
    moved = _patch_line(owner_client, line, category_id=categories["Stocks"]["id"])
    assert moved.status_code == 422
    both = _patch_line(owner_client, line, visibility="joint", regulated_type=None)
    assert both.status_code == 200, both.text
    assert (both.json()["visibility"], both.json()["regulated_type"]) == ("joint", None)


def test_only_the_owner_makes_a_regulated_line_joint(
    client: TestClient, clock: Clock, owner: User, member: User
) -> None:
    clock.now = TODAY
    log_in(client, clock)
    line = _line(client, "Savings accounts", "Livret A")
    assert _patch_line(client, line, regulated_type="livret_a").status_code == 200
    log_in(client, clock, "member@example.com")
    assert _patch_line(client, line, visibility="joint").status_code == 403


def test_a_line_moved_into_savings_takes_a_regulated_type_at_once(
    owner_client: TestClient,
) -> None:
    line = _line(owner_client, "Current accounts", "Livret A")
    savings = _categories(owner_client)["Savings accounts"]["id"]
    moved = _patch_line(owner_client, line, category_id=savings, regulated_type="livret_a")
    assert moved.status_code == 200, moved.text
    assert moved.json()["regulated_type"] == "livret_a"
