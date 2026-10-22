"""The spending's categories (F-CAT-1): one level, each of a kind."""

import enum
from dataclasses import dataclass

from kwak_core.users import Language


class CategoryKind(enum.StrEnum):
    EXPENSE = "expense"
    INCOME = "income"
    """Money received (F-INC-1): its lines make up the month's income."""
    SAVINGS = "savings"
    """Money put aside (F-CAT-4): never spending nor income."""


@dataclass(frozen=True)
class Names:
    """A default category's name in each interface language."""

    en: str
    fr: str

    def name(self, language: Language) -> str:
        return self.fr if language is Language.FR else self.en


@dataclass(frozen=True)
class DefaultCategory:
    names: Names
    kind: CategoryKind
    one_off: bool = False
    """Paid once in the month (F-CAT-6): not judged against the pace of the month."""

    def name(self, language: Language) -> str:
        return self.names.name(language)


_E, _I, _S, N = CategoryKind.EXPENSE, CategoryKind.INCOME, CategoryKind.SAVINGS, Names

# Seeded for every new household, in the owner's language (F-CAT-1).
DEFAULT_SPENDING_CATEGORIES: tuple[DefaultCategory, ...] = (
    DefaultCategory(N("Housing", "Logement"), _E, one_off=True),
    DefaultCategory(N("Groceries", "Courses"), _E),
    DefaultCategory(N("Transport", "Transport"), _E),
    DefaultCategory(N("Children", "Enfants"), _E),
    DefaultCategory(N("Health", "Santé"), _E),
    DefaultCategory(N("Subscriptions", "Abonnements"), _E, one_off=True),
    DefaultCategory(N("Home", "Foyer"), _E),
    DefaultCategory(N("Leisure", "Loisirs"), _E),
    DefaultCategory(N("Shopping", "Shopping"), _E),
    DefaultCategory(N("Gifts", "Cadeaux"), _E),
    DefaultCategory(N("Miscellaneous", "Divers"), _E),
    DefaultCategory(N("Savings", "Épargne"), _S),
    DefaultCategory(N("Salaries", "Salaires"), _I),
    DefaultCategory(N("Benefits", "Aides et allocations"), _I),
    DefaultCategory(N("Refunds", "Remboursements"), _I),
    DefaultCategory(N("Other income", "Autres revenus"), _I),
)
