from sqlalchemy import Column, String, Float, ForeignKey, Boolean, Text
from sqlalchemy.orm import relationship

from database.database import Base
from core.base_model import TimestampMixin


class Transaction(Base, TimestampMixin):

    __tablename__ = "transactions"

    id = Column(String, primary_key=True, index=True)

    business_id = Column(
        String, ForeignKey("businesses.id"), nullable=False, index=True
    )

    branch_id = Column(String, nullable=True, default="main", index=True)

    customer_id = Column(
        String, ForeignKey("customers.id"), nullable=True
    )

    # ── Fields to match Flutter's local model ──────────────────────────────
    flow = Column(String, default="Quick")           # "Quick" | "Credit" | "Return"
    bill_no = Column(String, nullable=True)
    bill_date = Column(String, nullable=True)        # ISO string
    bill_date_text = Column(String, nullable=True)
    due_date = Column(String, nullable=True)

    customer_name = Column(String, nullable=True, default="")
    customer_phone = Column(String, nullable=True, default="")
    customer_address = Column(String, nullable=True, default="")

    payment_method = Column(String, nullable=False)  # kept for compat
    payment_option = Column(String, nullable=True, default="Cash")

    cash_amount = Column(Float, default=0.0)
    upi_amount = Column(Float, default=0.0)
    card_amount = Column(Float, default=0.0)
    other_paid_amount = Column(Float, default=0.0)
    credit_amount = Column(Float, default=0.0)
    discount = Column(Float, default=0.0)

    is_parcel = Column(Boolean, default=False)
    is_hold = Column(Boolean, default=False)

    # JSON snapshot of items
    items_json = Column(Text, nullable=True, default="[]")

    # Totals
    total_amount = Column(Float, nullable=False, default=0.0)
    subtotal = Column(Float, default=0.0)
    total_cgst = Column(Float, default=0.0)
    total_sgst = Column(Float, default=0.0)
    total_igst = Column(Float, default=0.0)
    total_tax = Column(Float, default=0.0)
    old_balance = Column(Float, default=0.0)
    is_intra_state = Column(Boolean, default=True)

    status = Column(String, default="completed")

    created_by = Column(String, ForeignKey("users.id"), nullable=True)
    created_by_staff_id = Column(String, nullable=True, index=True)
    source_app = Column(String, nullable=False, default="admin_app", index=True)
    sync_status = Column(String, nullable=False, default="synced", index=True)
    idempotency_key = Column(String, nullable=True, index=True)
    device_id = Column(String, nullable=True)

    items = relationship("TransactionItem", back_populates="transaction", cascade="all, delete-orphan")
