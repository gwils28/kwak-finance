from typing import Any

import pytest
from fastapi.testclient import TestClient
from kwak_api.auth.routes import client_ip
from kwak_api.models import User
from starlette.requests import Request

from tests.api.conftest import PASSWORD, Clock, csrf, log_in, totp_code


@pytest.fixture
def owner_client(client: TestClient, clock: Clock, owner: User) -> TestClient:
    log_in(client, clock)
    return client


def _log(client: TestClient, **params: str) -> Any:
    response = client.get("/api/audit", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def _actions(client: TestClient, **params: str) -> list[str]:
    return [e["action"] for e in _log(client, **params)["items"]]


def _category(client: TestClient, name: str) -> str:
    categories = client.get("/api/spending/categories").json()
    found: str = next(c["id"] for c in categories if c["name"] == name)
    return found


def test_a_sign_in_is_logged_with_its_second_factor_and_address(owner_client: TestClient) -> None:
    entry = _log(owner_client)["items"][0]
    assert entry["action"] == "signed_in"
    assert entry["kind"] == "sign_in"
    assert entry["details"] == {"method": "totp"}
    assert entry["ip"] == "192.0.2.10"
    assert entry["user_name"] == "Owner"


def test_failed_sign_ins_on_a_known_account_are_logged(
    client: TestClient, clock: Clock, owner: User
) -> None:
    client.post("/api/auth/login", json={"email": "owner@example.com", "password": "wrong"})
    client.post("/api/auth/login", json={"email": "nobody@example.com", "password": "wrong"})
    client.post("/api/auth/login", json={"email": "owner@example.com", "password": PASSWORD})
    client.post("/api/auth/totp/verify", json={"code": "000000"}, headers=csrf(client))
    client.post("/api/auth/totp/verify", json={"code": totp_code(clock)}, headers=csrf(client))

    entries = _log(client)["items"]
    assert [(e["action"], e["details"]) for e in entries] == [
        ("signed_in", {"method": "totp"}),
        ("sign_in_failed", {"step": "code"}),
        ("sign_in_failed", {"step": "password"}),  # the unknown email is not logged
    ]


def test_a_recovery_code_sign_in_and_a_sign_out_are_logged(
    client: TestClient, clock: Clock, owner: User
) -> None:
    log_in(client, clock)
    codes = client.post(
        "/api/auth/recovery-codes", json={"password": PASSWORD}, headers=csrf(client)
    ).json()["recovery_codes"]
    client.post("/api/auth/logout", headers=csrf(client))
    client.post("/api/auth/login", json={"email": "owner@example.com", "password": PASSWORD})
    client.post("/api/auth/recovery", json={"code": codes[0]}, headers=csrf(client))

    assert [(e["action"], e["details"]) for e in _log(client)["items"][:4]] == [
        ("signed_in", {"method": "recovery_code"}),
        ("signed_out", {}),
        ("recovery_codes_renewed", {}),
        ("signed_in", {"method": "totp"}),
    ]


def test_deletions_are_logged_with_what_was_deleted(owner_client: TestClient) -> None:
    line = owner_client.post(
        "/api/spending/lines",
        json={
            "day": "2026-01-05",
            "label": "Marché",
            "amount": "-12.50",
            "category_id": _category(owner_client, "Groceries"),
        },
        headers=csrf(owner_client),
    ).json()["id"]
    owner_client.delete(f"/api/spending/lines/{line}", headers=csrf(owner_client))
    category = owner_client.post(
        "/api/spending/categories",
        json={"name": "Vélo", "kind": "expense"},
        headers=csrf(owner_client),
    ).json()["id"]
    owner_client.delete(f"/api/spending/categories/{category}", headers=csrf(owner_client))

    entries = _log(owner_client, kind="deletion")["items"]
    assert [(e["action"], e["details"]) for e in entries] == [
        ("spending_category_deleted", {"name": "Vélo"}),
        ("spending_line_deleted", {"label": "Marché", "amount": "-12.50", "date": "2026-01-05"}),
    ]


def test_a_refused_deletion_leaves_no_entry(owner_client: TestClient) -> None:
    owner_client.post(
        "/api/spending/lines",
        json={
            "day": "2026-01-05",
            "label": "Marché",
            "amount": "-12.50",
            "category_id": _category(owner_client, "Groceries"),
        },
        headers=csrf(owner_client),
    )
    response = owner_client.delete(
        f"/api/spending/categories/{_category(owner_client, 'Groceries')}",
        headers=csrf(owner_client),
    )
    assert response.status_code == 409
    assert _actions(owner_client, kind="deletion") == []


def test_household_changes_are_logged(
    owner_client: TestClient, clock: Clock, client: TestClient
) -> None:
    first = owner_client.post(
        "/api/invites", json={"email": "a@example.com"}, headers=csrf(owner_client)
    ).json()
    owner_client.delete(f"/api/invites/{first['invite']['id']}", headers=csrf(owner_client))
    token = owner_client.post(
        "/api/invites", json={"email": "b@example.com"}, headers=csrf(owner_client)
    ).json()["token"]
    owner_client.patch(
        "/api/household/settings", json={"warn_at": "0.90"}, headers=csrf(owner_client)
    )
    owner_client.post(
        f"/api/invites/accept/{token}",
        json={"display_name": "Bea", "password": "another long passphrase"},
    )

    entries = _log(owner_client, kind="household")["items"]
    assert [(e["action"], e["user_name"], e["details"]) for e in entries] == [
        ("member_joined", "Bea", {"email": "b@example.com"}),
        ("settings_changed", "Owner", {"warn_at": "0.90"}),
        ("invite_created", "Owner", {"email": "b@example.com"}),
        ("invite_revoked", "Owner", {"email": "a@example.com"}),
        ("invite_created", "Owner", {"email": "a@example.com"}),
    ]


def test_a_member_sees_only_their_own_entries_and_the_owner_everyone_s(
    client: TestClient, clock: Clock, owner: User, member: User
) -> None:
    log_in(client, clock)
    log_in(client, clock, "member@example.com")
    assert [e["user_name"] for e in _log(client)["items"]] == ["Member"]

    log_in(client, clock)
    assert [e["user_name"] for e in _log(client)["items"]] == ["Owner", "Member", "Owner"]
    assert _log(client, user_id=str(member.id))["total"] == 1


def test_the_log_is_paged_and_filtered_by_kind(owner_client: TestClient, clock: Clock) -> None:
    for _ in range(3):
        log_in(owner_client, clock)
    page = _log(owner_client, kind="sign_in", limit="2", offset="1")
    assert page["total"] == 4
    assert len(page["items"]) == 2
    assert _actions(owner_client, kind="deletion") == []


def test_the_log_requires_a_full_sign_in(client: TestClient) -> None:
    assert client.get("/api/audit").status_code == 401


def test_abandoning_a_sign_in_after_the_password_is_not_a_sign_out(
    client: TestClient, clock: Clock, owner: User
) -> None:
    client.post("/api/auth/login", json={"email": "owner@example.com", "password": PASSWORD})
    client.post("/api/auth/logout", headers=csrf(client))
    log_in(client, clock)
    assert _actions(client) == ["signed_in"]


@pytest.mark.parametrize(
    ("host", "kept"),
    [("192.168.1.20", "192.168.1.20"), ("2001:db8::1", "2001:db8::1"), ("x" * 100, None)],
)
def test_only_a_real_address_is_kept(host: str, kept: str | None) -> None:
    # A longer value would not fit the column, and the failed attempt would go uncounted.
    request = Request({"type": "http", "client": (host, 1234), "headers": []})
    assert client_ip(request) == kept


def test_a_member_cannot_read_someone_else_s_entries(
    client: TestClient, clock: Clock, owner: User, member: User
) -> None:
    log_in(client, clock)
    log_in(client, clock, "member@example.com")
    assert _log(client, user_id=str(owner.id)) == {"items": [], "total": 0}
