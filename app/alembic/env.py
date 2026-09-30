import sys
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# Ensure the app directory is on the path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.database import Base

from models.product_model import Product
from models.user_model import User
from models.business_model import Business
from models.customer_model import Customer
from models.transaction_model import Transaction
from models.transaction_item_model import TransactionItem
from models.inventory_movement_model import InventoryMovement
from models.subscription_model import Subscription
from models.staff_billing_model import StaffInvite
from models.staff_billing_model import StaffProfile
from models.staff_billing_model import StaffKot
from models.staff_billing_model import StaffHeldBill
from models.staff_billing_model import StaffPayment
from models.staff_billing_model import StaffProcessLock
from models.staff_billing_model import StaffRealtimeEvent
from models.auth_session_model import AuthSession
from models.order_model import Order
from models.order_model import OrderItem
from models.table_management_model import RestaurantTable
from models.table_management_model import TableSession
from models.table_management_model import TableSessionTable
from models.kot_model import KitchenKotSequence
from models.kot_model import KitchenOrderTicket
from models.kot_model import KitchenOrderTicketItem
from models.kot_model import KitchenKotCancellation
from models.outbox_model import OutboxEvent
from core.config import settings


target_metadata = Base.metadata


config = context.config
config.set_main_option("sqlalchemy.url", settings.get_database_url())


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
