"""drop the pre-v1.0 spending model

The accounts, imports, transactions, transfers, rules, recurring items, budget plans and their
categories gave way to the spending lines in v1.0: their tables go, with no export. The
activity log loses the entries about them (an old "categories restored" entry stays, its
sentence still reads), and the analyses start, which only they used,
becomes the wealth start where none was set (F-WLT-5).

Revision ID: c77a847d28b5
Revises: 3f9a1c2d7b40
Create Date: 2026-10-22 16:38:21.093573
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# Frozen copies as of this revision: a migration must keep doing what it did.
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
    "wealth_line_deleted",
    "wealth_category_deleted",
    "rule_created",
    "rule_updated",
    "rule_deleted",
    "rules_applied",
    "categories_restored",
    "goal_deleted",
    "spending_line_deleted",
    "spending_category_deleted",
    "fixed_expense_deleted",
)
GONE = (
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
)
AUDIT_AFTER = tuple(a for a in AUDIT_BEFORE if a not in GONE)
# Children before their parents.
TABLES = (
    "recurring_skip",
    "dismissed_suggestion",
    "recurring_item",
    "categorization_rule",
    "budget_plan_target",
    "budget_plan",
    "transaction_part",
    "transaction",
    "import_batch",
    "category",
    "account",
    "institution",
)


def _in(column: str, values: Sequence[str]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def _audit_check(values: Sequence[str]) -> None:
    op.drop_constraint(op.f("ck_audit_event_audit_action"), "audit_event", type_="check")
    op.create_check_constraint(
        op.f("ck_audit_event_audit_action"), "audit_event", _in("action", values)
    )


revision: str = "c77a847d28b5"
down_revision: str | None = "3f9a1c2d7b40"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text("DELETE FROM audit_event WHERE action IN :actions").bindparams(
            sa.bindparam("actions", GONE, expanding=True)
        )
    )
    _audit_check(AUDIT_AFTER)
    for table in TABLES:
        op.drop_table(table)
    op.execute(
        "UPDATE household SET wealth_start = analysis_start"
        " WHERE wealth_start IS NULL AND analysis_start IS NOT NULL"
    )
    op.drop_column("household", "analysis_start")


def downgrade() -> None:
    # The tables come back empty: what they held is gone.
    op.add_column("household", sa.Column("analysis_start", sa.DATE(), nullable=True))
    op.create_check_constraint(
        op.f("ck_household_analysis_start_month"),
        "household",
        "extract(day from analysis_start) = 1",
    )
    op.create_table(
        "institution",
        sa.Column("household_id", sa.UUID(), autoincrement=False, nullable=False),
        sa.Column("name", sa.VARCHAR(length=100), autoincrement=False, nullable=False),
        sa.Column("id", sa.UUID(), autoincrement=False, nullable=False),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            autoincrement=False,
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["household_id"], ["household.id"], name=op.f("fk_institution_household_id_household")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_institution")),
    )
    op.create_index(
        op.f("uq_institution_household_name"),
        "institution",
        ["household_id", sa.literal_column("lower(name::text)")],
        unique=True,
    )
    op.create_index(
        op.f("ix_institution_household_id"), "institution", ["household_id"], unique=False
    )
    op.create_table(
        "account",
        sa.Column("household_id", sa.UUID(), autoincrement=False, nullable=False),
        sa.Column("institution_id", sa.UUID(), autoincrement=False, nullable=False),
        sa.Column("owner_id", sa.UUID(), autoincrement=False, nullable=False),
        sa.Column("name", sa.VARCHAR(length=100), autoincrement=False, nullable=False),
        sa.Column("type", sa.VARCHAR(length=20), autoincrement=False, nullable=False),
        sa.Column("visibility", sa.VARCHAR(length=20), autoincrement=False, nullable=False),
        sa.Column(
            "opening_balance",
            sa.NUMERIC(precision=14, scale=2),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column("opening_date", sa.DATE(), autoincrement=False, nullable=False),
        sa.Column("closed_on", sa.DATE(), autoincrement=False, nullable=True),
        sa.Column("id", sa.UUID(), autoincrement=False, nullable=False),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            autoincrement=False,
            nullable=False,
        ),
        sa.CheckConstraint(
            "type IN ('checking', 'savings', 'brokerage', 'life_insurance', 'employee_savings',"
            " 'crypto', 'loan', 'real_estate', 'use_asset', 'other')",
            name=op.f("ck_account_account_type"),
        ),
        sa.CheckConstraint(
            "visibility IN ('private', 'shared', 'joint')",
            name=op.f("ck_account_visibility"),
        ),
        sa.CheckConstraint(
            "closed_on IS NULL OR closed_on >= opening_date",
            name=op.f("ck_account_closed_after_opening"),
        ),
        sa.ForeignKeyConstraint(
            ["household_id"], ["household.id"], name=op.f("fk_account_household_id_household")
        ),
        sa.ForeignKeyConstraint(
            ["institution_id"],
            ["institution.id"],
            name=op.f("fk_account_institution_id_institution"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["app_user.id"], name=op.f("fk_account_owner_id_app_user")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_account")),
    )
    op.create_index(
        op.f("uq_account_institution_name"),
        "account",
        ["institution_id", sa.literal_column("lower(name::text)")],
        unique=True,
    )
    op.create_index(op.f("ix_account_owner_id"), "account", ["owner_id"], unique=False)
    op.create_index(op.f("ix_account_institution_id"), "account", ["institution_id"], unique=False)
    op.create_index(op.f("ix_account_household_id"), "account", ["household_id"], unique=False)
    op.create_table(
        "category",
        sa.Column("household_id", sa.UUID(), autoincrement=False, nullable=False),
        sa.Column("parent_id", sa.UUID(), autoincrement=False, nullable=True),
        sa.Column("name", sa.VARCHAR(length=60), autoincrement=False, nullable=False),
        sa.Column("kind", sa.VARCHAR(length=20), autoincrement=False, nullable=False),
        sa.Column("id", sa.UUID(), autoincrement=False, nullable=False),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column("shift_day", sa.SMALLINT(), autoincrement=False, nullable=True),
        sa.Column("one_off", sa.BOOLEAN(), autoincrement=False, nullable=True),
        sa.CheckConstraint(
            "kind IN ('expense', 'income', 'savings')",
            name=op.f("ck_category_category_kind"),
        ),
        sa.CheckConstraint(
            "shift_day >= 0 AND shift_day <= 31", name=op.f("ck_category_shift_day_range")
        ),
        sa.ForeignKeyConstraint(
            ["household_id"], ["household.id"], name=op.f("fk_category_household_id_household")
        ),
        sa.ForeignKeyConstraint(
            ["parent_id"], ["category.id"], name=op.f("fk_category_parent_id_category")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_category")),
    )
    op.create_index(
        op.f("uq_category_household_parent_name"),
        "category",
        [
            "household_id",
            sa.literal_column("COALESCE(parent_id, '00000000-0000-0000-0000-000000000000'::uuid)"),
            sa.literal_column("lower(name::text)"),
        ],
        unique=True,
    )
    op.create_index(op.f("ix_category_parent_id"), "category", ["parent_id"], unique=False)
    op.create_index(op.f("ix_category_household_id"), "category", ["household_id"], unique=False)
    op.create_table(
        "import_batch",
        sa.Column("account_id", sa.UUID(), autoincrement=False, nullable=False),
        sa.Column("user_id", sa.UUID(), autoincrement=False, nullable=False),
        sa.Column("format_key", sa.VARCHAR(length=50), autoincrement=False, nullable=False),
        sa.Column("file_name", sa.VARCHAR(length=255), autoincrement=False, nullable=False),
        sa.Column("file_sha256", sa.VARCHAR(length=64), autoincrement=False, nullable=False),
        sa.Column("imported_count", sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column("duplicate_count", sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column("skipped_count", sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column("error_count", sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column("period_start", sa.DATE(), autoincrement=False, nullable=True),
        sa.Column("period_end", sa.DATE(), autoincrement=False, nullable=True),
        sa.Column(
            "bank_balance", sa.NUMERIC(precision=14, scale=2), autoincrement=False, nullable=True
        ),
        sa.Column("bank_balance_on", sa.DATE(), autoincrement=False, nullable=True),
        sa.Column(
            "created_at", postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=False
        ),
        sa.Column(
            "rolled_back_at",
            postgresql.TIMESTAMP(timezone=True),
            autoincrement=False,
            nullable=True,
        ),
        sa.Column("id", sa.UUID(), autoincrement=False, nullable=False),
        sa.Column(
            "reconciled_count",
            sa.INTEGER(),
            server_default=sa.text("0"),
            autoincrement=False,
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["account_id"], ["account.id"], name=op.f("fk_import_batch_account_id_account")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["app_user.id"], name=op.f("fk_import_batch_user_id_app_user")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_import_batch")),
    )
    op.create_index(
        op.f("uq_import_batch_account_file"),
        "import_batch",
        ["account_id", "file_sha256"],
        unique=True,
        postgresql_where="((rolled_back_at IS NULL) AND (imported_count > 0))",
    )
    op.create_index(
        op.f("ix_import_batch_account_id"), "import_batch", ["account_id"], unique=False
    )
    op.create_table(
        "transaction",
        sa.Column("account_id", sa.UUID(), autoincrement=False, nullable=False),
        sa.Column("booked_on", sa.DATE(), autoincrement=False, nullable=False),
        sa.Column("amount", sa.NUMERIC(precision=14, scale=2), autoincrement=False, nullable=False),
        sa.Column("label_raw", sa.TEXT(), autoincrement=False, nullable=False),
        sa.Column("label_norm", sa.TEXT(), autoincrement=False, nullable=False),
        sa.Column("fingerprint", sa.VARCHAR(length=64), autoincrement=False, nullable=True),
        sa.Column("import_batch_id", sa.UUID(), autoincrement=False, nullable=True),
        sa.Column("id", sa.UUID(), autoincrement=False, nullable=False),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column("category_id", sa.UUID(), autoincrement=False, nullable=True),
        sa.Column("transfer_group_id", sa.UUID(), autoincrement=False, nullable=True),
        sa.Column("budget_month", sa.DATE(), autoincrement=False, nullable=True),
        sa.Column("bank_label", sa.TEXT(), autoincrement=False, nullable=True),
        sa.Column("entered_on", sa.DATE(), autoincrement=False, nullable=True),
        sa.Column("note", sa.VARCHAR(length=500), autoincrement=False, nullable=True),
        sa.CheckConstraint(
            "EXTRACT(day FROM budget_month) = 1::numeric",
            name=op.f("ck_transaction_budget_month_first_day"),
        ),
        sa.ForeignKeyConstraint(
            ["account_id"], ["account.id"], name=op.f("fk_transaction_account_id_account")
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["category.id"],
            name=op.f("fk_transaction_category_id_category"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["import_batch_id"],
            ["import_batch.id"],
            name=op.f("fk_transaction_import_batch_id_import_batch"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_transaction")),
    )
    op.create_index(
        op.f("uq_transaction_account_fingerprint"),
        "transaction",
        ["account_id", "fingerprint"],
        unique=True,
    )
    op.create_index(
        op.f("ix_transaction_transfer_group_id"), "transaction", ["transfer_group_id"], unique=False
    )
    op.create_index(
        op.f("ix_transaction_import_batch_id"), "transaction", ["import_batch_id"], unique=False
    )
    op.create_index(
        op.f("ix_transaction_category_id"), "transaction", ["category_id"], unique=False
    )
    op.create_index(
        op.f("ix_transaction_account_booked_on"),
        "transaction",
        ["account_id", "booked_on"],
        unique=False,
    )
    op.create_table(
        "transaction_part",
        sa.Column("transaction_id", sa.UUID(), autoincrement=False, nullable=False),
        sa.Column("position", sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column("category_id", sa.UUID(), autoincrement=False, nullable=True),
        sa.Column("amount", sa.NUMERIC(precision=14, scale=2), autoincrement=False, nullable=False),
        sa.Column("id", sa.UUID(), autoincrement=False, nullable=False),
        sa.CheckConstraint(
            "amount <> 0::numeric", name=op.f("ck_transaction_part_amount_not_zero")
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["category.id"],
            name=op.f("fk_transaction_part_category_id_category"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["transaction_id"],
            ["transaction.id"],
            name=op.f("fk_transaction_part_transaction_id_transaction"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_transaction_part")),
    )
    op.create_index(
        op.f("uq_transaction_part_position"),
        "transaction_part",
        ["transaction_id", "position"],
        unique=True,
    )
    op.create_index(
        op.f("ix_transaction_part_transaction_id"),
        "transaction_part",
        ["transaction_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_transaction_part_category_id"), "transaction_part", ["category_id"], unique=False
    )
    op.create_table(
        "budget_plan",
        sa.Column("household_id", sa.UUID(), autoincrement=False, nullable=False),
        sa.Column("kind", sa.VARCHAR(length=10), autoincrement=False, nullable=False),
        sa.Column("year", sa.SMALLINT(), autoincrement=False, nullable=False),
        sa.Column("number", sa.SMALLINT(), autoincrement=False, nullable=False),
        sa.Column("start_month", sa.DATE(), autoincrement=False, nullable=False),
        sa.Column("end_month", sa.DATE(), autoincrement=False, nullable=False),
        sa.Column(
            "expected_income", sa.NUMERIC(precision=14, scale=2), autoincrement=False, nullable=True
        ),
        sa.Column("note", sa.TEXT(), autoincrement=False, nullable=True),
        sa.Column("close_reason", sa.TEXT(), autoincrement=False, nullable=True),
        sa.Column("id", sa.UUID(), autoincrement=False, nullable=False),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            autoincrement=False,
            nullable=False,
        ),
        sa.CheckConstraint(
            "kind IN ('year', 'semester', 'quarter')",
            name=op.f("ck_budget_plan_kind"),
        ),
        sa.CheckConstraint(
            "EXTRACT(day FROM start_month) = 1::numeric"
            " AND EXTRACT(day FROM end_month) = 1::numeric",
            name=op.f("ck_budget_plan_months_first_day"),
        ),
        sa.CheckConstraint(
            "expected_income IS NULL OR expected_income >= 0::numeric",
            name=op.f("ck_budget_plan_income_not_negative"),
        ),
        sa.CheckConstraint(
            "start_month <= end_month", name=op.f("ck_budget_plan_start_before_end")
        ),
        sa.ForeignKeyConstraint(
            ["household_id"], ["household.id"], name=op.f("fk_budget_plan_household_id_household")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_budget_plan")),
    )
    op.create_index(
        op.f("ix_budget_plan_household_id"), "budget_plan", ["household_id"], unique=False
    )
    op.create_table(
        "budget_plan_target",
        sa.Column("plan_id", sa.UUID(), autoincrement=False, nullable=False),
        sa.Column("category_id", sa.UUID(), autoincrement=False, nullable=False),
        sa.Column("amount", sa.NUMERIC(precision=14, scale=2), autoincrement=False, nullable=False),
        sa.Column("id", sa.UUID(), autoincrement=False, nullable=False),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column("paid_from", sa.VARCHAR(length=10), autoincrement=False, nullable=True),
        sa.CheckConstraint(
            "paid_from IN ('joint', 'personal')",
            name=op.f("ck_budget_plan_target_paid_from"),
        ),
        sa.CheckConstraint(
            "amount >= 0::numeric", name=op.f("ck_budget_plan_target_amount_not_negative")
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["category.id"],
            name=op.f("fk_budget_plan_target_category_id_category"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"],
            ["budget_plan.id"],
            name=op.f("fk_budget_plan_target_plan_id_budget_plan"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_budget_plan_target")),
        sa.UniqueConstraint(
            "plan_id",
            "category_id",
            name=op.f("uq_budget_plan_target_plan_id_category_id"),
            postgresql_include=[],
            postgresql_nulls_not_distinct=False,
        ),
    )
    op.create_table(
        "categorization_rule",
        sa.Column("household_id", sa.UUID(), autoincrement=False, nullable=False),
        sa.Column("category_id", sa.UUID(), autoincrement=False, nullable=False),
        sa.Column("priority", sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column("label_contains", sa.VARCHAR(length=100), autoincrement=False, nullable=True),
        sa.Column(
            "amount_min", sa.NUMERIC(precision=14, scale=2), autoincrement=False, nullable=True
        ),
        sa.Column(
            "amount_max", sa.NUMERIC(precision=14, scale=2), autoincrement=False, nullable=True
        ),
        sa.Column("account_id", sa.UUID(), autoincrement=False, nullable=True),
        sa.Column("id", sa.UUID(), autoincrement=False, nullable=False),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            autoincrement=False,
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["account.id"],
            name=op.f("fk_categorization_rule_account_id_account"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["category.id"],
            name=op.f("fk_categorization_rule_category_id_category"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["household_id"],
            ["household.id"],
            name=op.f("fk_categorization_rule_household_id_household"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_categorization_rule")),
    )
    op.create_index(
        op.f("ix_categorization_rule_household_id"),
        "categorization_rule",
        ["household_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_categorization_rule_category_id"),
        "categorization_rule",
        ["category_id"],
        unique=False,
    )
    op.create_table(
        "recurring_item",
        sa.Column("household_id", sa.UUID(), autoincrement=False, nullable=False),
        sa.Column("account_id", sa.UUID(), autoincrement=False, nullable=False),
        sa.Column("category_id", sa.UUID(), autoincrement=False, nullable=True),
        sa.Column("label", sa.VARCHAR(length=100), autoincrement=False, nullable=False),
        sa.Column("amount", sa.NUMERIC(precision=14, scale=2), autoincrement=False, nullable=False),
        sa.Column("frequency", sa.VARCHAR(length=10), autoincrement=False, nullable=False),
        sa.Column("day", sa.SMALLINT(), autoincrement=False, nullable=False),
        sa.Column("start_on", sa.DATE(), autoincrement=False, nullable=False),
        sa.Column("end_on", sa.DATE(), autoincrement=False, nullable=True),
        sa.Column(
            "estimated",
            sa.BOOLEAN(),
            server_default=sa.text("false"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "paused",
            sa.BOOLEAN(),
            server_default=sa.text("false"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), autoincrement=False, nullable=False),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column("destination_id", sa.UUID(), autoincrement=False, nullable=True),
        sa.CheckConstraint(
            "frequency IN ('weekly', 'monthly', 'quarterly', 'yearly')",
            name=op.f("ck_recurring_item_recurring_frequency"),
        ),
        sa.CheckConstraint("day >= 0 AND day <= 31", name=op.f("ck_recurring_item_day_range")),
        sa.CheckConstraint(
            "destination_id IS NULL OR category_id IS NULL",
            name=op.f("ck_recurring_item_transfer_no_category"),
        ),
        sa.CheckConstraint(
            "destination_id IS NULL OR destination_id <> account_id",
            name=op.f("ck_recurring_item_transfer_accounts"),
        ),
        sa.CheckConstraint(
            "end_on IS NULL OR end_on >= start_on", name=op.f("ck_recurring_item_start_before_end")
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["account.id"],
            name=op.f("fk_recurring_item_account_id_account"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["category.id"],
            name=op.f("fk_recurring_item_category_id_category"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["destination_id"],
            ["account.id"],
            name=op.f("fk_recurring_item_destination_id_account"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["household_id"],
            ["household.id"],
            name=op.f("fk_recurring_item_household_id_household"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_recurring_item")),
    )
    op.create_index(
        op.f("ix_recurring_item_household_id"), "recurring_item", ["household_id"], unique=False
    )
    op.create_index(
        op.f("ix_recurring_item_destination_id"), "recurring_item", ["destination_id"], unique=False
    )
    op.create_index(
        op.f("ix_recurring_item_account_id"), "recurring_item", ["account_id"], unique=False
    )
    op.create_table(
        "recurring_skip",
        sa.Column("item_id", sa.UUID(), autoincrement=False, nullable=False),
        sa.Column("due_on", sa.DATE(), autoincrement=False, nullable=False),
        sa.Column("id", sa.UUID(), autoincrement=False, nullable=False),
        sa.ForeignKeyConstraint(
            ["item_id"],
            ["recurring_item.id"],
            name=op.f("fk_recurring_skip_item_id_recurring_item"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_recurring_skip")),
        sa.UniqueConstraint(
            "item_id",
            "due_on",
            name=op.f("uq_recurring_skip_item_id_due_on"),
            postgresql_include=[],
            postgresql_nulls_not_distinct=False,
        ),
    )
    op.create_table(
        "dismissed_suggestion",
        sa.Column("account_id", sa.UUID(), autoincrement=False, nullable=False),
        sa.Column("label", sa.VARCHAR(length=200), autoincrement=False, nullable=False),
        sa.Column("id", sa.UUID(), autoincrement=False, nullable=False),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["account.id"],
            name=op.f("fk_dismissed_suggestion_account_id_account"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dismissed_suggestion")),
        sa.UniqueConstraint(
            "account_id",
            "label",
            name=op.f("uq_dismissed_suggestion_account_id_label"),
            postgresql_include=[],
            postgresql_nulls_not_distinct=False,
        ),
    )
    _audit_check(AUDIT_BEFORE)
