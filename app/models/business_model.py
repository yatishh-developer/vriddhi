from sqlalchemy import Column, String, Boolean

from database.database import Base
from core.base_model import TimestampMixin


class Business(Base, TimestampMixin):

    __tablename__ = "businesses"

    id = Column(String, primary_key=True, index=True)

    name = Column(String, nullable=False)

    business_type = Column(String, nullable=False)

    gst_number = Column(String, nullable=True)

    # ── Extended profile fields ───────────────────────────────────────────
    owner_name = Column(String, nullable=True, default="")

    phone = Column(String, nullable=True, default="")

    email = Column(String, nullable=True, default="")

    address = Column(String, nullable=True, default="")

    city = Column(String, nullable=True, default="")

    state = Column(String, nullable=True, default="")

    pincode = Column(String, nullable=True, default="")

    upi_id = Column(String, nullable=True, default="")

    is_intra_state = Column(Boolean, default=True)

    default_discount = Column(String, nullable=True, default="0")
