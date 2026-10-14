"""add wealth tables and seed the default wealth categories

Revision ID: 02d05c0c4e51
Revises: 8dccddd9977d
Create Date: 2026-10-15 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from kwak_core.ids import uuid7

revision: str = "02d05c0c4e51"
down_revision: str | None = "8dccddd9977d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Frozen copies as of this revision: a migration must keep doing what it did.
ACCOUNT_TYPES = (
    "checking",
    "savings",
    "brokerage",
    "life_insurance",
    "employee_savings",
    "crypto",
    "loan",
    "real_estate",
    "use_asset",
    "other",
)
# (English name, French name, kind, colour key, account type it holds)
DEFAULTS = (
    ("Savings accounts", "Livrets", "asset", "savings", "savings"),
    ("Current accounts", "Comptes courants", "asset", "current", "checking"),
    ("Stocks", "Actions", "asset", "stocks", None),
    ("Crypto", "Cryptos", "asset", "crypto", None),
    ("Bonds", "Obligations", "asset", "bonds", None),
    ("Private equity", "Private equity", "asset", "private-equity", None),
    ("Gold", "Or", "asset", "gold", None),
    ("Real estate", "Immobilier", "asset", "real-estate", None),
    ("Equipment", "Matériels", "asset", "equipment", None),
    ("Exotic", "Exotiques", "asset", "exotic", None),
    ("Debts", "Dettes", "debt", "debts", None),
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
    "imported",
    "import_rolled_back",
    "transaction_deleted",
    "category_deleted",
    "plan_deleted",
    "recurring_deleted",
    "rule_created",
    "rule_updated",
    "rule_deleted",
    "rules_applied",
    "categories_restored",
)
AUDIT_AFTER = (*AUDIT_BEFORE, "wealth_line_deleted", "wealth_category_deleted")


def _in(column: str, values: Sequence[str]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def _audit_check(values: Sequence[str]) -> None:
    op.drop_constraint(op.f("ck_audit_event_audit_action"), "audit_event", type_="check")
    op.create_check_constraint(
        op.f("ck_audit_event_audit_action"), "audit_event", _in("action", values)
    )


def upgrade() -> None:
    op.create_table(
        "wealth_category",
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=60), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("colour", sa.String(length=20), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("holds", sa.String(length=20), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            _in("holds", ACCOUNT_TYPES), name=op.f("ck_wealth_category_account_type")
        ),
        sa.CheckConstraint(
            _in("kind", ("asset", "debt")), name=op.f("ck_wealth_category_wealth_kind")
        ),
        sa.ForeignKeyConstraint(
            ["household_id"],
            ["household.id"],
            name=op.f("fk_wealth_category_household_id_household"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_wealth_category")),
        sa.UniqueConstraint(
            "household_id", "holds", name=op.f("uq_wealth_category_household_id_holds")
        ),
    )
    op.create_index(
        op.f("ix_wealth_category_household_id"), "wealth_category", ["household_id"], unique=False
    )
    op.create_index(
        "uq_wealth_category_household_name",
        "wealth_category",
        ["household_id", sa.literal_column("lower(name)")],
        unique=True,
    )
    op.create_table(
        "wealth_line",
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("category_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("visibility", sa.String(length=20), nullable=False),
        sa.Column("closed_from", sa.Date(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            _in("visibility", ("private", "shared", "joint")),
            name=op.f("ck_wealth_line_visibility"),
        ),
        sa.CheckConstraint(
            "extract(day from closed_from) = 1", name=op.f("ck_wealth_line_closed_from_month")
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["wealth_category.id"],
            name=op.f("fk_wealth_line_category_id_wealth_category"),
        ),
        sa.ForeignKeyConstraint(
            ["household_id"], ["household.id"], name=op.f("fk_wealth_line_household_id_household")
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["app_user.id"], name=op.f("fk_wealth_line_owner_id_app_user")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_wealth_line")),
    )
    op.create_index(
        op.f("ix_wealth_line_category_id"), "wealth_line", ["category_id"], unique=False
    )
    op.create_index(
        op.f("ix_wealth_line_household_id"), "wealth_line", ["household_id"], unique=False
    )
    op.create_index(op.f("ix_wealth_line_owner_id"), "wealth_line", ["owner_id"], unique=False)
    op.create_table(
        "wealth_value",
        sa.Column("line_id", sa.Uuid(), nullable=False),
        sa.Column("month", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("amount >= 0", name=op.f("ck_wealth_value_amount_positive")),
        sa.CheckConstraint(
            "extract(day from month) = 1", name=op.f("ck_wealth_value_month_first_day")
        ),
        sa.ForeignKeyConstraint(
            ["line_id"],
            ["wealth_line.id"],
            name=op.f("fk_wealth_value_line_id_wealth_line"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_wealth_value")),
        sa.UniqueConstraint("line_id", "month", name=op.f("uq_wealth_value_line_id_month")),
    )
    _audit_check(AUDIT_AFTER)

    # Every existing household gets the defaults, in its owner's language.
    conn = op.get_bind()
    households = conn.execute(
        sa.text(
            "SELECT h.id, coalesce(u.language, 'en') FROM household h"
            " LEFT JOIN app_user u ON u.household_id = h.id AND u.role = 'owner'"
        )
    ).all()
    insert = sa.text(
        "INSERT INTO wealth_category (id, household_id, name, kind, colour, position, holds)"
        " VALUES (:id, :household, :name, :kind, :colour, :position, :holds)"
    )
    for household_id, language in households:
        for position, (en, fr, kind, colour, holds) in enumerate(DEFAULTS):
            conn.execute(
                insert,
                {
                    "id": uuid7(),
                    "household": household_id,
                    "name": fr if language == "fr" else en,
                    "kind": kind,
                    "colour": colour,
                    "position": position,
                    "holds": holds,
                },
            )


def downgrade() -> None:
    op.execute(
        "DELETE FROM audit_event WHERE action IN ('wealth_line_deleted', 'wealth_category_deleted')"
    )
    _audit_check(AUDIT_BEFORE)
    op.drop_table("wealth_value")
    op.drop_index(op.f("ix_wealth_line_owner_id"), table_name="wealth_line")
    op.drop_index(op.f("ix_wealth_line_household_id"), table_name="wealth_line")
    op.drop_index(op.f("ix_wealth_line_category_id"), table_name="wealth_line")
    op.drop_table("wealth_line")
    op.drop_index("uq_wealth_category_household_name", table_name="wealth_category")
    op.drop_index(op.f("ix_wealth_category_household_id"), table_name="wealth_category")
    op.drop_table("wealth_category")
