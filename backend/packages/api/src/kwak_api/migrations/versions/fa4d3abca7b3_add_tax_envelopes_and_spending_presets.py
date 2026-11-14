"""add tax envelopes and spending category presets

An asset line may have a tax envelope and an opening year, which the audit document shows
(F-WLT-2, §4.15). A default spending category keeps which one it is whatever its name, so the
debt ratio leaves Refunds out (F-AUD-2). The activity log records an audit document issued.

Revision ID: fa4d3abca7b3
Revises: ce114400dfb0
Create Date: 2026-11-14 18:24:36.890682
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "fa4d3abca7b3"
down_revision: str | None = "ce114400dfb0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Frozen copies as of this revision: a migration must keep doing what it did.
ENVELOPES = ("pea", "pea_pme", "life_insurance", "capitalisation", "per", "cto", "employee_savings")
PRESETS = (
    ("housing", "Housing", "Logement"),
    ("groceries", "Groceries", "Courses"),
    ("transport", "Transport", "Transport"),
    ("children", "Children", "Enfants"),
    ("health", "Health", "Santé"),
    ("subscriptions", "Subscriptions", "Abonnements"),
    ("home", "Home", "Foyer"),
    ("leisure", "Leisure", "Loisirs"),
    ("shopping", "Shopping", "Shopping"),
    ("gifts", "Gifts", "Cadeaux"),
    ("miscellaneous", "Miscellaneous", "Divers"),
    ("savings", "Savings", "Épargne"),
    ("salaries", "Salaries", "Salaires"),
    ("benefits", "Benefits", "Aides et allocations"),
    ("refunds", "Refunds", "Remboursements"),
    ("other_income", "Other income", "Autres revenus"),
)
AUDIT_BEFORE = (
    "signed_in",
    "sign_in_failed",
    "signed_out",
    "recovery_codes_renewed",
    "invite_created",
    "invite_revoked",
    "member_joined",
    "settings_changed",
    "wealth_line_deleted",
    "wealth_category_deleted",
    "goal_deleted",
    "spending_line_deleted",
    "spending_category_deleted",
    "fixed_expense_deleted",
    "categories_restored",
    "goal_renewed",
)
AUDIT_AFTER = (*AUDIT_BEFORE, "audit_document_issued")


def _in(column: str, values: Sequence[str]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def _audit_check(values: Sequence[str]) -> None:
    op.drop_constraint(op.f("ck_audit_event_audit_action"), "audit_event", type_="check")
    op.create_check_constraint(
        op.f("ck_audit_event_audit_action"), "audit_event", _in("action", values)
    )


def upgrade() -> None:
    op.add_column("spending_category", sa.Column("preset", sa.String(length=20), nullable=True))
    for preset, en, fr in PRESETS:
        op.execute(
            sa.text(
                "UPDATE spending_category SET preset = :p"
                " WHERE lower(name) IN (lower(:en), lower(:fr))"
            ).bindparams(p=preset, en=en, fr=fr)
        )
    op.add_column("wealth_line", sa.Column("tax_envelope", sa.String(length=20), nullable=True))
    op.create_check_constraint(
        op.f("ck_wealth_line_tax_envelope"), "wealth_line", _in("tax_envelope", ENVELOPES)
    )
    op.create_check_constraint(
        op.f("ck_wealth_line_envelope_or_regulated"),
        "wealth_line",
        "tax_envelope IS NULL OR regulated_type IS NULL",
    )
    op.add_column("wealth_line", sa.Column("opening_year", sa.SmallInteger(), nullable=True))
    op.create_check_constraint(
        op.f("ck_wealth_line_opening_year_range"), "wealth_line", "opening_year >= 1900"
    )
    _audit_check(AUDIT_AFTER)


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM audit_event WHERE action = 'audit_document_issued'"))
    _audit_check(AUDIT_BEFORE)
    op.drop_column("wealth_line", "opening_year")
    op.drop_column("wealth_line", "tax_envelope")
    op.drop_column("spending_category", "preset")
