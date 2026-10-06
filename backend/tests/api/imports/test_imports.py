from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from kwak_api.models import Transaction, User
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tests.api.conftest import Clock, csrf, log_in

FIXTURES = Path(__file__).parents[2] / "fixtures" / "import" / "societe_generale"
CHECKING_CSV = (FIXTURES / "checking.csv").read_bytes()
SAVINGS_CSV = (FIXTURES / "savings.csv").read_bytes()


@pytest.fixture
def owner_client(client: TestClient, clock: Clock, owner: User) -> TestClient:
    log_in(client, clock)
    return client


def _account(client: TestClient, **changes: Any) -> str:
    body = {
        "name": "Compte courant",
        "institution_name": "Société Générale",
        "type": "checking",
        "visibility": "shared",
        "opening_balance": "336.95",
        "opening_date": "2026-03-01",
        **changes,
    }
    response = client.post("/api/accounts", json=body, headers=csrf(client))
    assert response.status_code == 201, response.text
    account_id: str = response.json()["id"]
    return account_id


def _send(client: TestClient, account_id: str, data: bytes, *, preview: bool = False) -> Any:
    url = f"/api/accounts/{account_id}/imports" + ("/preview" if preview else "")
    return client.post(url, files={"file": ("export.csv", data, "text/csv")}, headers=csrf(client))


def _count(session: Session) -> int:
    return session.scalar(select(func.count()).select_from(Transaction)) or 0


def test_preview_shows_every_row_and_stores_nothing(
    owner_client: TestClient, session: Session
) -> None:
    account = _account(owner_client)

    response = _send(owner_client, account, CHECKING_CSV, preview=True)

    assert response.status_code == 200
    preview = response.json()
    assert preview["format"] == "societe_generale_checking"
    assert preview["counts"] == {"new": 14, "duplicate": 0, "before_opening": 0, "error": 0}
    assert preview["rows"][0] == {
        "line": 4,
        "booked_on": "2026-03-14",
        "label": "CARTE X0000 13/03 BOULANGERIE DU PARC 100000000000001IOPD",
        "amount": "-4.20",
        "status": "new",
    }
    assert preview["period"] == {"start": "2026-03-01", "end": "2026-03-14"}
    assert preview["already_imported_at"] is None
    assert _count(session) == 0


def test_import_stores_new_rows_and_checks_the_bank_balance(
    owner_client: TestClient, session: Session
) -> None:
    account = _account(owner_client)

    response = _send(owner_client, account, CHECKING_CSV)

    assert response.status_code == 201
    batch = response.json()
    assert batch["imported_count"] == 14
    assert batch["duplicate_count"] == 0
    assert batch["balance_check"] == {
        "on": "2026-03-14",
        "bank": "1234.56",
        "computed": "1234.56",
        "difference": "0.00",
    }
    assert _count(session) == 14
    accounts = owner_client.get("/api/accounts").json()
    assert accounts[0]["balance"] == "1234.56"


def test_a_balance_mismatch_is_reported(owner_client: TestClient) -> None:
    account = _account(owner_client, opening_balance="300.00")
    check = _send(owner_client, account, CHECKING_CSV).json()["balance_check"]
    assert check["difference"] == "-36.95"


def test_importing_the_same_file_twice_adds_nothing(
    owner_client: TestClient, session: Session
) -> None:
    """Invariant §8.4, end to end."""
    account = _account(owner_client)
    first = _send(owner_client, account, CHECKING_CSV).json()

    preview = _send(owner_client, account, CHECKING_CSV, preview=True).json()
    assert preview["counts"]["duplicate"] == 14
    assert preview["already_imported_at"] == first["created_at"]

    second = _send(owner_client, account, CHECKING_CSV)
    assert second.status_code == 201
    assert second.json()["imported_count"] == 0
    assert second.json()["duplicate_count"] == 14
    assert _count(session) == 14


def test_a_later_overlapping_export_only_adds_the_new_rows(
    owner_client: TestClient, session: Session
) -> None:
    account = _account(owner_client)
    lines = CHECKING_CSV.split(b"\r\n")
    older = b"\r\n".join([lines[0].replace(b";14;", b";10;"), *lines[1:3], *lines[7:]])
    _send(owner_client, account, older)
    assert _count(session) == 10

    batch = _send(owner_client, account, CHECKING_CSV).json()

    assert batch["imported_count"] == 4
    assert _count(session) == 14


def test_rows_before_the_opening_date_are_skipped(
    owner_client: TestClient, session: Session
) -> None:
    account = _account(owner_client, opening_date="2026-03-10")
    preview = _send(owner_client, account, CHECKING_CSV, preview=True).json()
    assert preview["counts"]["before_opening"] == 9
    assert preview["counts"]["new"] == 5

    batch = _send(owner_client, account, CHECKING_CSV).json()
    assert batch["imported_count"] == 5
    assert batch["skipped_count"] == 9


def test_the_savings_layout_is_detected(owner_client: TestClient) -> None:
    account = _account(owner_client, name="Livret A", type="savings", opening_date="2026-01-01")
    batch = _send(owner_client, account, SAVINGS_CSV).json()
    assert batch["format"] == "societe_generale_savings"
    assert batch["imported_count"] == 6
    assert batch["balance_check"] is None


def test_bad_rows_are_reported_and_the_rest_imported(owner_client: TestClient) -> None:
    account = _account(owner_client)
    broken = CHECKING_CSV.replace(
        b"14/03/2026;CARTE X0000 13/03 ;CARTE X0000 13/03 BOULANGERIE",
        b"99/99/2026;CARTE X0000 13/03 ;CARTE X0000 13/03 BOULANGERIE",
    )

    preview = _send(owner_client, account, broken, preview=True).json()

    assert preview["counts"]["error"] == 1
    assert preview["errors"][0]["line"] == 4
    assert "date" in preview["errors"][0]["message"]
    assert _send(owner_client, account, broken).json()["imported_count"] == 13


def test_an_unknown_file_is_rejected(owner_client: TestClient) -> None:
    account = _account(owner_client)
    response = _send(owner_client, account, b"date,amount\n2026-01-01,12\n", preview=True)
    assert response.status_code == 422
    assert "format" in response.json()["detail"]


def test_a_large_file_is_rejected(owner_client: TestClient) -> None:
    account = _account(owner_client)
    response = _send(owner_client, account, CHECKING_CSV + b"x" * 5_000_000, preview=True)
    assert response.status_code == 413


def test_only_cash_accounts_accept_imports(owner_client: TestClient) -> None:
    account = _account(owner_client, name="PEA", type="brokerage")
    assert _send(owner_client, account, CHECKING_CSV, preview=True).status_code == 422


def test_closed_accounts_do_not_accept_imports(owner_client: TestClient) -> None:
    account = _account(owner_client)
    owner_client.patch(
        f"/api/accounts/{account}", json={"closed_on": "2026-06-30"}, headers=csrf(owner_client)
    )
    assert _send(owner_client, account, CHECKING_CSV).status_code == 422


@pytest.mark.usefixtures("member")
def test_someone_elses_private_account_is_not_found(client: TestClient, clock: Clock) -> None:
    log_in(client, clock)
    account = _account(client, visibility="private")
    log_in(client, clock, "member@example.com")
    assert _send(client, account, CHECKING_CSV, preview=True).status_code == 404


def test_imports_are_listed_and_can_be_rolled_back(
    owner_client: TestClient, session: Session, clock: Clock
) -> None:
    account = _account(owner_client)
    batch = _send(owner_client, account, CHECKING_CSV).json()
    clock.advance(timedelta(minutes=1))

    listed = owner_client.get(f"/api/accounts/{account}/imports").json()
    assert [b["id"] for b in listed] == [batch["id"]]
    assert listed[0]["file_name"] == "export.csv"

    response = owner_client.delete(f"/api/imports/{batch['id']}", headers=csrf(owner_client))
    assert response.status_code == 204
    assert _count(session) == 0
    assert (
        owner_client.get(f"/api/accounts/{account}/imports").json()[0]["rolled_back_at"] is not None
    )

    again = _send(owner_client, account, CHECKING_CSV).json()
    assert again["imported_count"] == 14
    assert (
        owner_client.delete(f"/api/imports/{batch['id']}", headers=csrf(owner_client)).status_code
        == 404
    )
