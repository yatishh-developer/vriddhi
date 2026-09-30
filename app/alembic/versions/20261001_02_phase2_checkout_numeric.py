"""Convert checkout-critical money columns to NUMERIC and enforce idempotency.

Revision ID: 20261001_02
Revises: 20261001_01
Create Date: 2026-10-01
"""

from alembic import op
import sqlalchemy as sa


revision = "20261001_02"
down_revision = "20261001_01"
branch_labels = None
depends_on = None


MONEY_COLUMNS = {
    "products": [("price", False), ("gst_percentage", False)],
    "customers": [("balance_remaining", True), ("preset_discount", True)],
    "transactions": [
        ("cash_amount", True), ("upi_amount", True), ("card_amount", True),
        ("other_paid_amount", True), ("credit_amount", True), ("discount", True),
        ("total_amount", False), ("subtotal", True), ("total_cgst", True),
        ("total_sgst", True), ("total_igst", True), ("total_tax", True), ("old_balance", True),
    ],
    "transaction_items": [("price", False), ("subtotal", False)],
    "staff_payments": [
        ("cash_amount", False), ("upi_amount", False), ("card_amount", False),
        ("other_paid_amount", False), ("credit_amount", False), ("total_paid_amount", False),
    ],
}


def upgrade() -> None:
    for table_name, columns in MONEY_COLUMNS.items():
        with op.batch_alter_table(table_name) as batch:
            for column_name, nullable in columns:
                batch.alter_column(
                    column_name,
                    existing_type=sa.Float(),
                    type_=sa.Numeric(12, 2),
                    existing_nullable=nullable,
                )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_transactions_shared_idempotency_key "
        "ON transactions (business_id, branch_id, source_app, idempotency_key) "
        "WHERE idempotency_key IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ux_transactions_shared_idempotency_key")
    for table_name, columns in MONEY_COLUMNS.items():
        with op.batch_alter_table(table_name) as batch:
            for column_name, nullable in columns:
                batch.alter_column(
                    column_name,
                    existing_type=sa.Numeric(12, 2),
                    type_=sa.Float(),
                    existing_nullable=nullable,
                )
