"""The wealth projection's assumptions, a household setting any member can change (spec §4.11
F-SIM-1)."""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from kwak_api.models import User

from tests.api.conftest import Clock, csrf, log_in
from tests.api.wealth.test_wealth import TODAY, _categories, _line, _value


@pytest.fixture
def owner_client(client: TestClient, clock: Clock, owner: User) -> TestClient:
    clock.now = TODAY
    log_in(client, clock)
    return client


def _assumptions(client: TestClient) -> dict[str, Any]:
    response = client.get("/api/projection/assumptions")
    assert response.status_code == 200, response.text
    out: dict[str, Any] = response.json()
    return out


def _category(client: TestClient, name: str) -> dict[str, Any]:
    return next(c for c in _assumptions(client)["categories"] if c["name"] == name)


def _set_category(client: TestClient, name: str, ret: str, volatility: str) -> Any:
    category = _categories(client)[name]["id"]
    return client.put(
        f"/api/projection/categories/{category}",
        json={"ret": ret, "volatility": volatility},
        headers=csrf(client),
    )


def _terms(client: TestClient, line: str, **body: str | None) -> Any:
    return client.put(f"/api/projection/debts/{line}", json=body, headers=csrf(client))


def test_a_new_household_projects_with_the_defaults(owner_client: TestClient) -> None:
    out = _assumptions(owner_client)
    assert (out["inflation"], out["default_inflation"]) == ("0.020", "0.020")
    assert [c["name"] for c in out["categories"]][:3] == [
        "Savings accounts",
        "Current accounts",
        "Stocks",
    ]
    assert "Debts" not in {c["name"] for c in out["categories"]}  # debts go by line
    stocks = _category(owner_client, "Stocks")
    assert stocks | {"id": None} == {
        "id": None,
        "name": "Stocks",
        "colour": "stocks",
        "preset": "stocks",
        "ret": "0.070",
        "volatility": "0.160",
        "default_ret": "0.070",
        "default_volatility": "0.160",
        "median_growth": "0.058",
        "own": False,
        "contribution": None,
        "contribution_indexed": True,
    }
    assert _category(owner_client, "Crypto")["median_growth"] == "-0.056"
    assert out["debts"] == []


def test_a_category_takes_its_own_assumption_then_its_default_again(
    owner_client: TestClient,
) -> None:
    assert _set_category(owner_client, "Stocks", "0.065", "0.18").status_code == 200
    stocks = _category(owner_client, "Stocks")
    assert (stocks["ret"], stocks["volatility"], stocks["own"]) == ("0.065", "0.180", True)
    assert stocks["default_ret"] == "0.070"

    category = _categories(owner_client)["Stocks"]["id"]
    response = owner_client.delete(
        f"/api/projection/categories/{category}", headers=csrf(owner_client)
    )
    assert response.status_code == 200, response.text
    assert _category(owner_client, "Stocks")["ret"] == "0.070"
    assert not _category(owner_client, "Stocks")["own"]


@pytest.mark.parametrize(
    ("ret", "volatility"),
    [("0.0655", "0.1"), ("-1", "0"), ("1.001", "0"), ("0.05", "-0.01"), ("0.05", "2.1")],
)
def test_a_category_assumption_out_of_bounds_is_refused(
    owner_client: TestClient, ret: str, volatility: str
) -> None:
    assert _set_category(owner_client, "Stocks", ret, volatility).status_code == 422


def test_a_debt_category_has_no_return(owner_client: TestClient) -> None:
    assert _set_category(owner_client, "Debts", "0.03", "0").status_code == 422


def test_the_inflation_is_set_then_restored(owner_client: TestClient) -> None:
    def put(value: str | None) -> Any:
        return owner_client.put(
            "/api/projection/inflation", json={"inflation": value}, headers=csrf(owner_client)
        )

    assert put("0.025").status_code == 200
    assert _assumptions(owner_client)["inflation"] == "0.025"
    assert put("0.0255").status_code == 422
    assert put("0.21").status_code == 422
    assert put(None).status_code == 200
    assert _assumptions(owner_client)["inflation"] == "0.020"


def test_a_debt_line_gets_its_payment_rate_and_insurance(owner_client: TestClient) -> None:
    loan = _line(owner_client, "Debts", "Prêt immo")
    _value(owner_client, loan, "2026-11", "150000.00")
    [debt] = _assumptions(owner_client)["debts"]
    assert debt | {"id": None} == {
        "id": None,
        "name": "Prêt immo",
        "owner_name": "Owner",
        "visibility": "shared",
        "owed": "150000.00",
        "payment": None,
        "rate": "0.0000",
        "insurance": "0.00",
        "grows": False,
    }
    response = _terms(owner_client, loan, payment="900.00", rate="0.0325", insurance="30.00")
    assert response.status_code == 200, response.text
    [debt] = _assumptions(owner_client)["debts"]
    assert (debt["payment"], debt["rate"], debt["insurance"]) == ("900.00", "0.0325", "30.00")
    assert not debt["grows"]

    _terms(owner_client, loan, payment="400.00", rate="0.0325", insurance="0")
    assert _assumptions(owner_client)["debts"][0]["grows"]  # 406.25 of interest a month
    _terms(owner_client, loan, payment=None, rate="0", insurance="0")
    assert _assumptions(owner_client)["debts"][0]["payment"] is None


@pytest.mark.parametrize(
    "body",
    [
        {"payment": "-1.00", "rate": "0", "insurance": "0"},
        {"payment": "900.001", "rate": "0", "insurance": "0"},
        {"payment": "900.00", "rate": "0.03255", "insurance": "0"},
        {"payment": "900.00", "rate": "1.01", "insurance": "0"},
        {"payment": "900.00", "rate": "0", "insurance": "-5"},
    ],
)
def test_debt_terms_out_of_bounds_are_refused(
    owner_client: TestClient, body: dict[str, str]
) -> None:
    loan = _line(owner_client, "Debts", "Prêt auto")
    assert _terms(owner_client, loan, **body).status_code == 422


def test_only_a_debt_line_has_debt_terms(owner_client: TestClient) -> None:
    livret = _line(owner_client, "Savings accounts", "Livret A")
    assert (
        _terms(owner_client, livret, payment="100.00", rate="0", insurance="0").status_code == 422
    )


def test_closed_debts_are_not_listed(owner_client: TestClient) -> None:
    loan = _line(owner_client, "Debts", "Prêt auto")
    _value(owner_client, loan, "2026-10", "3000.00")
    response = owner_client.patch(
        f"/api/wealth/lines/{loan}", json={"closed_from": "2026-12"}, headers=csrf(owner_client)
    )
    assert response.status_code == 200, response.text
    assert _assumptions(owner_client)["debts"] == []


def test_a_member_changes_the_households_assumptions_but_sees_no_private_debt(
    owner_client: TestClient, clock: Clock, member: User
) -> None:
    private = _line(owner_client, "Debts", "Prêt perso", "private")
    owner_client.post("/api/auth/logout", headers=csrf(owner_client))
    log_in(owner_client, clock, "member@example.com")

    assert _assumptions(owner_client)["debts"] == []
    terms = {"payment": "100.00", "rate": "0", "insurance": "0"}
    assert _terms(owner_client, private, **terms).status_code == 404
    assert _set_category(owner_client, "Gold", "0.04", "0.15").status_code == 200
    assert _category(owner_client, "Gold")["ret"] == "0.040"


def test_changes_are_in_the_activity_log(owner_client: TestClient) -> None:
    _set_category(owner_client, "Stocks", "0.065", "0.18")
    owner_client.put(
        "/api/projection/inflation", json={"inflation": "0.025"}, headers=csrf(owner_client)
    )
    log = owner_client.get("/api/audit").json()
    details = [e["details"] for e in log["items"] if e["action"] == "settings_changed"]
    assert {"inflation": "0.025"} in details
    assert {"category": "Stocks", "ret": "0.065", "volatility": "0.180"} in details


# F-SIM-3: the monthly contributions


def _contributions(client: TestClient, *items: dict[str, Any]) -> Any:
    return client.put(
        "/api/projection/contributions", json={"contributions": list(items)}, headers=csrf(client)
    )


def _item(client: TestClient, name: str, amount: str, **more: Any) -> dict[str, Any]:
    return {"category_id": _categories(client)[name]["id"], "amount": amount, **more}


def test_the_contributions_are_saved_with_the_returns_changed_with_them(
    owner_client: TestClient,
) -> None:
    assert _category(owner_client, "Stocks")["contribution"] is None
    response = _contributions(
        owner_client,
        _item(owner_client, "Stocks", "300.00", ret="0.065"),
        _item(owner_client, "Savings accounts", "150.00", indexed=False),
    )
    assert response.status_code == 200, response.text
    stocks = _category(owner_client, "Stocks")
    assert (stocks["contribution"], stocks["contribution_indexed"]) == ("300.00", True)
    assert (stocks["ret"], stocks["volatility"], stocks["own"]) == ("0.065", "0.160", True)
    livret = _category(owner_client, "Savings accounts")
    assert (livret["contribution"], livret["contribution_indexed"]) == ("150.00", False)
    assert livret["own"] is False  # its return was not changed

    # The list replaces the saved one.
    assert _contributions(owner_client, _item(owner_client, "Gold", "50.00")).status_code == 200
    saved = {c["name"]: c["contribution"] for c in _assumptions(owner_client)["categories"]}
    assert saved["Stocks"] is None
    assert saved["Gold"] == "50.00"
    assert _contributions(owner_client).status_code == 200
    assert all(c["contribution"] is None for c in _assumptions(owner_client)["categories"])


@pytest.mark.parametrize(
    ("items", "status"),
    [
        ([("Stocks", "0.99")], 422),
        ([("Stocks", "100000.01")], 422),
        ([("Stocks", "10.001")], 422),
        ([("Stocks", "10.00"), ("Stocks", "20.00")], 422),
        ([("Debts", "10.00")], 422),
    ],
)
def test_impossible_contributions_are_refused(
    owner_client: TestClient, items: list[tuple[str, str]], status: int
) -> None:
    body = [_item(owner_client, name, amount) for name, amount in items]
    assert _contributions(owner_client, *body).status_code == status


def test_a_contribution_to_another_household_s_category_is_not_found(
    owner_client: TestClient,
) -> None:
    body = {"category_id": "019a0000-0000-7000-8000-000000000000", "amount": "10.00"}
    assert _contributions(owner_client, body).status_code == 404


def test_the_contributions_are_in_the_activity_log(owner_client: TestClient) -> None:
    _contributions(owner_client, _item(owner_client, "Stocks", "300.00"))
    log = owner_client.get("/api/audit").json()
    details = [e["details"] for e in log["items"] if e["action"] == "settings_changed"]
    assert {"contributions": "Stocks 300.00"} in details
    _contributions(owner_client, _item(owner_client, "Gold", "50.00", indexed=False, ret="0.035"))
    log = owner_client.get("/api/audit").json()
    details = [e["details"] for e in log["items"] if e["action"] == "settings_changed"]
    assert {"contributions": "Gold 50.00 fixed at 0.035"} in details


def test_a_member_sets_the_contributions_but_never_without_the_csrf_token(
    client: TestClient, clock: Clock, member: User
) -> None:
    clock.now = TODAY
    log_in(client, clock, "member@example.com")
    body = {"contributions": [_item(client, "Stocks", "100.00")]}
    assert client.put("/api/projection/contributions", json=body).status_code == 403
    assert _contributions(client, _item(client, "Stocks", "100.00")).status_code == 200


def test_the_savings_source_is_saved_with_the_contributions(owner_client: TestClient) -> None:
    assert _assumptions(owner_client)["savings_source"] is None
    response = owner_client.put(
        "/api/projection/contributions",
        json={"contributions": [], "savings_source": "declared"},
        headers=csrf(owner_client),
    )
    assert response.status_code == 200, response.text
    assert response.json()["savings_source"] == "declared"
    # Left out, it is kept.
    assert _contributions(owner_client, _item(owner_client, "Stocks", "300.00")).status_code == 200
    assert _assumptions(owner_client)["savings_source"] == "declared"
    response = owner_client.put(
        "/api/projection/contributions",
        json={"contributions": [], "savings_source": "guessed"},
        headers=csrf(owner_client),
    )
    assert response.status_code == 422
