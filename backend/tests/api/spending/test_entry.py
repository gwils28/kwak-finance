from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from kwak_api.models import User

from tests.api.conftest import Clock, csrf, log_in

TODAY = datetime(2026, 10, 21, 12, tzinfo=UTC)  # a Wednesday


@pytest.fixture
def owner_client(client: TestClient, clock: Clock, owner: User) -> TestClient:
    clock.now = TODAY
    log_in(client, clock)
    return client


def _categories(client: TestClient) -> dict[str, Any]:
    return {c["name"]: c for c in client.get("/api/spending/categories").json()}


def _post(client: TestClient, path: str, body: dict[str, Any]) -> Any:
    return client.post(f"/api/spending{path}", json=body, headers=csrf(client))


def _line(
    client: TestClient, label: str, amount: str, category: str, day: str = "2026-10-14"
) -> Any:
    body = {"day": day, "label": label, "amount": amount}
    body["category_id"] = _categories(client)[category]["id"]
    response = _post(client, "/lines", body)
    assert response.status_code == 201, response.text
    return response.json()


def _month(client: TestClient, month: str = "2026-10") -> Any:
    response = client.get("/api/spending/lines", params={"month": month})
    assert response.status_code == 200, response.text
    return response.json()


# Categories (F-CAT-1, 4, 6)


def test_a_new_household_has_the_flat_default_categories(owner_client: TestClient) -> None:
    categories = owner_client.get("/api/spending/categories").json()
    assert [c["name"] for c in categories] == [
        "Housing",
        "Groceries",
        "Transport",
        "Children",
        "Health",
        "Subscriptions",
        "Home",
        "Leisure",
        "Shopping",
        "Gifts",
        "Miscellaneous",
        "Savings",
        "Salaries",
        "Benefits",
        "Refunds",
        "Other income",
    ]
    kinds = {c["name"]: (c["kind"], c["one_off"]) for c in categories}
    assert kinds["Savings"] == ("savings", False)
    assert kinds["Refunds"] == ("income", False)
    assert kinds["Housing"] == ("expense", True)
    assert kinds["Groceries"] == ("expense", False)


def test_add_rename_and_mark_a_category_one_off(owner_client: TestClient) -> None:
    created = _post(owner_client, "/categories", {"name": "Pets", "kind": "expense"})
    assert created.status_code == 201, created.text
    assert (
        _post(owner_client, "/categories", {"name": "pets", "kind": "expense"}).status_code == 409
    )
    response = owner_client.patch(
        f"/api/spending/categories/{created.json()['id']}",
        json={"name": "Animals", "one_off": True},
        headers=csrf(owner_client),
    )
    assert response.status_code == 200, response.text
    assert (response.json()["name"], response.json()["one_off"]) == ("Animals", True)


def test_a_savings_category_cannot_be_one_off(owner_client: TestClient) -> None:
    savings = _categories(owner_client)["Savings"]["id"]
    response = owner_client.patch(
        f"/api/spending/categories/{savings}", json={"one_off": True}, headers=csrf(owner_client)
    )
    assert response.status_code == 422


def test_deleting_a_category_in_use_moves_its_lines(owner_client: TestClient) -> None:
    cats = _categories(owner_client)
    _line(owner_client, "Cinema", "-12.00", "Leisure")
    leisure, misc, savings = (
        cats["Leisure"]["id"],
        cats["Miscellaneous"]["id"],
        cats["Savings"]["id"],
    )
    url = f"/api/spending/categories/{leisure}"
    assert owner_client.delete(url, headers=csrf(owner_client)).status_code == 409
    wrong_kind = owner_client.delete(url, params={"move_to": savings}, headers=csrf(owner_client))
    assert wrong_kind.status_code == 422
    moved = owner_client.delete(url, params={"move_to": misc}, headers=csrf(owner_client))
    assert moved.status_code == 204, moved.text
    assert [ln["category_id"] for ln in _month(owner_client)["lines"]] == [misc]
    log = owner_client.get("/api/audit").json()["items"][0]
    assert (log["action"], log["details"]["name"]) == ("spending_category_deleted", "Leisure")


def test_restore_adds_back_missing_defaults(owner_client: TestClient) -> None:
    gifts = _categories(owner_client)["Gifts"]["id"]
    owner_client.delete(f"/api/spending/categories/{gifts}", headers=csrf(owner_client))
    response = _post(owner_client, "/categories/restore", {})
    assert response.status_code == 200, response.text
    assert response.json() == {"added": 1}
    assert "Gifts" in _categories(owner_client)


# Lines (F-LIN)


def test_enter_lines_and_read_the_month_with_the_last_entry(
    owner_client: TestClient, clock: Clock
) -> None:
    first = _line(owner_client, "Carrefour", "-87.40", "Groceries", "2026-10-14")
    clock.advance(timedelta(minutes=1))
    second = _line(owner_client, "Bakery", "-6.20", "Groceries", "2026-10-03")
    _line(owner_client, "Old", "-1.00", "Groceries", "2026-09-30")
    month = _month(owner_client)
    assert [ln["label"] for ln in month["lines"]] == ["Bakery", "Carrefour"]  # by date
    assert month["lines"][1]["id"] == first["id"]
    assert month["lines"][1]["entered_by"] == "Owner"
    assert month["last_entry"]["id"] == _month(owner_client, "2026-09")["last_entry"]["id"]
    assert month["last_entry"]["day"] == "2026-09-30"
    assert second["amount"] == "-6.20"


def test_an_expense_is_an_outflow_a_savings_line_either_way(owner_client: TestClient) -> None:
    cats = _categories(owner_client)
    body = {"day": "2026-10-01", "label": "Refund", "amount": "5.00"}
    refund = _post(owner_client, "/lines", {**body, "category_id": cats["Health"]["id"]})
    assert refund.status_code == 422
    taken_back = _post(owner_client, "/lines", {**body, "category_id": cats["Savings"]["id"]})
    assert taken_back.status_code == 201, taken_back.text
    zero = _post(
        owner_client, "/lines", {**body, "amount": "0.00", "category_id": cats["Savings"]["id"]}
    )
    assert zero.status_code == 422


def test_a_line_needs_a_category_or_a_split(owner_client: TestClient) -> None:
    response = _post(owner_client, "/lines", {"day": "2026-10-01", "label": "X", "amount": "-1.00"})
    assert response.status_code == 422


def test_split_the_last_part_takes_the_rest(owner_client: TestClient) -> None:
    cats = _categories(owner_client)
    body = {
        "day": "2026-10-10",
        "label": "Hypermarket",
        "amount": "-84.30",
        "split": {
            "parts": [{"category_id": cats["Groceries"]["id"], "amount": "-60.00"}],
            "rest_category_id": cats["Home"]["id"],
        },
    }
    response = _post(owner_client, "/lines", body)
    assert response.status_code == 201, response.text
    line = response.json()
    assert line["category_id"] is None
    assert [(p["category_id"], p["amount"]) for p in line["parts"]] == [
        (cats["Groceries"]["id"], "-60.00"),
        (cats["Home"]["id"], "-24.30"),
    ]
    body["split"]["parts"][0]["amount"] = "-90.00"
    assert _post(owner_client, "/lines", body).status_code == 422


def test_edit_a_line_and_unsplit_it(owner_client: TestClient) -> None:
    cats = _categories(owner_client)
    line = _line(owner_client, "Carrefour", "-87.40", "Groceries")
    body = {
        "day": "2026-10-15",
        "label": "Carrefour Market",
        "amount": "-80.00",
        "category_id": cats["Home"]["id"],
    }
    response = owner_client.put(
        f"/api/spending/lines/{line['id']}", json=body, headers=csrf(owner_client)
    )
    assert response.status_code == 200, response.text
    assert (response.json()["label"], response.json()["category_id"]) == (
        "Carrefour Market",
        cats["Home"]["id"],
    )


def test_delete_a_line_is_logged(owner_client: TestClient) -> None:
    line = _line(owner_client, "Cinema", "-12.00", "Leisure")
    response = owner_client.delete(f"/api/spending/lines/{line['id']}", headers=csrf(owner_client))
    assert response.status_code == 204
    assert _month(owner_client)["lines"] == []
    log = owner_client.get("/api/audit").json()["items"][0]
    assert log["action"] == "spending_line_deleted"
    assert (log["details"]["label"], log["details"]["amount"]) == ("Cinema", "-12.00")


def test_a_member_sees_and_edits_every_line(
    owner_client: TestClient, clock: Clock, member: User
) -> None:
    line = _line(owner_client, "Cinema", "-12.00", "Leisure")
    log_in(owner_client, clock, "member@example.com")
    assert [ln["id"] for ln in _month(owner_client)["lines"]] == [line["id"]]
    response = owner_client.delete(f"/api/spending/lines/{line['id']}", headers=csrf(owner_client))
    assert response.status_code == 204


# Label memory and quick line (F-ENT-2, 3)


def test_label_suggestions_carry_the_remembered_category(
    owner_client: TestClient, clock: Clock
) -> None:
    cats = _categories(owner_client)
    _line(owner_client, "Carrefour", "-87.40", "Groceries")
    clock.advance(timedelta(minutes=1))
    _line(owner_client, "carrefour", "-20.00", "Home")
    _line(owner_client, "Carburant", "-60.00", "Transport")
    response = owner_client.get("/api/spending/labels", params={"q": "car"})
    assert response.status_code == 200, response.text
    assert response.json() == [
        {"label": "carrefour", "category_id": cats["Home"]["id"]},
        {"label": "Carburant", "category_id": cats["Transport"]["id"]},
    ]


def test_the_quick_line_is_understood(owner_client: TestClient) -> None:
    cats = _categories(owner_client)
    _line(owner_client, "Boulangerie", "-1.10", "Groceries")
    response = _post(owner_client, "/quick", {"text": "boulangerie 12,50 yesterday"})
    assert response.status_code == 200, response.text
    assert response.json() == {
        "day": "2026-10-20",
        "amount": "-12.50",
        "label": "boulangerie",
        "category_id": cats["Groceries"]["id"],
        "category_word": None,
    }
    forced = _post(owner_client, "/quick", {"text": "#sav 200 livret"}).json()
    assert (forced["category_id"], forced["amount"]) == (cats["Savings"]["id"], "-200.00")
    withdrawal = _post(owner_client, "/quick", {"text": "#sav -200 livret"}).json()
    assert withdrawal["amount"] == "200.00"
    unknown = _post(owner_client, "/quick", {"text": "#zz cinema"}).json()
    assert (unknown["category_id"], unknown["category_word"], unknown["amount"]) == (
        None,
        "zz",
        None,
    )


# Income (F-INC-1)


def test_an_income_line_is_an_inflow_never_mixed_with_spending(
    owner_client: TestClient,
) -> None:
    ids = {name: c["id"] for name, c in _categories(owner_client).items()}
    _line(owner_client, "Salary", "2500.00", "Salaries")
    outflow = {"day": "2026-10-14", "label": "x", "amount": "-10.00"}
    assert (
        _post(owner_client, "/lines", outflow | {"category_id": ids["Refunds"]}).status_code == 422
    )
    mixed = {
        "day": "2026-10-14",
        "label": "x",
        "amount": "100.00",
        "split": {
            "parts": [{"category_id": ids["Refunds"], "amount": "40.00"}],
            "rest_category_id": ids["Savings"],
        },
    }
    assert _post(owner_client, "/lines", mixed).status_code == 422
    income = _post(
        owner_client,
        "/lines",
        mixed
        | {
            "split": {
                "parts": [{"category_id": ids["Refunds"], "amount": "40.00"}],
                "rest_category_id": ids["Benefits"],
            }
        },
    )
    assert income.status_code == 201, income.text
    figures = owner_client.get("/api/spending/month", params={"month": "2026-10"}).json()
    assert figures["figures"]["income"] == "2600.00"


def test_an_income_category_can_be_added_but_has_no_target_nor_fixed_expense(
    owner_client: TestClient,
) -> None:
    created = _post(owner_client, "/categories", {"name": "Rent received", "kind": "income"})
    assert created.status_code == 201, created.text
    category = created.json()["id"]
    target = owner_client.put(
        f"/api/spending/targets/{category}/2026-10",
        json={"amount": "100.00"},
        headers=csrf(owner_client),
    )
    assert target.status_code == 422
    fixed = {
        "label": "Rent",
        "category_id": category,
        "amount": "-500.00",
        "frequency": "monthly",
        "day": 5,
        "first_month": "2026-10",
    }
    assert _post(owner_client, "/fixed", fixed).status_code == 422


def test_an_expense_line_can_become_an_income_line(owner_client: TestClient) -> None:
    line = _line(owner_client, "Mutuelle", "-30.00", "Health")
    body = {
        "day": "2026-10-14",
        "label": "Mutuelle",
        "amount": "30.00",
        "category_id": _categories(owner_client)["Refunds"]["id"],
    }
    response = owner_client.put(
        f"/api/spending/lines/{line['id']}", json=body, headers=csrf(owner_client)
    )
    assert response.status_code == 200, response.text
    assert response.json()["amount"] == "30.00"


def test_the_quick_line_keeps_an_income_positive(owner_client: TestClient) -> None:
    quick = _post(owner_client, "/quick", {"text": "#sal 2500 paie"}).json()
    assert (quick["amount"], quick["label"]) == ("2500.00", "paie")
    assert quick["category_id"] == _categories(owner_client)["Salaries"]["id"]


# Fixed expenses (F-FIX)


def _fixed(client: TestClient, label: str, amount: str, category: str, **extra: Any) -> Any:
    body = {
        "label": label,
        "category_id": _categories(client)[category]["id"],
        "amount": amount,
        "frequency": "monthly",
        "day": 1,
        "first_month": "2026-01",
        **extra,
    }
    response = _post(client, "/fixed", body)
    assert response.status_code == 201, response.text
    return response.json()


def _occurrences(client: TestClient, month: str = "2026-10") -> list[Any]:
    response = client.get("/api/spending/fixed/occurrences", params={"month": month})
    assert response.status_code == 200, response.text
    result: list[Any] = response.json()
    return result


def test_confirm_skip_and_hand_match_occurrences(owner_client: TestClient) -> None:
    rent = _fixed(owner_client, "Rent", "-950.00", "Housing")
    nanny = _fixed(owner_client, "Childminder", "-420.00", "Children", day=5)
    tax = _fixed(
        owner_client, "Tax", "-90.00", "Home", frequency="quarterly", first_month="2026-02"
    )
    netflix = _fixed(owner_client, "Netflix", "-13.49", "Subscriptions", day=12)
    assert [o["label"] for o in _occurrences(owner_client)] == ["Rent", "Childminder", "Netflix"]
    assert tax["frequency"] == "quarterly"

    confirmed = _post(
        owner_client,
        "/lines",
        {
            "day": "2026-10-01",
            "label": "Rent",
            "amount": "-950.00",
            "category_id": rent["category_id"],
            "fixed_expense_id": rent["id"],
        },
    )
    assert confirmed.status_code == 201, confirmed.text
    _line(owner_client, " childminder ", "-430.00", "Children", "2026-10-06")
    skip = owner_client.put(
        f"/api/spending/fixed/{netflix['id']}/skips/2026-10", headers=csrf(owner_client)
    )
    assert skip.status_code == 204, skip.text
    status = {o["label"]: o["status"] for o in _occurrences(owner_client)}
    assert status == {"Rent": "confirmed", "Childminder": "confirmed", "Netflix": "skipped"}
    assert nanny["day"] == 5

    owner_client.delete(
        f"/api/spending/fixed/{netflix['id']}/skips/2026-10", headers=csrf(owner_client)
    )
    assert {o["label"]: o["status"] for o in _occurrences(owner_client)}["Netflix"] == "to_confirm"


def test_edit_pause_and_delete_a_fixed_expense(owner_client: TestClient) -> None:
    rent = _fixed(owner_client, "Rent", "-950.00", "Housing")
    body = {k: rent[k] for k in ("label", "category_id", "frequency", "day", "first_month")}
    body.update(amount="-980.00", paused=True)
    response = owner_client.put(
        f"/api/spending/fixed/{rent['id']}", json=body, headers=csrf(owner_client)
    )
    assert response.status_code == 200, response.text
    assert response.json()["amount"] == "-980.00"
    assert _occurrences(owner_client) == []
    response = owner_client.delete(f"/api/spending/fixed/{rent['id']}", headers=csrf(owner_client))
    assert response.status_code == 204
    assert owner_client.get("/api/spending/fixed").json() == []
    log = owner_client.get("/api/audit").json()["items"][0]
    assert (log["action"], log["details"]["label"]) == ("fixed_expense_deleted", "Rent")


def test_a_fixed_expense_must_end_after_it_starts(owner_client: TestClient) -> None:
    cats = _categories(owner_client)
    body = {
        "label": "Gym",
        "category_id": cats["Leisure"]["id"],
        "amount": "-30.00",
        "frequency": "monthly",
        "day": 32,
        "first_month": "2026-05",
    }
    assert _post(owner_client, "/fixed", body).status_code == 422
    body.update(day=10, last_month="2026-04")
    assert _post(owner_client, "/fixed", body).status_code == 422
