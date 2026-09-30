"""Add normalized KOT v2 records without changing legacy staff KOT data.

Revision ID: 20261001_05
Revises: 20261001_04
Create Date: 2026-10-01
"""

from alembic import op
import sqlalchemy as sa


revision = "20261001_05"
down_revision = "20261001_04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "kitchen_kot_sequences",
        sa.Column("business_id", sa.String(), sa.ForeignKey("businesses.id"), primary_key=True),
        sa.Column("branch_id", sa.String(), primary_key=True),
        sa.Column("current_value", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_table(
        "kitchen_order_tickets",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("business_id", sa.String(), sa.ForeignKey("businesses.id"), nullable=False),
        sa.Column("branch_id", sa.String(), nullable=False),
        sa.Column("order_id", sa.String(), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("table_session_id", sa.String(), sa.ForeignKey("table_sessions.id"), nullable=True),
        sa.Column("kot_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="PENDING"),
        sa.Column("created_by_principal_id", sa.String(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("preparing_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ready_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("served_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("idempotency_key", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_kots_business_branch_order_status_created", "kitchen_order_tickets", ["business_id", "branch_id", "order_id", "status", "created_at"])
    op.create_index("ux_kots_branch_number", "kitchen_order_tickets", ["business_id", "branch_id", "kot_number"], unique=True)
    op.create_index("ux_kots_idempotency", "kitchen_order_tickets", ["business_id", "branch_id", "order_id", "idempotency_key"], unique=True)

    op.create_table(
        "kitchen_order_ticket_items",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("kot_id", sa.String(), sa.ForeignKey("kitchen_order_tickets.id"), nullable=False),
        sa.Column("order_item_id", sa.String(), sa.ForeignKey("order_items.id"), nullable=False),
        sa.Column("product_id", sa.String(), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("product_name_snapshot", sa.String(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("notes_snapshot", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_kot_items_kot_order_item", "kitchen_order_ticket_items", ["kot_id", "order_item_id"])
    op.create_table(
        "kitchen_kot_cancellations",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("business_id", sa.String(), sa.ForeignKey("businesses.id"), nullable=False),
        sa.Column("branch_id", sa.String(), nullable=False),
        sa.Column("order_id", sa.String(), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("order_item_id", sa.String(), sa.ForeignKey("order_items.id"), nullable=False),
        sa.Column("kot_id", sa.String(), sa.ForeignKey("kitchen_order_tickets.id"), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_by_principal_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )


def downgrade() -> None:
    op.drop_table("kitchen_kot_cancellations")
    op.drop_index("ix_kot_items_kot_order_item", table_name="kitchen_order_ticket_items")
    op.drop_table("kitchen_order_ticket_items")
    op.drop_index("ux_kots_idempotency", table_name="kitchen_order_tickets")
    op.drop_index("ux_kots_branch_number", table_name="kitchen_order_tickets")
    op.drop_index("ix_kots_business_branch_order_status_created", table_name="kitchen_order_tickets")
    op.drop_table("kitchen_order_tickets")
    op.drop_table("kitchen_kot_sequences")
