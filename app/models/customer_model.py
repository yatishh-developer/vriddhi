import uuid

from sqlalchemy import Column, String, Numeric, Boolean, ForeignKey, Index

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

    # Stable client mutation identity used only by the scoped v1 create flow.
    # It is tenant-scoped so an offline retry cannot create a second customer.
    client_mutation_id = Column(String, nullable=True)

    __table_args__ = (
        Index(
            "ux_customers_business_client_mutation",
            "business_id",
            "client_mutation_id",
            unique=True,
            postgresql_where=client_mutation_id.isnot(None),
            sqlite_where=client_mutation_id.isnot(None),
        ),
    )
