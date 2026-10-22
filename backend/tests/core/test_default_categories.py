from kwak_core.categories import DEFAULT_SPENDING_CATEGORIES, CategoryKind
from kwak_core.users import Language


def test_the_spending_defaults_are_flat_with_one_savings_category() -> None:
    savings = [d for d in DEFAULT_SPENDING_CATEGORIES if d.kind is CategoryKind.SAVINGS]
    assert [d.name(Language.FR) for d in savings] == ["Épargne"]
    one_off = [d.name(Language.FR) for d in DEFAULT_SPENDING_CATEGORIES if d.one_off]
    assert one_off == ["Logement", "Abonnements"]
    assert "Foyer" in [d.name(Language.FR) for d in DEFAULT_SPENDING_CATEGORIES]


def test_the_spending_defaults_have_four_income_categories() -> None:
    income = [d for d in DEFAULT_SPENDING_CATEGORIES if d.kind is CategoryKind.INCOME]
    assert [d.name(Language.EN) for d in income] == [
        "Salaries",
        "Benefits",
        "Refunds",
        "Other income",
    ]
    assert [d.name(Language.FR) for d in income] == [
        "Salaires",
        "Aides et allocations",
        "Remboursements",
        "Autres revenus",
    ]
