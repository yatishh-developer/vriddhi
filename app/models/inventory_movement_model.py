from sqlalchemy import (
    Column,
    String,
    Integer,
    DateTime,
    ForeignKey,
    Enum,
)
from sqlalchemy.sql import func
from database.database import Base
import enum
import uuid


class InventoryMovementType(str, enum.Enum):
    SALE = "SALE"
    REFUND = "REFUND"
    MANUAL_ADD = "MANUAL_ADD"
    MANUAL_REMOVE = "MANUAL_REMOVE"
    PURCHASE = "PURCHASE"


class InventoryMovement(Base):
    __tablename__ = "inventory_movements"

    id = Column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    business_id = Column(
        String,
        ForeignKey("businesses.id"),
        nullable=False,
        index=True
    )

    branch_id = Column(
        String,
        nullable=True,
        default="main",
        index=True
    )

    product_id = Column(
        String,
        ForeignKey("products.id"),
        nullable=False,
        index=True
    )

    movement_type = Column(
        Enum(InventoryMovementType),
        nullable=False
    )

    quantity = Column(
        Integer,
        nullable=False
    )

    before_stock = Column(
        Integer,
        nullable=False
    )

    after_stock = Column(
        Integer,
        nullable=False
    )

    reference_id = Column(
        String,
        nullable=True
    )

    notes = Column(
        String,
        nullable=True
    )

    created_by = Column(
        String,
        ForeignKey("users.id"),
        nullable=False
    )

    created_by_staff_id = Column(
        String,
        nullable=True,
        index=True
    )

    source_app = Column(
        String,
        nullable=False,
        default="admin_app",
        index=True
    )

    sync_status = Column(
        String,
        nullable=False,
        default="synced",
        index=True
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )
