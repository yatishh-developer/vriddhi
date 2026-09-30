"""Create the pre-Phase-1 application schema on an empty database.

The original application created these tables via ``Base.metadata.create_all``
at startup.  That left Alembic's first revision (auth_sessions) referring to
tables that did not exist on a fresh production database.  This revision is a
static, deterministic baseline for the legacy application schema only; the
Phase 1-6 revisions remain responsible for their own additions.
"""

from alembic import op
import sqlalchemy as sa


revision = "20261001_00"
down_revision = None
branch_labels = None
depends_on = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    ]


def upgrade() -> None:
    # Core application tables.  Keep this static rather than importing model
    # metadata, so future model edits cannot rewrite historical bootstrap DDL.
    op.create_table(
        "businesses",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("business_type", sa.String(), nullable=False),
        sa.Column("gst_number", sa.String()),
        sa.Column("owner_name", sa.String()), sa.Column("phone", sa.String()),
        sa.Column("email", sa.String()), sa.Column("address", sa.String()),
        sa.Column("city", sa.String()), sa.Column("state", sa.String()),
        sa.Column("pincode", sa.String()), sa.Column("upi_id", sa.String()),
        sa.Column("is_intra_state", sa.Boolean()), sa.Column("default_discount", sa.String()),
        *_timestamps(),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("business_id", sa.String(), sa.ForeignKey("businesses.id"), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=False),
        *_timestamps(),
    )
    op.create_index("ix_users_business_id", "users", ["business_id"])
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "products",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("business_id", sa.String(), sa.ForeignKey("businesses.id"), nullable=False),
        sa.Column("name", sa.String(), nullable=False), sa.Column("barcode", sa.String()),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column("gst_percentage", sa.Numeric(5, 2), nullable=False),
        sa.Column("hsn_code", sa.String()), sa.Column("image_url", sa.String()),
        sa.Column("category", sa.String()), sa.Column("in_stock", sa.Boolean()),
        sa.Column("is_stockless", sa.Boolean()), sa.Column("stock_quantity", sa.Integer()),
        sa.Column("description", sa.String()), sa.Column("ingredients", sa.String()),
        *_timestamps(), sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_products_business_id", "products", ["business_id"])
    op.create_index("ix_products_barcode", "products", ["barcode"])
    op.create_index(
        "ux_products_business_barcode", "products", ["business_id", "barcode"], unique=True,
        postgresql_where=sa.text("barcode IS NOT NULL AND barcode <> ''"),
    )
    op.create_table(
        "customers",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("business_id", sa.String(), sa.ForeignKey("businesses.id"), nullable=False),
        sa.Column("name", sa.String(), nullable=False), sa.Column("phone", sa.String(), nullable=False),
        sa.Column("email", sa.String()), sa.Column("address", sa.String()),
        sa.Column("balance_remaining", sa.Numeric(12, 2)), sa.Column("loyal_customer", sa.Boolean()),
        sa.Column("preset_discount", sa.Numeric(12, 2)), *_timestamps(),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    # ``order_id`` is deliberately absent: Phase 3 adds it with its FK.
    op.create_table(
        "transactions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("business_id", sa.String(), sa.ForeignKey("businesses.id"), nullable=False),
        sa.Column("branch_id", sa.String()), sa.Column("customer_id", sa.String(), sa.ForeignKey("customers.id")),
        sa.Column("flow", sa.String()), sa.Column("bill_no", sa.String()), sa.Column("bill_date", sa.String()),
        sa.Column("bill_date_text", sa.String()), sa.Column("due_date", sa.String()),
        sa.Column("customer_name", sa.String()), sa.Column("customer_phone", sa.String()), sa.Column("customer_address", sa.String()),
        sa.Column("payment_method", sa.String(), nullable=False), sa.Column("payment_option", sa.String()),
        sa.Column("cash_amount", sa.Numeric(12, 2)), sa.Column("upi_amount", sa.Numeric(12, 2)),
        sa.Column("card_amount", sa.Numeric(12, 2)), sa.Column("other_paid_amount", sa.Numeric(12, 2)),
        sa.Column("credit_amount", sa.Numeric(12, 2)), sa.Column("discount", sa.Numeric(12, 2)),
        sa.Column("is_parcel", sa.Boolean()), sa.Column("is_hold", sa.Boolean()), sa.Column("items_json", sa.Text()),
        sa.Column("total_amount", sa.Numeric(12, 2), nullable=False), sa.Column("subtotal", sa.Numeric(12, 2)),
        sa.Column("total_cgst", sa.Numeric(12, 2)), sa.Column("total_sgst", sa.Numeric(12, 2)),
        sa.Column("total_igst", sa.Numeric(12, 2)), sa.Column("total_tax", sa.Numeric(12, 2)),
        sa.Column("old_balance", sa.Numeric(12, 2)), sa.Column("is_intra_state", sa.Boolean()),
        sa.Column("status", sa.String()), sa.Column("created_by", sa.String(), sa.ForeignKey("users.id")),
        sa.Column("created_by_staff_id", sa.String()), sa.Column("source_app", sa.String(), nullable=False),
        sa.Column("sync_status", sa.String(), nullable=False), sa.Column("idempotency_key", sa.String()),
        sa.Column("device_id", sa.String()), *_timestamps(),
    )
    for name, columns in (
        ("ix_transactions_business_id", ["business_id"]), ("ix_transactions_branch_id", ["branch_id"]),
        ("ix_transactions_created_by_staff_id", ["created_by_staff_id"]),
        ("ix_transactions_source_app", ["source_app"]), ("ix_transactions_sync_status", ["sync_status"]),
        ("ix_transactions_idempotency_key", ["idempotency_key"]),
    ):
        op.create_index(name, "transactions", columns)
    op.create_table(
        "transaction_items",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("transaction_id", sa.String(), sa.ForeignKey("transactions.id"), nullable=False),
        sa.Column("product_id", sa.String(), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("product_name", sa.String(), nullable=False), sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("price", sa.Numeric(12, 2), nullable=False), sa.Column("subtotal", sa.Numeric(12, 2), nullable=False),
        *_timestamps(),
    )
    op.create_index("ix_transaction_items_transaction_id", "transaction_items", ["transaction_id"])
    op.create_index("ix_transaction_items_product_id", "transaction_items", ["product_id"])
    op.create_table(
        "inventory_movements",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("business_id", sa.String(), sa.ForeignKey("businesses.id"), nullable=False),
        sa.Column("branch_id", sa.String()), sa.Column("product_id", sa.String(), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("movement_type", sa.Enum("SALE", "REFUND", "MANUAL_ADD", "MANUAL_REMOVE", "PURCHASE", name="inventorymovementtype"), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False), sa.Column("before_stock", sa.Integer(), nullable=False),
        sa.Column("after_stock", sa.Integer(), nullable=False), sa.Column("reference_id", sa.String()), sa.Column("notes", sa.String()),
        sa.Column("created_by", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_by_staff_id", sa.String()), sa.Column("source_app", sa.String(), nullable=False),
        sa.Column("sync_status", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    for name, columns in (
        ("ix_inventory_movements_business_id", ["business_id"]), ("ix_inventory_movements_branch_id", ["branch_id"]),
        ("ix_inventory_movements_product_id", ["product_id"]), ("ix_inventory_movements_created_by_staff_id", ["created_by_staff_id"]),
        ("ix_inventory_movements_source_app", ["source_app"]), ("ix_inventory_movements_sync_status", ["sync_status"]),
    ):
        op.create_index(name, "inventory_movements", columns)
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("business_id", sa.String(), sa.ForeignKey("businesses.id"), nullable=False),
        sa.Column("plan_code", sa.String(), nullable=False), sa.Column("billing_cycle", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False), sa.Column("auto_renew", sa.Boolean(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("current_period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("trial_ends_at", sa.DateTime(timezone=True)), sa.Column("cancelled_at", sa.DateTime(timezone=True)),
        sa.Column("invoices_used_in_period", sa.Integer(), nullable=False), sa.Column("ai_credits_used_in_period", sa.Integer(), nullable=False),
        sa.Column("price_amount", sa.Float(), nullable=False), sa.Column("currency", sa.String(), nullable=False),
        sa.Column("last_expiry_reminder_at", sa.DateTime(timezone=True)), *_timestamps(),
    )
    op.create_index("ix_subscriptions_business_id", "subscriptions", ["business_id"], unique=True)

    _create_staff_schema()


def _create_staff_schema() -> None:
    """Static legacy staff tables, including the former startup migrations."""
    op.create_table(
        "staff_invites",
        sa.Column("id", sa.String(), primary_key=True), sa.Column("business_id", sa.String(), sa.ForeignKey("businesses.id"), nullable=False),
        sa.Column("branch_id", sa.String(), nullable=False), sa.Column("staff_name", sa.String(), nullable=False),
        sa.Column("staff_role", sa.String(), nullable=False), sa.Column("invite_code_hash", sa.String(), nullable=False),
        sa.Column("code_length", sa.Integer(), nullable=False), sa.Column("allowed_apps", sa.Text(), nullable=False),
        sa.Column("permissions_json", sa.Text(), nullable=False), sa.Column("feature_flags_snapshot", sa.Text(), nullable=False),
        sa.Column("business_type_snapshot", sa.String()), sa.Column("business_name", sa.String()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False), sa.Column("max_uses", sa.Integer(), nullable=False),
        sa.Column("used_count", sa.Integer(), nullable=False), sa.Column("status", sa.String(), nullable=False),
        sa.Column("created_by", sa.String(), sa.ForeignKey("users.id")), sa.Column("created_by_staff_id", sa.String()),
        sa.Column("source_app", sa.String(), nullable=False), sa.Column("sync_status", sa.String(), nullable=False), *_timestamps(),
    )
    for name, columns, unique in (
        ("ix_staff_invites_business_id", ["business_id"], False), ("ix_staff_invites_branch_id", ["branch_id"], False),
        ("ix_staff_invites_invite_code_hash", ["invite_code_hash"], True), ("ix_staff_invites_expires_at", ["expires_at"], False),
        ("ix_staff_invites_status", ["status"], False), ("ix_staff_invites_created_by", ["created_by"], False),
        ("ix_staff_invites_created_by_staff_id", ["created_by_staff_id"], False), ("ix_staff_invites_source_app", ["source_app"], False),
        ("ix_staff_invites_sync_status", ["sync_status"], False),
    ):
        op.create_index(name, "staff_invites", columns, unique=unique)
    op.create_table(
        "staff_profiles",
        sa.Column("id", sa.String(), primary_key=True), sa.Column("business_id", sa.String(), sa.ForeignKey("businesses.id"), nullable=False),
        sa.Column("branch_id", sa.String(), nullable=False), sa.Column("invite_id", sa.String(), sa.ForeignKey("staff_invites.id")),
        sa.Column("staff_name", sa.String(), nullable=False), sa.Column("role", sa.String(), nullable=False),
        sa.Column("permissions_json", sa.Text(), nullable=False), sa.Column("allowed_apps", sa.Text(), nullable=False),
        sa.Column("status", sa.String(), nullable=False), sa.Column("last_seen_at", sa.DateTime(timezone=True)),
        sa.Column("firebase_uid", sa.String()), sa.Column("auth_provider", sa.String()), sa.Column("auth_email", sa.String()),
        sa.Column("auth_display_name", sa.String()), sa.Column("auth_phone_number", sa.String()),
        sa.Column("created_by", sa.String(), sa.ForeignKey("users.id")), sa.Column("created_by_staff_id", sa.String()),
        sa.Column("source_app", sa.String(), nullable=False), sa.Column("sync_status", sa.String(), nullable=False), *_timestamps(),
    )
    for name, columns, unique in (
        ("ix_staff_profiles_business_id", ["business_id"], False), ("ix_staff_profiles_branch_id", ["branch_id"], False),
        ("ix_staff_profiles_invite_id", ["invite_id"], False), ("ix_staff_profiles_status", ["status"], False),
        ("ix_staff_profiles_firebase_uid", ["firebase_uid"], True), ("ix_staff_profiles_auth_email", ["auth_email"], False),
        ("ix_staff_profiles_created_by", ["created_by"], False), ("ix_staff_profiles_created_by_staff_id", ["created_by_staff_id"], False),
        ("ix_staff_profiles_source_app", ["source_app"], False), ("ix_staff_profiles_sync_status", ["sync_status"], False),
    ):
        op.create_index(name, "staff_profiles", columns, unique=unique)
    _create_staff_activity_tables()


def _create_staff_activity_tables() -> None:
    def activity_columns() -> list[sa.Column]:
        return [
            sa.Column("id", sa.String(), primary_key=True), sa.Column("business_id", sa.String(), sa.ForeignKey("businesses.id"), nullable=False),
            sa.Column("branch_id", sa.String(), nullable=False), sa.Column("staff_id", sa.String(), sa.ForeignKey("staff_profiles.id")),
            sa.Column("staff_name", sa.String()), sa.Column("status", sa.String(), nullable=False),
        ]
    for table, extra in (
        ("staff_kots", [sa.Column("order_type", sa.String()), sa.Column("table_token", sa.String())]),
        ("staff_held_bills", [sa.Column("customer_id", sa.String(), sa.ForeignKey("customers.id")), sa.Column("customer_name", sa.String())]),
    ):
        op.create_table(
            table, *activity_columns(), *extra, sa.Column("items_json", sa.Text(), nullable=False),
            sa.Column("subtotal", sa.Float(), nullable=False), sa.Column("total_tax", sa.Float(), nullable=False), sa.Column("total_amount", sa.Float(), nullable=False),
            sa.Column("bill_transaction_id", sa.String(), sa.ForeignKey("transactions.id")), sa.Column("idempotency_key", sa.String()),
            sa.Column("created_by", sa.String(), sa.ForeignKey("users.id")), sa.Column("created_by_staff_id", sa.String()),
            sa.Column("source_app", sa.String(), nullable=False), sa.Column("sync_status", sa.String(), nullable=False), *_timestamps(),
        )
        for suffix in ("business_id", "branch_id", "staff_id", "status", "bill_transaction_id", "idempotency_key", "created_by", "created_by_staff_id", "source_app", "sync_status"):
            op.create_index(f"ix_{table}_{suffix}", table, [suffix])
        if table == "staff_held_bills":
            op.create_index("ix_staff_held_bills_customer_id", table, ["customer_id"])
        op.create_index(
            f"ux_{table}_shared_idempotency_key", table, ["business_id", "branch_id", "idempotency_key"], unique=True,
            postgresql_where=sa.text("idempotency_key IS NOT NULL"),
        )
    op.create_table(
        "staff_payments",
        sa.Column("id", sa.String(), primary_key=True), sa.Column("business_id", sa.String(), sa.ForeignKey("businesses.id"), nullable=False),
        sa.Column("branch_id", sa.String(), nullable=False), sa.Column("staff_id", sa.String(), sa.ForeignKey("staff_profiles.id")), sa.Column("staff_name", sa.String()),
        sa.Column("bill_transaction_id", sa.String(), sa.ForeignKey("transactions.id")),
        sa.Column("cash_amount", sa.Numeric(12, 2), nullable=False), sa.Column("upi_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("card_amount", sa.Numeric(12, 2), nullable=False), sa.Column("other_paid_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("credit_amount", sa.Numeric(12, 2), nullable=False), sa.Column("total_paid_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("payment_json", sa.Text(), nullable=False), sa.Column("created_by", sa.String(), sa.ForeignKey("users.id")),
        sa.Column("created_by_staff_id", sa.String()), sa.Column("source_app", sa.String(), nullable=False),
        sa.Column("sync_status", sa.String(), nullable=False), *_timestamps(),
    )
    for suffix in ("business_id", "branch_id", "staff_id", "bill_transaction_id", "created_by", "created_by_staff_id", "source_app", "sync_status"):
        op.create_index(f"ix_staff_payments_{suffix}", "staff_payments", [suffix])
    op.create_table(
        "staff_process_locks",
        sa.Column("process_id", sa.String(), primary_key=True), sa.Column("process_type", sa.String(), nullable=False), sa.Column("entity_id", sa.String(), nullable=False),
        sa.Column("business_id", sa.String(), sa.ForeignKey("businesses.id"), nullable=False), sa.Column("branch_id", sa.String(), nullable=False),
        sa.Column("handled_by_staff_id", sa.String(), sa.ForeignKey("staff_profiles.id")), sa.Column("handled_by_staff_name", sa.String()),
        sa.Column("status", sa.String(), nullable=False), sa.Column("locked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=False), sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(), sa.ForeignKey("users.id")), sa.Column("created_by_staff_id", sa.String()),
        sa.Column("source_app", sa.String(), nullable=False), sa.Column("sync_status", sa.String(), nullable=False), *_timestamps(),
    )
    for suffix in ("process_type", "entity_id", "business_id", "branch_id", "handled_by_staff_id", "status", "expires_at", "created_by", "created_by_staff_id", "source_app", "sync_status"):
        op.create_index(f"ix_staff_process_locks_{suffix}", "staff_process_locks", [suffix])
    op.create_table(
        "staff_realtime_events",
        sa.Column("event_id", sa.String(), primary_key=True), sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("entity_type", sa.String(), nullable=False), sa.Column("entity_id", sa.String(), nullable=False),
        sa.Column("business_id", sa.String(), sa.ForeignKey("businesses.id"), nullable=False), sa.Column("branch_id", sa.String(), nullable=False),
        sa.Column("staff_id", sa.String(), sa.ForeignKey("staff_profiles.id")), sa.Column("device_id", sa.String()),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False), sa.Column("payload_json", sa.Text(), nullable=False), sa.Column("processed", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.String(), sa.ForeignKey("users.id")), sa.Column("created_by_staff_id", sa.String()),
        sa.Column("source_app", sa.String(), nullable=False), sa.Column("sync_status", sa.String(), nullable=False), *_timestamps(),
    )
    for suffix in ("event_type", "entity_type", "entity_id", "business_id", "branch_id", "staff_id", "device_id", "created_by", "created_by_staff_id", "source_app", "sync_status"):
        op.create_index(f"ix_staff_realtime_events_{suffix}", "staff_realtime_events", [suffix])


def downgrade() -> None:
    # Downgrade is intentionally explicit and reverse dependency ordered.
    for table in (
        "staff_realtime_events", "staff_process_locks", "staff_payments", "staff_held_bills", "staff_kots",
        "staff_profiles", "staff_invites", "subscriptions", "inventory_movements", "transaction_items",
        "transactions", "customers", "products", "users", "businesses",
    ):
        op.drop_table(table)
    sa.Enum(name="inventorymovementtype").drop(op.get_bind(), checkfirst=True)
