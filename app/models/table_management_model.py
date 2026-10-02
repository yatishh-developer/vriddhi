import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import relationship

from core.base_model import TimestampMixin
from database.database import Base


class RestaurantTable(Base, TimestampMixin):
    __tablename__ = "restaurant_tables"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    business_id = Column(String, ForeignKey("businesses.id"), nullable=False, index=True)
    branch_id = Column(String, nullable=False, default="main", index=True)
    name = Column(String, nullable=False)
    code = Column(String, nullable=True)
    capacity = Column(Integer, nullable=False)
    section = Column(String, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    sort_order = Column(Integer, nullable=True)
    x_position = Column(Integer, nullable=True)
    y_position = Column(Integer, nullable=True)
    shape = Column(String, nullable=True)
    version = Column(Integer, nullable=False, default=1)

    session_links = relationship("TableSessionTable", back_populates="table")

    __table_args__ = (
        Index("ix_restaurant_tables_business_branch_active", "business_id", "branch_id", "is_active"),
    )


class TableSession(Base, TimestampMixin):
    __tablename__ = "table_sessions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    business_id = Column(String, ForeignKey("businesses.id"), nullable=False, index=True)
    branch_id = Column(String, nullable=False, default="main", index=True)
    primary_table_id = Column(String, ForeignKey("restaurant_tables.id"), nullable=False, index=True)
    # Immutable original table identity used to recover an interrupted open
    # even if this session is later moved to another physical table.
    opened_table_id = Column(String, ForeignKey("restaurant_tables.id"), nullable=True, index=True)
    open_idempotency_key = Column(String, nullable=True)
    open_request_hash = Column(String(64), nullable=True)
    status = Column(String, nullable=False, default="OPEN", index=True)
    guest_count = Column(Integer, nullable=False, default=1)
    customer_id = Column(String, ForeignKey("customers.id"), nullable=True, index=True)
    assigned_principal_id = Column(String, nullable=True)
    opened_by_principal_id = Column(String, nullable=False)
    opened_at = Column(DateTime(timezone=True), nullable=False)
    closed_at = Column(DateTime(timezone=True), nullable=True)
    notes = Column(Text, nullable=True)
    version = Column(Integer, nullable=False, default=1)

    tables = relationship("TableSessionTable", back_populates="session", cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="table_session")

    __table_args__ = (
        Index("ix_table_sessions_business_branch_status", "business_id", "branch_id", "status"),
        Index(
            "ux_table_sessions_open_idempotency",
            "business_id",
            "branch_id",
            "opened_table_id",
            "open_idempotency_key",
            unique=True,
            postgresql_where=open_idempotency_key.isnot(None),
            sqlite_where=open_idempotency_key.isnot(None),
        ),
    )


class TableSessionTable(Base):
    __tablename__ = "table_session_tables"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String, ForeignKey("table_sessions.id"), nullable=False, index=True)
    table_id = Column(String, ForeignKey("restaurant_tables.id"), nullable=False, index=True)
    is_primary = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    attached_at = Column(DateTime(timezone=True), nullable=False)

    session = relationship("TableSession", back_populates="tables")
    table = relationship("RestaurantTable", back_populates="session_links")

    __table_args__ = (
        Index(
            "ux_table_session_tables_active_table",
            "table_id", unique=True,
            postgresql_where=is_active.is_(True), sqlite_where=is_active.is_(True),
        ),
        Index(
            "ux_table_session_tables_active_session_table",
            "session_id", "table_id", unique=True,
            postgresql_where=is_active.is_(True), sqlite_where=is_active.is_(True),
        ),
    )
