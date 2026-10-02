import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import relationship

from core.base_model import TimestampMixin
from database.database import Base


class KitchenKotSequence(Base):
    __tablename__ = "kitchen_kot_sequences"

    business_id = Column(String, ForeignKey("businesses.id"), primary_key=True)
    branch_id = Column(String, primary_key=True)
    current_value = Column(Integer, nullable=False, default=0)


class KitchenOrderTicket(Base, TimestampMixin):
    __tablename__ = "kitchen_order_tickets"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    business_id = Column(String, ForeignKey("businesses.id"), nullable=False, index=True)
    branch_id = Column(String, nullable=False, index=True)
    order_id = Column(String, ForeignKey("orders.id"), nullable=False, index=True)
    table_session_id = Column(String, ForeignKey("table_sessions.id"), nullable=True, index=True)
    kot_number = Column(Integer, nullable=False)
    status = Column(String, nullable=False, default="PENDING", index=True)
    created_by_principal_id = Column(String, nullable=False)
    notes = Column(Text, nullable=True)
    preparing_at = Column(DateTime(timezone=True), nullable=True)
    ready_at = Column(DateTime(timezone=True), nullable=True)
    served_at = Column(DateTime(timezone=True), nullable=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)
    version = Column(Integer, nullable=False, default=1)
    idempotency_key = Column(String, nullable=True)
    # Canonical create request hash; protects a reused key from silently
    # producing a ticket for a different kitchen intent.
    request_hash = Column(String(64), nullable=True)
    # JSON snapshot of the session's table names at ticket creation. It keeps
    # KOT history/reprints coherent when the session later moves tables.
    table_names_snapshot = Column(Text, nullable=True)

    items = relationship("KitchenOrderTicketItem", back_populates="kot", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_kots_business_branch_order_status_created", "business_id", "branch_id", "order_id", "status", "created_at"),
        Index("ux_kots_branch_number", "business_id", "branch_id", "kot_number", unique=True),
        Index(
            "ux_kots_idempotency", "business_id", "branch_id", "order_id", "idempotency_key", unique=True,
            postgresql_where=idempotency_key.isnot(None), sqlite_where=idempotency_key.isnot(None),
        ),
    )


class KitchenOrderTicketItem(Base, TimestampMixin):
    __tablename__ = "kitchen_order_ticket_items"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    kot_id = Column(String, ForeignKey("kitchen_order_tickets.id"), nullable=False, index=True)
    order_item_id = Column(String, ForeignKey("order_items.id"), nullable=False, index=True)
    product_id = Column(String, ForeignKey("products.id"), nullable=False, index=True)
    product_name_snapshot = Column(String, nullable=False)
    quantity = Column(Integer, nullable=False)
    notes_snapshot = Column(Text, nullable=True)

    kot = relationship("KitchenOrderTicket", back_populates="items")

    __table_args__ = (Index("ix_kot_items_kot_order_item", "kot_id", "order_item_id"),)


class KitchenKotCancellation(Base, TimestampMixin):
    __tablename__ = "kitchen_kot_cancellations"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    business_id = Column(String, ForeignKey("businesses.id"), nullable=False, index=True)
    branch_id = Column(String, nullable=False, index=True)
    order_id = Column(String, ForeignKey("orders.id"), nullable=False, index=True)
    order_item_id = Column(String, ForeignKey("order_items.id"), nullable=False, index=True)
    kot_id = Column(String, ForeignKey("kitchen_order_tickets.id"), nullable=True, index=True)
    quantity = Column(Integer, nullable=False)
    reason = Column(Text, nullable=False)
    created_by_principal_id = Column(String, nullable=False)
