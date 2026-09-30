import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database.database import Base
from core.base_model import TimestampMixin


class Order(Base, TimestampMixin):
    __tablename__ = "orders"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    business_id = Column(String, ForeignKey("businesses.id"), nullable=False, index=True)
    branch_id = Column(String, nullable=False, default="main", index=True)
    order_type = Column(String, nullable=False, default="QUICK")
    status = Column(String, nullable=False, default="ACTIVE", index=True)
    customer_id = Column(String, ForeignKey("customers.id"), nullable=True, index=True)
    table_session_id = Column(String, ForeignKey("table_sessions.id"), nullable=True, index=True)
    cancellation_reason = Column(Text, nullable=True)
    created_by = Column(String, ForeignKey("users.id"), nullable=True)
    created_by_staff_id = Column(String, nullable=True, index=True)
    source_app = Column(String, nullable=False, default="unified_api_v1", index=True)
    idempotency_key = Column(String, nullable=True, index=True)
    version = Column(Integer, nullable=False, default=1)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)

    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    transaction = relationship("Transaction", back_populates="order", uselist=False)
    table_session = relationship("TableSession", back_populates="orders")

    __table_args__ = (
        Index("ix_orders_business_branch_status_created", "business_id", "branch_id", "status", "created_at"),
        Index(
            "ux_orders_idempotency_key",
            "business_id", "branch_id", "source_app", "idempotency_key",
            unique=True,
            postgresql_where=idempotency_key.isnot(None),
            sqlite_where=idempotency_key.isnot(None),
        ),
    )


class OrderItem(Base, TimestampMixin):
    __tablename__ = "order_items"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    order_id = Column(String, ForeignKey("orders.id"), nullable=False, index=True)
    business_id = Column(String, ForeignKey("businesses.id"), nullable=False, index=True)
    branch_id = Column(String, nullable=False, index=True)
    product_id = Column(String, ForeignKey("products.id"), nullable=False, index=True)
    product_name_snapshot = Column(String, nullable=False)
    unit_price_snapshot = Column(Numeric(12, 2), nullable=False)
    tax_rate_snapshot = Column(Numeric(5, 2), nullable=False, default=0)
    quantity = Column(Integer, nullable=False)
    notes = Column(Text, nullable=True)
    status = Column(String, nullable=False, default="DRAFT", index=True)
    kot_sent_quantity = Column(Integer, nullable=False, default=0)
    cancelled_quantity = Column(Integer, nullable=False, default=0)
    billed_quantity = Column(Integer, nullable=False, default=0)
    version = Column(Integer, nullable=False, default=1)

    order = relationship("Order", back_populates="items")

    __table_args__ = (
        Index("ix_order_items_order_product_status", "order_id", "product_id", "status"),
    )


# Orders remain importable by the legacy transaction model; registering the
# table/session metadata here keeps all foreign keys resolvable in that path.
from models.table_management_model import RestaurantTable as _RestaurantTable  # noqa: E402,F401
