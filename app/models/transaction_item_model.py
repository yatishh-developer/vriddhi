from sqlalchemy import Column, String, Integer, Float, ForeignKey
from sqlalchemy.orm import relationship

from database.database import Base
from core.base_model import TimestampMixin


class TransactionItem(Base, TimestampMixin):

    __tablename__ = "transaction_items"

    id = Column(String, primary_key=True, index=True)

    transaction_id = Column(
        String, ForeignKey("transactions.id"), nullable=False, index=True
    )

    product_id = Column(
        String, ForeignKey("products.id"), nullable=False, index=True
    )

    product_name = Column(String, nullable=False)

    quantity = Column(Integer, nullable=False)

    price = Column(Float, nullable=False)

    subtotal = Column(Float, nullable=False)

    transaction = relationship("Transaction", back_populates="items")
