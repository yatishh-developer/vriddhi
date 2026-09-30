import uuid

from sqlalchemy import Column, String, Numeric, Boolean, ForeignKey

from database.database import Base
from core.base_model import TimestampMixin, SoftDeleteMixin


class Customer(Base, TimestampMixin, SoftDeleteMixin):

    __tablename__ = "customers"

    id = Column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    business_id = Column(
        String, ForeignKey("businesses.id"), nullable=False
    )

    name = Column(String, nullable=False)

    phone = Column(String, nullable=False, default="")

    email = Column(String, nullable=True)

    address = Column(String, nullable=True, default="")

    # ── Extended fields for Flutter's CustomerProfile ─────────────────────
    balance_remaining = Column(Numeric(12, 2), default=0)

    loyal_customer = Column(Boolean, default=False)

    preset_discount = Column(Numeric(12, 2), default=0)
