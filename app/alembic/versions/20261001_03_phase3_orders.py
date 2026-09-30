"""Add normalized orders and link finalized transactions to their order.

Revision ID: 20261001_03
Revises: 20261001_02
Create Date: 2026-10-01
"""

from alembic import op
import sqlalchemy as sa


revision = "20261001_03"
down_revision = "20261001_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "orders",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("business_id", sa.String(), sa.ForeignKey("businesses.id"), nullable=False),
        sa.Column("branch_id", sa.String(), nullable=False, server_default="main"),
        sa.Column("order_type", sa.String(), nullable=False, server_default="QUICK"),
        sa.Column("status", sa.String(), nullable=False, server_default="ACTIVE"),
        sa.Column("customer_id", sa.String(), sa.ForeignKey("customers.id"), nullable=True),
        sa.Column("table_session_id", sa.String(), nullable=True),
        sa.Column("cancellation_reason", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_by_staff_id", sa.String(), nullable=True),
        sa.Column("source_app", sa.String(), nullable=False, server_default="unified_api_v1"),
        sa.Column("idempotency_key", sa.String(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_orders_business_branch_status_created", "orders", ["business_id", "branch_id", "status", "created_at"])
    op.create_index("ux_orders_idempotency_key", "orders", ["business_id", "branch_id", "source_app", "idempotency_key"], unique=True)

    op.create_table(
        "order_items",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("order_id", sa.String(), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("business_id", sa.String(), sa.ForeignKey("businesses.id"), nullable=False),
        sa.Column("branch_id", sa.String(), nullable=False),
        sa.Column("product_id", sa.String(), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("product_name_snapshot", sa.String(), nullable=False),
        sa.Column("unit_price_snapshot", sa.Numeric(12, 2), nullable=False),
        sa.Column("tax_rate_snapshot", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="DRAFT"),
        sa.Column("kot_sent_quantity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cancelled_quantity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("billed_quantity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_order_items_order_product_status", "order_items", ["order_id", "product_id", "status"])

    with op.batch_alter_table("transactions") as batch:
        batch.add_column(sa.Column("order_id", sa.String(), nullable=True))
        batch.create_foreign_key("fk_transactions_order_id", "orders", ["order_id"], ["id"])
        batch.create_index("ux_transactions_order_id", ["order_id"], unique=True)


def downgrade() -> None:
    with op.batch_alter_table("transactions") as batch:
        batch.drop_index("ux_transactions_order_id")
        batch.drop_constraint("fk_transactions_order_id", type_="foreignkey")
        batch.drop_column("order_id")
    op.drop_index("ix_order_items_order_product_status", table_name="order_items")
    op.drop_table("order_items")
    op.drop_index("ux_orders_idempotency_key", table_name="orders")
    op.drop_index("ix_orders_business_branch_status_created", table_name="orders")
    op.drop_table("orders")
