"""Persist checkout intent hashes for deterministic idempotency recovery.

Revision ID: 20261002_08
Revises: 20261002_07
"""

from alembic import op
import sqlalchemy as sa


revision = "20261002_08"
down_revision = "20261002_07"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "transactions",
        sa.Column("checkout_request_hash", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("transactions", "checkout_request_hash")
