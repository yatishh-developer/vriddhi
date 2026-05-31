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