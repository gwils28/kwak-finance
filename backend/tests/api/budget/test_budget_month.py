"""The budget month (F-TX-7) and the next-month shift of a category (F-CAT-5)."""

from typing import Any

from fastapi.testclient import TestClient

from tests.api.conftest import csrf


def _category(client: TestClient, name: str) -> str:
    category_id: str = next(
        c["id"] for c in client.get("/api/categories").json() if c["name"] == name
    )
    return category_id


def _account(client: TestClient, name: str = "Checking") -> str:
    body = {
        "name": name,
        "institution_name": "Bank",
        "type": "checking",
        "visibility": "shared",
        "opening_balance": "0",
        "opening_date": "2025-11-01",
    }
    response = client.post("/api/accounts", json=body, headers=csrf(client))
    assert response.status_code == 201, response.text
    account_id: str = response.json()["id"]
    return account_id


def _add(
    client: TestClient, account: str, day: str, amount: str, label: str, category: str | None
) -> str:
    body = {"account_id": account, "booked_on": day, "amount": amount, "label": label}
    response = client.post("/api/transactions", json=body, headers=csrf(client))
    assert response.status_code == 201, response.text
    transaction_id: str = response.json()["id"]
    if category:
        patch = {"category_id": _category(client, category)}
        response = client.patch(
            f"/api/transactions/{transaction_id}", json=patch, headers=csrf(client)
        )
        assert response.status_code == 200, response.text
    return transaction_id


def _shift(client: TestClient, name: str, day: int | None) -> Any:
    response = client.patch(
        f"/api/categories/{_category(client, name)}", json={"shift_day": day}, headers=csrf(client)
    )
    assert response.status_code == 200, response.text
    return response.json()


def _kpis(client: TestClient, month: str) -> Any:
    response = client.get("/api/dashboard", params={"month": month})
    assert response.status_code == 200, response.text
    return response.json()


def _transaction(client: TestClient, transaction_id: str) -> Any:
    items = client.get("/api/transactions").json()["items"]
    return next(t for t in items if t["id"] == transaction_id)


def _salary_month(client: TestClient) -> tuple[str, str]:
    """A salary paid on 20 December for January, and January's groceries."""
    account = _account(client)
    salary = _add(client, account, "2025-12-20", "2500.00", "SALAIRE", "Salary")
    _add(client, account, "2026-01-05", "-300.00", "SUPERMARCHE", "Groceries")
    return account, salary


def test_a_category_shifts_from_a_day_of_the_month(owner_client: TestClient) -> None:
    assert _shift(owner_client, "Salary", 15)["shift_day"] == 15
    listed = next(c for c in owner_client.get("/api/categories").json() if c["name"] == "Salary")
    assert listed["shift_day"] == 15
    assert _shift(owner_client, "Salary", None)["shift_day"] is None

    response = owner_client.patch(
        f"/api/categories/{_category(owner_client, 'Salary')}",
        json={"shift_day": 32},
        headers=csrf(owner_client),
    )
    assert response.status_code == 422


def test_a_salary_paid_on_the_20th_counts_for_the_next_month(owner_client: TestClient) -> None:
    _, salary = _salary_month(owner_client)
    assert _kpis(owner_client, "2025-12")["kpis"]["income"] == "2500.00"

    _shift(owner_client, "Salary", 15)

    january = _kpis(owner_client, "2026-01")["kpis"]
    assert january["income"] == "2500.00"
    assert january["net"] == "2200.00"  # not negative while waiting for the next salary
    assert _kpis(owner_client, "2025-12")["kpis"]["income"] == "0.00"
    # The list keeps the real date and says which month it counts in.
    item = _transaction(owner_client, salary)
    assert item["booked_on"] == "2025-12-20"
    assert item["budget_month"] == "2026-01"
    assert item["budget_month_set"] is False


def test_the_list_filters_on_the_budget_month(owner_client: TestClient) -> None:
    _salary_month(owner_client)
    _shift(owner_client, "Salary", 15)

    january = owner_client.get("/api/transactions", params={"budget_month": "2026-01"}).json()
    assert {t["label"] for t in january["items"]} == {"SALAIRE", "SUPERMARCHE"}
    december = owner_client.get("/api/transactions", params={"budget_month": "2025-12"}).json()
    assert december["items"] == []


def test_a_subcategory_follows_its_parent_unless_it_says_never(owner_client: TestClient) -> None:
    _, salary = _salary_month(owner_client)
    _shift(owner_client, "Income", 15)
    assert _transaction(owner_client, salary)["budget_month"] == "2026-01"

    _shift(owner_client, "Salary", 0)
    assert _transaction(owner_client, salary)["budget_month"] == "2025-12"


def test_a_budget_month_set_by_hand_wins_and_is_at_most_one_month_away(
    owner_client: TestClient,
) -> None:
    _, salary = _salary_month(owner_client)
    _shift(owner_client, "Salary", 15)

    def set_month(month: str | None) -> Any:
        return owner_client.patch(
            f"/api/transactions/{salary}", json={"budget_month": month}, headers=csrf(owner_client)
        )

    response = set_month("2025-12")
    assert response.status_code == 200, response.text
    assert response.json()["budget_month"] == "2025-12"
    assert response.json()["budget_month_set"] is True
    assert _kpis(owner_client, "2025-12")["kpis"]["income"] == "2500.00"

    assert set_month("2026-02").status_code == 422

    response = set_month(None)  # back to the category's rule
    assert response.json()["budget_month"] == "2026-01"
    assert response.json()["budget_month_set"] is False


def test_a_transfer_cannot_change_month(
    owner_client: TestClient,
) -> None:
    checking = _account(owner_client)
    savings = _account(owner_client, "Savings")
    out = _add(owner_client, checking, "2025-12-28", "-200.00", "VIR LIVRET", None)
    into = _add(owner_client, savings, "2025-12-28", "200.00", "VIR LIVRET", None)
    response = owner_client.post(
        "/api/transfers", json={"outflow_id": out, "inflow_id": into}, headers=csrf(owner_client)
    )
    assert response.status_code == 201, response.text

    response = owner_client.patch(
        f"/api/transactions/{out}", json={"budget_month": "2026-01"}, headers=csrf(owner_client)
    )
    assert response.status_code == 409
    assert _transaction(owner_client, out)["budget_month"] == "2025-12"


def test_shifted_spending_lands_in_the_matrix_and_the_months_curve(
    owner_client: TestClient,
) -> None:
    account = _account(owner_client)
    _add(owner_client, account, "2025-12-28", "-900.00", "LOYER", "Rent or mortgage")
    _shift(owner_client, "Rent or mortgage", 25)

    matrix = owner_client.get(
        "/api/budget/matrix", params={"start": "2025-12", "end": "2026-01"}
    ).json()
    rent = next(r for r in matrix["rows"] if r["name"] == "Rent or mortgage")
    assert [c["spent"] for c in rent["cells"]] == ["0.00", "900.00"]

    # Moved to a later month, it sits on that month's first day.
    cumulative = _kpis(owner_client, "2026-01")["cumulative"]
    assert cumulative[0] == {"day": "2026-01-01", "spent": "900.00"}


def test_the_plan_review_and_its_flows_count_the_shifted_salary(owner_client: TestClient) -> None:
    _salary_month(owner_client)
    _shift(owner_client, "Salary", 15)
    plan = owner_client.post(
        "/api/budget/plans", json={"period": "2026-Q1"}, headers=csrf(owner_client)
    ).json()

    review = owner_client.get(f"/api/budget/plans/{plan['id']}/review").json()
    assert review["income"] == "2500.00"
    flows = owner_client.get(f"/api/budget/plans/{plan['id']}/flows").json()["flows"]
    salary = next(f for f in flows if f["kind"] == "income")
    assert salary["amount"] == "2500.00"


def test_changing_the_shift_day_is_previewed_with_the_locked_plans_it_changes(
    owner_client: TestClient,
) -> None:
    _salary_month(owner_client)
    locked = owner_client.post(
        "/api/budget/plans", json={"period": "2025-Q4"}, headers=csrf(owner_client)
    ).json()
    salary = _category(owner_client, "Salary")

    preview = owner_client.get(f"/api/categories/{salary}/shift-preview", params={"day": 15})
    assert preview.status_code == 200, preview.text
    assert preview.json() == {
        "moved": 1,
        "months": ["2025-12", "2026-01"],
        "locked_plans": [locked["period"]],
    }
    # Previewing changes nothing.
    assert _kpis(owner_client, "2025-12")["kpis"]["income"] == "2500.00"


def test_the_sql_budget_month_agrees_with_the_listed_one(owner_client: TestClient) -> None:
    """Totals use a SQL expression, the list kwak_core: both must say the same month."""
    account = _account(owner_client)
    for day in ("2025-12-14", "2025-12-15", "2025-12-31", "2026-01-01", "2026-01-20"):
        _add(owner_client, account, day, "1000.00", "SALAIRE", "Salary")
        _add(owner_client, account, day, "-10.00", "CAFE", "Bakery and coffee")
    manual = _add(owner_client, account, "2026-01-02", "500.00", "PRIME", "Salary")
    owner_client.patch(
        f"/api/transactions/{manual}", json={"budget_month": "2025-12"}, headers=csrf(owner_client)
    )
    _shift(owner_client, "Income", 15)
    _shift(owner_client, "Food", 31)

    listed = owner_client.get("/api/transactions", params={"limit": 200}).json()["items"]
    for month in ("2025-11", "2025-12", "2026-01", "2026-02"):
        filtered = owner_client.get(
            "/api/transactions", params={"budget_month": month, "limit": 200}
        ).json()["items"]
        assert {t["id"] for t in filtered} == {
            t["id"] for t in listed if t["budget_month"] == month
        }
