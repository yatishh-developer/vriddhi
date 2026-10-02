"""Add scoped v1 customer-create idempotency.

Revision ID: 20261002_07
Revises: 20261001_06b
"""

from alembic import op
import sqlalchemy as sa


revision = "20261002_07"
down_revision = "20261001_06b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("customers", sa.Column("client_mutation_id", sa.String(), nullable=True))
    op.create_index(
        "ux_customers_business_client_mutation",
        "customers",
        ["business_id", "client_mutation_id"],
        unique=True,
        postgresql_where=sa.text("client_mutation_id IS NOT NULL"),
        sqlite_where=sa.text("client_mutation_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ux_customers_business_client_mutation", table_name="customers")
    op.drop_column("customers", "client_mutation_id")
