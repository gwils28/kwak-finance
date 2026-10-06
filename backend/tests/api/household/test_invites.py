from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from kwak_api.models import Invite, Role, User
from sqlalchemy import select
from sqlalchemy.orm import Session

from tests.api.conftest import PASSWORD, Clock, csrf, log_in

NEW_PASSWORD = "another long passphrase"


@pytest.fixture
def owner_client(client: TestClient, clock: Clock, owner: User) -> TestClient:
    log_in(client, clock)
    return client


def _invite(client: TestClient, email: str = "Partner@Example.com") -> str:
    response = client.post("/api/invites", json={"email": email}, headers=csrf(client))
    assert response.status_code == 201, response.text
    token: str = response.json()["token"]
    return token


def _accept(client: TestClient, token: str, password: str = NEW_PASSWORD) -> int:
    body = {"display_name": "Partner", "password": password}
    return client.post(f"/api/invites/accept/{token}", json=body).status_code


def test_owner_invites_a_member_by_email(owner_client: TestClient, session: Session) -> None:
    response = owner_client.post(
        "/api/invites", json={"email": " Partner@Example.com "}, headers=csrf(owner_client)
    )

    assert response.status_code == 201
    invite = response.json()["invite"]
    assert invite["email"] == "partner@example.com"
    assert invite["state"] == "pending"
    token = response.json()["token"]
    assert token not in session.scalars(select(Invite.token_hash)).one()


def test_the_invitee_sees_who_invited_them_without_signing_in(owner_client: TestClient) -> None:
    token = _invite(owner_client)
    owner_client.cookies.clear()

    response = owner_client.get(f"/api/invites/accept/{token}")

    assert response.status_code == 200
    assert response.json()["email"] == "partner@example.com"
    assert response.json()["household_name"] == "Home"


def test_accepting_creates_a_member_who_then_sets_up_totp(
    owner_client: TestClient, session: Session
) -> None:
    token = _invite(owner_client)
    owner_client.cookies.clear()

    assert _accept(owner_client, token) == 201

    member = session.scalars(select(User).where(User.email == "partner@example.com")).one()
    assert member.role is Role.MEMBER
    assert member.display_name == "Partner"
    login = owner_client.post(
        "/api/auth/login", json={"email": "partner@example.com", "password": NEW_PASSWORD}
    )
    assert login.json()["next_step"] == "totp_setup"


def test_an_invite_works_once(owner_client: TestClient) -> None:
    token = _invite(owner_client)
    assert _accept(owner_client, token) == 201
    assert _accept(owner_client, token) == 404
    assert owner_client.get(f"/api/invites/accept/{token}").status_code == 404


def test_an_invite_expires_after_seven_days(owner_client: TestClient, clock: Clock) -> None:
    token = _invite(owner_client)
    clock.advance(timedelta(days=7))
    assert owner_client.get(f"/api/invites/accept/{token}").status_code == 404
    assert _accept(owner_client, token) == 404


def test_a_revoked_invite_cannot_be_used(owner_client: TestClient) -> None:
    token = _invite(owner_client)
    invite_id = owner_client.get("/api/invites").json()[0]["id"]

    response = owner_client.delete(f"/api/invites/{invite_id}", headers=csrf(owner_client))

    assert response.status_code == 204
    assert _accept(owner_client, token) == 404
    assert owner_client.get("/api/invites").json() == []


def test_inviting_the_same_email_again_replaces_the_old_link(owner_client: TestClient) -> None:
    old = _invite(owner_client)
    new = _invite(owner_client, "partner@example.com")

    assert _accept(owner_client, old) == 404
    assert _accept(owner_client, new) == 201
    assert len(owner_client.get("/api/invites").json()) == 0


def test_an_existing_user_cannot_be_invited(owner_client: TestClient) -> None:
    response = owner_client.post(
        "/api/invites", json={"email": "owner@example.com"}, headers=csrf(owner_client)
    )
    assert response.status_code == 409


def test_a_weak_password_keeps_the_invite_usable(owner_client: TestClient) -> None:
    token = _invite(owner_client)
    response = owner_client.post(
        f"/api/invites/accept/{token}", json={"display_name": "Partner", "password": "short"}
    )
    assert response.status_code == 422
    assert "12 characters" in response.json()["detail"]
    assert _accept(owner_client, token) == 201


def test_the_owner_lists_pending_invites(owner_client: TestClient) -> None:
    _invite(owner_client)
    accepted = _invite(owner_client, "other@example.com")
    _accept(owner_client, accepted)

    invites = owner_client.get("/api/invites").json()

    assert [i["email"] for i in invites] == ["partner@example.com"]


@pytest.mark.usefixtures("member")
def test_members_cannot_manage_invites(client: TestClient, clock: Clock) -> None:
    log_in(client, clock, "member@example.com")
    headers = csrf(client)
    assert (
        client.post("/api/invites", json={"email": "x@example.com"}, headers=headers).status_code
        == 403
    )
    assert client.get("/api/invites").status_code == 403


def test_managing_invites_requires_a_full_sign_in(client: TestClient, owner: User) -> None:
    client.post("/api/auth/login", json={"email": "owner@example.com", "password": PASSWORD})
    assert client.get("/api/invites").status_code == 401
