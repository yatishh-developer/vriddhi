"""Add restaurant tables, table sessions, and active occupancy links.

Revision ID: 20261001_04
Revises: 20261001_03
Create Date: 2026-10-01
"""

from alembic import op
import sqlalchemy as sa


revision = "20261001_04"
down_revision = "20261001_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "restaurant_tables",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("business_id", sa.String(), sa.ForeignKey("businesses.id"), nullable=False),
        sa.Column("branch_id", sa.String(), nullable=False, server_default="main"),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("code", sa.String(), nullable=True),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("section", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=True),
        sa.Column("x_position", sa.Integer(), nullable=True),
        sa.Column("y_position", sa.Integer(), nullable=True),
        sa.Column("shape", sa.String(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_restaurant_tables_business_branch_active", "restaurant_tables", ["business_id", "branch_id", "is_active"])

    op.create_table(
        "table_sessions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("business_id", sa.String(), sa.ForeignKey("businesses.id"), nullable=False),
        sa.Column("branch_id", sa.String(), nullable=False, server_default="main"),
        sa.Column("primary_table_id", sa.String(), sa.ForeignKey("restaurant_tables.id"), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="OPEN"),
        sa.Column("guest_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("customer_id", sa.String(), sa.ForeignKey("customers.id"), nullable=True),
        sa.Column("assigned_principal_id", sa.String(), nullable=True),
        sa.Column("opened_by_principal_id", sa.String(), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_table_sessions_business_branch_status", "table_sessions", ["business_id", "branch_id", "status"])

    op.create_table(
        "table_session_tables",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("session_id", sa.String(), sa.ForeignKey("table_sessions.id"), nullable=False),
        sa.Column("table_id", sa.String(), sa.ForeignKey("restaurant_tables.id"), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("attached_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ux_table_session_tables_active_table", "table_session_tables", ["table_id"], unique=True,
        postgresql_where=sa.text("is_active = true"), sqlite_where=sa.text("is_active = 1"),
    )
    op.create_index(
        "ux_table_session_tables_active_session_table", "table_session_tables", ["session_id", "table_id"], unique=True,
        postgresql_where=sa.text("is_active = true"), sqlite_where=sa.text("is_active = 1"),
    )

    with op.batch_alter_table("orders") as batch:
        batch.create_foreign_key("fk_orders_table_session_id", "table_sessions", ["table_session_id"], ["id"])


def downgrade() -> None:
    with op.batch_alter_table("orders") as batch:
        batch.drop_constraint("fk_orders_table_session_id", type_="foreignkey")
    op.drop_index("ux_table_session_tables_active_session_table", table_name="table_session_tables")
    op.drop_index("ux_table_session_tables_active_table", table_name="table_session_tables")
    op.drop_table("table_session_tables")
    op.drop_index("ix_table_sessions_business_branch_status", table_name="table_sessions")
    op.drop_table("table_sessions")
    op.drop_index("ix_restaurant_tables_business_branch_active", table_name="restaurant_tables")
    op.drop_table("restaurant_tables")
