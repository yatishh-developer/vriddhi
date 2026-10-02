"""Persist v1 order add-items idempotency records.

Revision ID: 20261002_09
Revises: 20261002_08
"""

from alembic import op
import sqlalchemy as sa


revision = "20261002_09"
down_revision = "20261002_08"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "order_item_mutations",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("business_id", sa.String(), nullable=False),
        sa.Column("branch_id", sa.String(), nullable=False),
        sa.Column("order_id", sa.String(), nullable=False),
        sa.Column("operation", sa.String(), nullable=False),
        sa.Column("idempotency_key", sa.String(), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("result_order_version", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"]),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_order_item_mutations_business_id", "order_item_mutations", ["business_id"])
    op.create_index("ix_order_item_mutations_branch_id", "order_item_mutations", ["branch_id"])
    op.create_index("ix_order_item_mutations_order_id", "order_item_mutations", ["order_id"])
    op.create_index(
        "ux_order_item_mutations_identity",
        "order_item_mutations",
        ["business_id", "branch_id", "order_id", "operation", "idempotency_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ux_order_item_mutations_identity", table_name="order_item_mutations")
    op.drop_index("ix_order_item_mutations_order_id", table_name="order_item_mutations")
    op.drop_index("ix_order_item_mutations_branch_id", table_name="order_item_mutations")
    op.drop_index("ix_order_item_mutations_business_id", table_name="order_item_mutations")
    op.drop_table("order_item_mutations")
