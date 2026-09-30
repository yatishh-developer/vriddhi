"""Bring the migrated PostgreSQL schema into parity with registered metadata.

This is a schema-only follow-up to Phase 6.  It fixes indexes that historical
handwritten migrations omitted, corrects the GST precision, and replaces the
outbox event unique constraint with the model's unique index.  No domain data
is changed or removed.
"""

from alembic import op
import sqlalchemy as sa


revision = "20261001_06b"
down_revision = "20261001_06"
branch_labels = None
depends_on = None


def _indexes(table: str, definitions: tuple[tuple[str, tuple[str, ...], bool], ...]) -> None:
    for name, columns, unique in definitions:
        op.create_index(name, table, list(columns), unique=unique)


def upgrade() -> None:
    op.alter_column("products", "gst_percentage", existing_type=sa.Numeric(12, 2), type_=sa.Numeric(5, 2), existing_nullable=False)
    _indexes("businesses", (("ix_businesses_id", ("id",), False),))
    _indexes("users", (("ix_users_id", ("id",), False),))
    _indexes("products", (("ix_products_id", ("id",), False),))
    _indexes("transaction_items", (("ix_transaction_items_id", ("id",), False),))
    _indexes("transactions", (("ix_transactions_id", ("id",), False),))
    _indexes("staff_invites", (("ix_staff_invites_id", ("id",), False),))
    _indexes("staff_profiles", (("ix_staff_profiles_id", ("id",), False),))
    _indexes("staff_kots", (("ix_staff_kots_id", ("id",), False),))
    _indexes("staff_held_bills", (("ix_staff_held_bills_id", ("id",), False),))
    _indexes("staff_payments", (("ix_staff_payments_id", ("id",), False),))
    _indexes("staff_process_locks", (("ix_staff_process_locks_process_id", ("process_id",), False),))
    _indexes("staff_realtime_events", (("ix_staff_realtime_events_event_id", ("event_id",), False),))
    op.drop_index("ux_transactions_order_id", table_name="transactions")
    op.create_index("ix_transactions_order_id", "transactions", ["order_id"], unique=True)

    _indexes("orders", (
        ("ix_orders_business_id", ("business_id",), False), ("ix_orders_branch_id", ("branch_id",), False),
        ("ix_orders_status", ("status",), False), ("ix_orders_customer_id", ("customer_id",), False),
        ("ix_orders_table_session_id", ("table_session_id",), False), ("ix_orders_created_by_staff_id", ("created_by_staff_id",), False),
        ("ix_orders_source_app", ("source_app",), False), ("ix_orders_idempotency_key", ("idempotency_key",), False),
    ))
    _indexes("order_items", (
        ("ix_order_items_order_id", ("order_id",), False), ("ix_order_items_business_id", ("business_id",), False),
        ("ix_order_items_branch_id", ("branch_id",), False), ("ix_order_items_product_id", ("product_id",), False),
        ("ix_order_items_status", ("status",), False),
    ))
    _indexes("restaurant_tables", (("ix_restaurant_tables_business_id", ("business_id",), False), ("ix_restaurant_tables_branch_id", ("branch_id",), False)))
    _indexes("table_sessions", (
        ("ix_table_sessions_business_id", ("business_id",), False), ("ix_table_sessions_branch_id", ("branch_id",), False),
        ("ix_table_sessions_primary_table_id", ("primary_table_id",), False), ("ix_table_sessions_status", ("status",), False),
        ("ix_table_sessions_customer_id", ("customer_id",), False),
    ))
    _indexes("table_session_tables", (
        ("ix_table_session_tables_session_id", ("session_id",), False), ("ix_table_session_tables_table_id", ("table_id",), False),
        ("ix_table_session_tables_is_active", ("is_active",), False),
    ))
    _indexes("kitchen_order_tickets", (
        ("ix_kitchen_order_tickets_business_id", ("business_id",), False), ("ix_kitchen_order_tickets_branch_id", ("branch_id",), False),
        ("ix_kitchen_order_tickets_order_id", ("order_id",), False), ("ix_kitchen_order_tickets_table_session_id", ("table_session_id",), False),
        ("ix_kitchen_order_tickets_status", ("status",), False),
    ))
    _indexes("kitchen_order_ticket_items", (
        ("ix_kitchen_order_ticket_items_kot_id", ("kot_id",), False), ("ix_kitchen_order_ticket_items_order_item_id", ("order_item_id",), False),
        ("ix_kitchen_order_ticket_items_product_id", ("product_id",), False),
    ))
    _indexes("kitchen_kot_cancellations", (
        ("ix_kitchen_kot_cancellations_business_id", ("business_id",), False), ("ix_kitchen_kot_cancellations_branch_id", ("branch_id",), False),
        ("ix_kitchen_kot_cancellations_order_id", ("order_id",), False), ("ix_kitchen_kot_cancellations_order_item_id", ("order_item_id",), False),
        ("ix_kitchen_kot_cancellations_kot_id", ("kot_id",), False),
    ))

    op.drop_constraint("uq_outbox_events_event_id", "outbox_events", type_="unique")
    _indexes("outbox_events", (
        ("ix_outbox_events_aggregate_id", ("aggregate_id",), False), ("ix_outbox_events_event_id", ("event_id",), True),
    ))


def downgrade() -> None:
    op.drop_index("ix_outbox_events_event_id", table_name="outbox_events")
    op.drop_index("ix_outbox_events_aggregate_id", table_name="outbox_events")
    op.create_unique_constraint("uq_outbox_events_event_id", "outbox_events", ["event_id"])
    for table, names in (
        ("kitchen_kot_cancellations", ("ix_kitchen_kot_cancellations_business_id", "ix_kitchen_kot_cancellations_branch_id", "ix_kitchen_kot_cancellations_order_id", "ix_kitchen_kot_cancellations_order_item_id", "ix_kitchen_kot_cancellations_kot_id")),
        ("kitchen_order_ticket_items", ("ix_kitchen_order_ticket_items_kot_id", "ix_kitchen_order_ticket_items_order_item_id", "ix_kitchen_order_ticket_items_product_id")),
        ("kitchen_order_tickets", ("ix_kitchen_order_tickets_business_id", "ix_kitchen_order_tickets_branch_id", "ix_kitchen_order_tickets_order_id", "ix_kitchen_order_tickets_table_session_id", "ix_kitchen_order_tickets_status")),
        ("table_session_tables", ("ix_table_session_tables_session_id", "ix_table_session_tables_table_id", "ix_table_session_tables_is_active")),
        ("table_sessions", ("ix_table_sessions_business_id", "ix_table_sessions_branch_id", "ix_table_sessions_primary_table_id", "ix_table_sessions_status", "ix_table_sessions_customer_id")),
        ("restaurant_tables", ("ix_restaurant_tables_business_id", "ix_restaurant_tables_branch_id")),
        ("order_items", ("ix_order_items_order_id", "ix_order_items_business_id", "ix_order_items_branch_id", "ix_order_items_product_id", "ix_order_items_status")),
        ("orders", ("ix_orders_business_id", "ix_orders_branch_id", "ix_orders_status", "ix_orders_customer_id", "ix_orders_table_session_id", "ix_orders_created_by_staff_id", "ix_orders_source_app", "ix_orders_idempotency_key")),
    ):
        for name in names:
            op.drop_index(name, table_name=table)
    op.drop_index("ix_transactions_order_id", table_name="transactions")
    op.create_index("ux_transactions_order_id", "transactions", ["order_id"], unique=True)
    for table, name in (
        ("staff_realtime_events", "ix_staff_realtime_events_event_id"), ("staff_process_locks", "ix_staff_process_locks_process_id"),
        ("staff_payments", "ix_staff_payments_id"), ("staff_held_bills", "ix_staff_held_bills_id"), ("staff_kots", "ix_staff_kots_id"),
        ("staff_profiles", "ix_staff_profiles_id"), ("staff_invites", "ix_staff_invites_id"), ("transactions", "ix_transactions_id"),
        ("transaction_items", "ix_transaction_items_id"), ("products", "ix_products_id"), ("users", "ix_users_id"), ("businesses", "ix_businesses_id"),
    ):
        op.drop_index(name, table_name=table)
    op.alter_column("products", "gst_percentage", existing_type=sa.Numeric(5, 2), type_=sa.Numeric(12, 2), existing_nullable=False)
