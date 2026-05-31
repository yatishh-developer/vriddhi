from sqlalchemy import Column
from sqlalchemy import String
from sqlalchemy import Float
from sqlalchemy import Boolean
from sqlalchemy import Integer
from sqlalchemy import ForeignKey

from database.database import Base

from core.base_model import TimestampMixin
from core.base_model import SoftDeleteMixin


class Product(
    Base,
    TimestampMixin,
    SoftDeleteMixin
):

    __tablename__ = "products"

    id = Column(
        String,
        primary_key=True,
        index=True
    )

    business_id = Column(
        String,
        ForeignKey("businesses.id"),
        nullable=False,
        index=True
    )

    name = Column(
        String,
        nullable=False
    )
    barcode = Column(
        String,
        unique=True,
        nullable=True,
        index=True
    )

    price = Column(
        Float,
        nullable=False
    )

    # GST rate in percent (0, 5, 12, 18, 28). Sent by the Flutter client.
    gst_percentage = Column(
        Float,
        nullable=False,
        default=0
    )

    # HSN code for GST compliance (4–8 digit). Sent by the Flutter client.
    hsn_code = Column(
        String,
        nullable=True,
        default=""
    )

    image_url = Column(
        String,
        nullable=True
    )

    category = Column(
        String,
        nullable=True
    )

    in_stock = Column(
        Boolean,
        default=True
    )

    is_stockless = Column(
        Boolean,
        default=False
    )

    stock_quantity = Column(
        Integer,
        default=0
    )

    description = Column(
        String,
        nullable=True
    )

    ingredients = Column(
        String,
        nullable=True
    )