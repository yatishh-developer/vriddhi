"""Persist KOT create-request hashes for safe idempotency recovery.

Revision ID: 20261002_10
Revises: 20261002_09
"""

from alembic import op
import sqlalchemy as sa


revision = "20261002_10"
down_revision = "20261002_09"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "kitchen_order_tickets",
        sa.Column("request_hash", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("kitchen_order_tickets", "request_hash")
