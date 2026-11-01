"""The demo household (spec §4.9 F-ADM-5, invariant §8.40): opened from a signed-in session,
which then acts as the demo's owner; never mixed with the real household."""

import json
from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from kwak_api.models import Household, User
from kwak_api.services.households import HouseholdAlreadyExistsError, create_household
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from tests.api.conftest import PASSWORD, Clock, csrf, log_in


@pytest.fixture
def signed_in(client: TestClient, clock: Clock, owner: User) -> TestClient:
    log_in(client, clock)
    return client


def _enter(client: TestClient) -> dict[str, Any]:
    response = client.post("/api/demo/enter", headers=csrf(client))
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def _leave(client: TestClient) -> None:
    response = client.post("/api/demo/leave", headers=csrf(client))
    assert response.status_code == 200, response.text


def _me(client: TestClient) -> dict[str, Any]:
    response = client.get("/api/auth/me")
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def _labels(client: TestClient, month: str) -> set[str]:
    response = client.get("/api/spending/lines", params={"month": month})
    assert response.status_code == 200, response.text
    return {line["label"] for line in response.json()["lines"]}


def _category(client: TestClient, name: str) -> str:
    categories = client.get("/api/spending/categories").json()
    return next(c["id"] for c in categories if c["name"] == name)


def _add_line(client: TestClient, label: str, day: str = "2025-12-10") -> str:
    body = {
        "day": day,
        "label": label,
        "amount": "-12.50",
        "category_id": _category(client, "Groceries"),
    }
    response = client.post("/api/spending/lines", json=body, headers=csrf(client))
    assert response.status_code == 201, response.text
    line_id: str = response.json()["id"]
    return line_id


REAL_ROWS = {
    "app_user": "household_id = :h",
    "spending_line": "household_id = :h",
    "spending_category": "household_id = :h",
    "fixed_expense": "household_id = :h",
    "wealth_category": "household_id = :h",
    "wealth_line": "household_id = :h",
    "wealth_value": "line_id IN (SELECT id FROM wealth_line WHERE household_id = :h)",
    "goal": "household_id = :h",
    "audit_event": "household_id = :h",
    "member_retirement": "user_id IN (SELECT id FROM app_user WHERE household_id = :h)",
    "user_session": "user_id IN (SELECT id FROM app_user WHERE household_id = :h)",
}


def _real_rows(session: Session, household_id: object) -> dict[str, int]:
    """How many rows of each table belong to the real household."""
    return {
        table: session.scalar(
            text(f"SELECT count(*) FROM {table} WHERE {where}"),  # noqa: S608 - from REAL_ROWS
            {"h": household_id},
        )
        or 0
        for table, where in REAL_ROWS.items()
    }


# Opening and leaving


def test_entering_acts_as_the_demo_owner(signed_in: TestClient, owner: User) -> None:
    me = _enter(signed_in)
    assert me["demo"] is True
    assert me["display_name"] == "Camille"
    assert me["role"] == "owner"
    assert me["household_id"] != str(owner.household_id)
    assert _me(signed_in) == me
    members = signed_in.get("/api/household/members").json()
    assert {m["display_name"] for m in members} == {"Camille", "Alex"}


def test_leaving_comes_back_to_the_real_household(signed_in: TestClient, owner: User) -> None:
    _enter(signed_in)
    _leave(signed_in)
    me = _me(signed_in)
    assert me["demo"] is False
    assert me["id"] == str(owner.id)


def test_the_demo_holds_three_years_of_lines(signed_in: TestClient) -> None:
    _enter(signed_in)
    assert "Carrefour" in _labels(signed_in, "2023-02")
    assert "Carrefour" in _labels(signed_in, "2025-12")


def test_the_demo_follows_the_language_of_who_opens_it(signed_in: TestClient) -> None:
    signed_in.patch("/api/auth/me", json={"language": "fr"}, headers=csrf(signed_in))
    me = _enter(signed_in)
    assert me["language"] == "fr"
    assert "Boulangerie" in _labels(signed_in, "2025-12")


def test_the_language_chosen_in_the_demo_is_the_member_s_own(
    signed_in: TestClient, owner: User, session: Session
) -> None:
    _enter(signed_in)
    response = signed_in.patch("/api/auth/me", json={"language": "fr"}, headers=csrf(signed_in))
    assert response.json()["language"] == "fr"
    _leave(signed_in)
    session.refresh(owner)
    assert owner.language == "fr"


def test_an_unfinished_sign_in_cannot_open_the_demo(
    client: TestClient, clock: Clock, owner: User
) -> None:
    client.post("/api/auth/login", json={"email": owner.email, "password": PASSWORD})
    assert client.post("/api/demo/enter", headers=csrf(client)).status_code == 401


def test_signing_out_leaves_the_demo(signed_in: TestClient, clock: Clock, owner: User) -> None:
    _enter(signed_in)
    signed_in.post("/api/auth/logout", headers=csrf(signed_in))
    log_in(signed_in, clock)
    assert _me(signed_in)["demo"] is False


def test_a_second_member_opens_the_same_demo(
    client: TestClient, clock: Clock, member: User
) -> None:
    log_in(client, clock)
    first = _enter(client)
    log_in(client, clock, member.email)
    assert _enter(client)["household_id"] == first["household_id"]


# Isolation (invariant §8.40)


def test_the_real_household_never_sees_the_demo(
    signed_in: TestClient, owner: User, session: Session
) -> None:
    _add_line(signed_in, "Real bakery")
    _enter(signed_in)
    assert "Real bakery" not in _labels(signed_in, "2025-12")
    _add_line(signed_in, "Demo bakery")
    _leave(signed_in)
    assert _labels(signed_in, "2025-12") == {"Real bakery"}
    assert signed_in.get("/api/wealth/lines").json() == []
    assert signed_in.get("/api/goals").json()["goals"] == []
    members = signed_in.get("/api/household/members").json()
    assert [m["display_name"] for m in members] == ["Owner"]


def test_what_is_done_in_the_demo_goes_to_the_demo_s_log(signed_in: TestClient) -> None:
    _enter(signed_in)
    line = _add_line(signed_in, "Deleted in the demo")
    signed_in.delete(f"/api/spending/lines/{line}", headers=csrf(signed_in))
    demo_log = signed_in.get("/api/audit").json()["items"]
    assert any(e["action"] == "spending_line_deleted" for e in demo_log)
    _leave(signed_in)
    real_log = signed_in.get("/api/audit").json()["items"]
    assert not any(e["action"] == "spending_line_deleted" for e in real_log)
    assert any(e["action"] == "signed_in" for e in real_log)


def test_the_demo_members_cannot_sign_in(signed_in: TestClient, session: Session) -> None:
    _enter(signed_in)
    demo = session.scalar(select(Household).where(Household.is_demo))
    assert demo is not None
    for user in session.scalars(select(User).where(User.household_id == demo.id)):
        response = signed_in.post(
            "/api/auth/login", json={"email": user.email, "password": PASSWORD}
        )
        assert response.status_code == 401


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("post", "/api/invites", {"email": "friend@example.com"}),
        ("get", "/api/invites", None),
        ("post", "/api/auth/recovery-codes", {"password": PASSWORD}),
        ("delete", "/api/invites/0193f0a0-0000-7000-8000-000000000000", None),
        ("post", "/api/auth/totp/setup", None),
        ("post", "/api/auth/totp/confirm", {"code": "000000"}),
        ("post", "/api/auth/totp/verify", {"code": "000000"}),
        ("post", "/api/auth/recovery", {"code": "0000-0000"}),
    ],
)
def test_what_touches_people_and_sign_ins_is_refused_in_the_demo(
    signed_in: TestClient, method: str, path: str, body: dict[str, str] | None
) -> None:
    _enter(signed_in)
    response = signed_in.request(method, path, json=body, headers=csrf(signed_in))
    assert response.status_code == 403, response.text
    assert response.json()["detail"] == "not available in the demo"


def test_changes_stay_until_a_reset(signed_in: TestClient) -> None:
    _enter(signed_in)
    _add_line(signed_in, "Kept")
    _leave(signed_in)
    _enter(signed_in)
    assert "Kept" in _labels(signed_in, "2025-12")


def test_resetting_generates_the_demo_again_and_nothing_else(
    signed_in: TestClient, clock: Clock, owner: User, session: Session
) -> None:
    _add_line(signed_in, "Real bakery")
    first = _enter(signed_in)
    _add_line(signed_in, "Gone after the reset")
    before = _real_rows(session, owner.household_id)
    clock.advance(timedelta(minutes=1))
    response = signed_in.post("/api/demo/reset", headers=csrf(signed_in))
    assert response.status_code == 200, response.text
    me = response.json()
    assert me["demo"] is True
    assert me["household_id"] != first["household_id"]
    assert "Gone after the reset" not in _labels(signed_in, "2025-12")
    assert session.scalar(select(func.count()).select_from(Household).where(Household.is_demo)) == 1
    assert _real_rows(session, owner.household_id) == before
    _leave(signed_in)
    assert _labels(signed_in, "2025-12") == {"Real bakery"}


def test_a_reset_right_after_the_demo_was_generated_waits(signed_in: TestClient) -> None:
    _enter(signed_in)
    response = signed_in.post("/api/demo/reset", headers=csrf(signed_in))
    assert response.status_code == 429


def test_a_member_left_in_the_demo_is_in_the_new_one_after_a_reset(
    client: TestClient, clock: Clock, owner: User, member: User
) -> None:
    log_in(client, clock, member.email)
    _enter(client)
    member_cookies = dict(client.cookies)
    log_in(client, clock)
    _enter(client)
    clock.advance(timedelta(minutes=1))
    new = client.post("/api/demo/reset", headers=csrf(client)).json()
    client.cookies.clear()
    client.cookies.update(member_cookies)
    me = _me(client)
    assert me["demo"] is True
    assert me["household_id"] == new["household_id"]


def test_a_change_from_a_page_showing_another_household_is_refused(
    signed_in: TestClient, owner: User
) -> None:
    _enter(signed_in)
    body = {"day": "2025-12-10", "label": "Stale tab", "amount": "-1.00"}
    body["category_id"] = _category(signed_in, "Groceries")
    headers = {**csrf(signed_in), "X-Kwak-Household": str(owner.household_id)}
    response = signed_in.post("/api/spending/lines", json=body, headers=headers)
    assert response.status_code == 409
    _leave(signed_in)
    assert "Stale tab" not in _labels(signed_in, "2025-12")


def test_a_line_of_the_other_household_is_not_found(signed_in: TestClient) -> None:
    real = _add_line(signed_in, "Real bakery")
    _enter(signed_in)
    demo = _add_line(signed_in, "Demo bakery")
    assert (
        signed_in.delete(f"/api/spending/lines/{real}", headers=csrf(signed_in)).status_code == 404
    )
    _leave(signed_in)
    assert (
        signed_in.delete(f"/api/spending/lines/{demo}", headers=csrf(signed_in)).status_code == 404
    )
    assert _labels(signed_in, "2025-12") == {"Real bakery"}


def test_the_reset_is_only_from_the_demo(signed_in: TestClient) -> None:
    response = signed_in.post("/api/demo/reset", headers=csrf(signed_in))
    assert response.status_code == 409


def test_the_demo_never_counts_as_the_household(
    signed_in: TestClient, owner: User, session: Session
) -> None:
    _enter(signed_in)
    with pytest.raises(HouseholdAlreadyExistsError):
        create_household(
            session,
            household_name="Another",
            email="another@example.com",
            display_name="Another",
            password=PASSWORD,
        )


def test_the_analysis_pages_show_the_demo(signed_in: TestClient) -> None:
    def plan() -> str:
        response = signed_in.get("/api/retirement/run")
        assert response.status_code == 200, response.text
        return json.dumps(response.json(), ensure_ascii=False)

    assert "Camille" not in plan()
    _enter(signed_in)
    assert "Camille" in plan()
