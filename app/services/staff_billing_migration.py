import logging

from sqlalchemy import text


logger = logging.getLogger("vriddhi.staff_billing_migration")


def run_staff_billing_migrations(engine) -> None:
    """Apply small additive migrations needed by the staff billing API.

    The project currently relies on SQLAlchemy create_all at startup, which does
    not alter existing tables. These statements are intentionally nullable or
    defaulted so existing admin-app rows keep working.
    """

    if engine.dialect.name != "postgresql":
        logger.warning(
            "Skipping staff billing shared-table migrations for %s dialect.",
            engine.dialect.name,
        )
        return

    statements = [
        # Shared DB safety: barcodes and idempotency keys must not collide
        # across independent businesses/branches/apps.
        "ALTER TABLE products DROP CONSTRAINT IF EXISTS products_barcode_key",
        "DROP INDEX IF EXISTS ix_products_barcode",
        (
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_products_business_barcode "
            "ON products (business_id, barcode) WHERE barcode IS NOT NULL AND barcode <> ''"
        ),
        "ALTER TABLE transactions ADD COLUMN IF NOT EXISTS branch_id VARCHAR DEFAULT 'main'",
        "ALTER TABLE transactions ADD COLUMN IF NOT EXISTS card_amount DOUBLE PRECISION DEFAULT 0",
        "ALTER TABLE transactions ADD COLUMN IF NOT EXISTS other_paid_amount DOUBLE PRECISION DEFAULT 0",
        "ALTER TABLE transactions ADD COLUMN IF NOT EXISTS created_by VARCHAR NULL REFERENCES users(id)",
        "ALTER TABLE transactions ADD COLUMN IF NOT EXISTS created_by_staff_id VARCHAR NULL",
        "ALTER TABLE transactions ADD COLUMN IF NOT EXISTS source_app VARCHAR NOT NULL DEFAULT 'admin_app'",
        "ALTER TABLE transactions ADD COLUMN IF NOT EXISTS sync_status VARCHAR NOT NULL DEFAULT 'synced'",
        "ALTER TABLE transactions ADD COLUMN IF NOT EXISTS idempotency_key VARCHAR NULL",
        "ALTER TABLE transactions ADD COLUMN IF NOT EXISTS device_id VARCHAR NULL",
        "CREATE INDEX IF NOT EXISTS ix_transactions_branch_id ON transactions (branch_id)",
        "CREATE INDEX IF NOT EXISTS ix_transactions_source_app ON transactions (source_app)",
        "CREATE INDEX IF NOT EXISTS ix_transactions_sync_status ON transactions (sync_status)",
        "CREATE INDEX IF NOT EXISTS ix_transactions_created_by_staff_id ON transactions (created_by_staff_id)",
        "ALTER TABLE transactions DROP CONSTRAINT IF EXISTS transactions_idempotency_key_key",
        "DROP INDEX IF EXISTS ux_transactions_idempotency_key",
        (
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_transactions_shared_idempotency_key "
            "ON transactions (business_id, branch_id, source_app, idempotency_key) "
            "WHERE idempotency_key IS NOT NULL"
        ),
        "ALTER TABLE inventory_movements ADD COLUMN IF NOT EXISTS branch_id VARCHAR DEFAULT 'main'",
        "ALTER TABLE inventory_movements ADD COLUMN IF NOT EXISTS created_by_staff_id VARCHAR NULL",
        "ALTER TABLE inventory_movements ADD COLUMN IF NOT EXISTS source_app VARCHAR NOT NULL DEFAULT 'admin_app'",
        "ALTER TABLE inventory_movements ADD COLUMN IF NOT EXISTS sync_status VARCHAR NOT NULL DEFAULT 'synced'",
        "CREATE INDEX IF NOT EXISTS ix_inventory_movements_branch_id ON inventory_movements (branch_id)",
        (
            "CREATE INDEX IF NOT EXISTS ix_inventory_movements_created_by_staff_id "
            "ON inventory_movements (created_by_staff_id)"
        ),
        "CREATE INDEX IF NOT EXISTS ix_inventory_movements_source_app ON inventory_movements (source_app)",
        "CREATE INDEX IF NOT EXISTS ix_inventory_movements_sync_status ON inventory_movements (sync_status)",
        "ALTER TABLE staff_profiles ADD COLUMN IF NOT EXISTS firebase_uid VARCHAR NULL",
        "ALTER TABLE staff_profiles ADD COLUMN IF NOT EXISTS auth_provider VARCHAR NULL",
        "ALTER TABLE staff_profiles ADD COLUMN IF NOT EXISTS auth_email VARCHAR NULL",
        "ALTER TABLE staff_profiles ADD COLUMN IF NOT EXISTS auth_display_name VARCHAR NULL",
        "ALTER TABLE staff_profiles ADD COLUMN IF NOT EXISTS auth_phone_number VARCHAR NULL",
        (
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_staff_profiles_firebase_uid "
            "ON staff_profiles (firebase_uid) WHERE firebase_uid IS NOT NULL"
        ),
        "CREATE INDEX IF NOT EXISTS ix_staff_profiles_auth_email ON staff_profiles (auth_email)",
        "ALTER TABLE staff_kots DROP CONSTRAINT IF EXISTS staff_kots_idempotency_key_key",
        (
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_staff_kots_shared_idempotency_key "
            "ON staff_kots (business_id, branch_id, idempotency_key) "
            "WHERE idempotency_key IS NOT NULL"
        ),
        "ALTER TABLE staff_held_bills DROP CONSTRAINT IF EXISTS staff_held_bills_idempotency_key_key",
        (
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_staff_held_bills_shared_idempotency_key "
            "ON staff_held_bills (business_id, branch_id, idempotency_key) "
            "WHERE idempotency_key IS NOT NULL"
        ),
    ]

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
