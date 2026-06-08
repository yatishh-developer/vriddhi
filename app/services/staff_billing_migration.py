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
        (
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_transactions_idempotency_key "
            "ON transactions (idempotency_key) WHERE idempotency_key IS NOT NULL"
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
    ]

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
