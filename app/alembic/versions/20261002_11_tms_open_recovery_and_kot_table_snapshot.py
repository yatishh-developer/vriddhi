"""Add durable table-open recovery and historical KOT table snapshots.

Revision ID: 20261002_11
Revises: 20261002_10
"""

from alembic import op
import sqlalchemy as sa


revision = "20261002_11"
down_revision = "20261002_10"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("table_sessions", sa.Column("opened_table_id", sa.String(), nullable=True))
    op.create_foreign_key(
        "fk_table_sessions_opened_table_id",
        "table_sessions",
        "restaurant_tables",
        ["opened_table_id"],
        ["id"],
    )
    op.add_column("table_sessions", sa.Column("open_idempotency_key", sa.String(), nullable=True))
    op.add_column("table_sessions", sa.Column("open_request_hash", sa.String(length=64), nullable=True))
    op.create_index("ix_table_sessions_opened_table_id", "table_sessions", ["opened_table_id"])
    op.create_index(
        "ux_table_sessions_open_idempotency",
        "table_sessions",
        ["business_id", "branch_id", "opened_table_id", "open_idempotency_key"],
        unique=True,
        postgresql_where=sa.text("open_idempotency_key IS NOT NULL"),
        sqlite_where=sa.text("open_idempotency_key IS NOT NULL"),
    )
    op.add_column("kitchen_order_tickets", sa.Column("table_names_snapshot", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("kitchen_order_tickets", "table_names_snapshot")
    op.drop_index("ux_table_sessions_open_idempotency", table_name="table_sessions")
    op.drop_index("ix_table_sessions_opened_table_id", table_name="table_sessions")
    op.drop_column("table_sessions", "open_request_hash")
    op.drop_column("table_sessions", "open_idempotency_key")
    op.drop_constraint("fk_table_sessions_opened_table_id", "table_sessions", type_="foreignkey")
    op.drop_column("table_sessions", "opened_table_id")
