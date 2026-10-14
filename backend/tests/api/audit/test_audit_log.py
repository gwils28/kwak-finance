from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from kwak_api.auth.routes import client_ip
from kwak_api.models import User
from starlette.requests import Request

from tests.api.conftest import PASSWORD, Clock, csrf, log_in, totp_code
from tests.api.dashboard.test_dashboard import _category

CHECKING_CSV = (
    Path(__file__).parents[2] / "fixtures" / "import" / "societe_generale" / "checking.csv"
).read_bytes()


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


def _account(client: TestClient, visibility: str = "shared", name: str = "Compte courant") -> str:
    body = {
        "name": name,
        "institution_name": "SG",
        "type": "checking",
        "visibility": visibility,
        "opening_balance": "0",
        "opening_date": "2026-01-01",
    }
    response = client.post("/api/accounts", json=body, headers=csrf(client))
    assert response.status_code == 201, response.text
    account: str = response.json()["id"]
    return account


def _entry(client: TestClient, account: str, label: str = "Marché") -> str:
    body = {"account_id": account, "booked_on": "2026-01-05", "amount": "-12.50", "label": label}
    response = client.post("/api/transactions", json=body, headers=csrf(client))
    assert response.status_code == 201, response.text
    transaction: str = response.json()["id"]
    return transaction


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


def test_an_import_and_its_rollback_are_logged(owner_client: TestClient) -> None:
    account = _account(owner_client)
    files = {"file": ("march.csv", CHECKING_CSV, "text/csv")}
    batch = owner_client.post(
        f"/api/accounts/{account}/imports", files=files, headers=csrf(owner_client)
    ).json()
    owner_client.delete(f"/api/imports/{batch['id']}", headers=csrf(owner_client))

    entries = _log(owner_client, kind="import")["items"]
    assert [(e["action"], e["details"]) for e in entries] == [
        ("import_rolled_back", {"account": "Compte courant", "file": "march.csv"}),
        (
            "imported",
            {"account": "Compte courant", "file": "march.csv", "added": batch["imported_count"]},
        ),
    ]


def test_deletions_are_logged_with_what_was_deleted(owner_client: TestClient) -> None:
    account = _account(owner_client)
    transaction = _entry(owner_client, account)
    owner_client.delete(f"/api/transactions/{transaction}", headers=csrf(owner_client))
    category = owner_client.post(
        "/api/categories", json={"name": "Vélo"}, headers=csrf(owner_client)
    ).json()["id"]
    owner_client.delete(f"/api/categories/{category}", headers=csrf(owner_client))
    item = owner_client.post(
        "/api/recurring",
        json={
            "account_id": account,
            "label": "Loyer",
            "amount": "-950.00",
            "frequency": "monthly",
            "day": 5,
            "start_on": "2026-01-05",
        },
        headers=csrf(owner_client),
    ).json()["id"]
    owner_client.delete(f"/api/recurring/{item}", headers=csrf(owner_client))
    plan = owner_client.post(
        "/api/budget/plans", json={"period": "2026-Q2"}, headers=csrf(owner_client)
    ).json()["id"]
    owner_client.delete(f"/api/budget/plans/{plan}", headers=csrf(owner_client))

    entries = _log(owner_client, kind="deletion")["items"]
    assert [(e["action"], e["details"]) for e in entries] == [
        ("plan_deleted", {"period": "2026-Q2"}),
        ("recurring_deleted", {"label": "Loyer", "amount": "-950.00", "account": "Compte courant"}),
        ("category_deleted", {"name": "Vélo"}),
        (
            "transaction_deleted",
            {
                "label": "Marché",
                "amount": "-12.50",
                "date": "2026-01-05",
                "account": "Compte courant",
            },
        ),
    ]


def test_a_refused_deletion_leaves_no_entry(owner_client: TestClient) -> None:
    category = owner_client.post(
        "/api/categories", json={"name": "Maison"}, headers=csrf(owner_client)
    ).json()["id"]
    owner_client.post(
        "/api/categories",
        json={"name": "Jardin", "parent_id": category},
        headers=csrf(owner_client),
    )
    response = owner_client.delete(f"/api/categories/{category}", headers=csrf(owner_client))
    assert response.status_code == 409
    assert _actions(owner_client, kind="deletion") == []


def test_rule_changes_are_logged(owner_client: TestClient) -> None:
    groceries = _category(owner_client, "Groceries")
    rule = owner_client.post(
        "/api/rules",
        json={"category_id": groceries, "label_contains": "CARREFOUR"},
        headers=csrf(owner_client),
    ).json()["id"]
    owner_client.patch(
        f"/api/rules/{rule}", json={"label_contains": "LECLERC"}, headers=csrf(owner_client)
    )
    owner_client.post(
        "/api/rules/apply", json={"only_uncategorised": True}, headers=csrf(owner_client)
    )
    owner_client.patch(
        f"/api/rules/{rule}", json={"label_contains": "LECLERC"}, headers=csrf(owner_client)
    )
    owner_client.delete(f"/api/rules/{rule}", headers=csrf(owner_client))

    # Saving it unchanged is not a change.
    owner_client.patch(
        f"/api/rules/{rule}", json={"label_contains": "LECLERC"}, headers=csrf(owner_client)
    )

    entries = _log(owner_client, kind="rules")["items"]
    assert [(e["action"], e["details"]) for e in entries] == [
        ("rule_deleted", {"category": "Groceries", "label": "LECLERC"}),
        # No count: it would tell the owner how many private transactions the rules caught.
        ("rules_applied", {}),
        ("rule_updated", {"category": "Groceries", "label": "LECLERC"}),
        ("rule_created", {"category": "Groceries", "label": "CARREFOUR"}),
    ]


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


def test_an_entry_about_a_private_account_is_only_for_its_owner(
    client: TestClient, clock: Clock, owner: User, member: User
) -> None:
    log_in(client, clock, "member@example.com")
    account = _account(client, "private", "Perso")
    client.delete(f"/api/transactions/{_entry(client, account)}", headers=csrf(client))
    assert "transaction_deleted" in _actions(client)

    log_in(client, clock)
    assert "transaction_deleted" not in _actions(client)


def test_the_log_is_paged_and_filtered_by_kind(owner_client: TestClient, clock: Clock) -> None:
    for _ in range(3):
        log_in(owner_client, clock)
    page = _log(owner_client, kind="sign_in", limit="2", offset="1")
    assert page["total"] == 4
    assert len(page["items"]) == 2
    assert _actions(owner_client, kind="rules") == []


def test_the_log_requires_a_full_sign_in(client: TestClient) -> None:
    assert client.get("/api/audit").status_code == 401


def test_a_recurring_transfer_into_a_private_account_stays_private(
    client: TestClient, clock: Clock, owner: User, member: User
) -> None:
    log_in(client, clock, "member@example.com")
    shared, private = _account(client, "shared", "Commun"), _account(client, "private", "Perso")
    item = client.post(
        "/api/recurring",
        json={
            "account_id": shared,
            "destination_account_id": private,
            "label": "",
            "amount": "-200.00",
            "frequency": "monthly",
            "day": 5,
            "start_on": "2026-01-05",
        },
        headers=csrf(client),
    ).json()["id"]
    client.delete(f"/api/recurring/{item}", headers=csrf(client))
    assert "recurring_deleted" in _actions(client)

    log_in(client, clock)
    assert "recurring_deleted" not in _actions(client)


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
