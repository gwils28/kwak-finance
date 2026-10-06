import pytest
from fastapi.testclient import TestClient

from tests.api.conftest import Clock, log_in


@pytest.mark.usefixtures("member")
def test_any_member_sees_the_household_members(client: TestClient, clock: Clock) -> None:
    log_in(client, clock, "member@example.com")

    response = client.get("/api/household/members")

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": response.json()[0]["id"],
            "display_name": "Member",
            "email": "member@example.com",
            "role": "member",
        },
        {
            "id": response.json()[1]["id"],
            "display_name": "Owner",
            "email": "owner@example.com",
            "role": "owner",
        },
    ]


def test_members_require_a_sign_in(client: TestClient) -> None:
    assert client.get("/api/household/members").status_code == 401
