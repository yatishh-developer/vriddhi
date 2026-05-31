from sqlalchemy import Column
from sqlalchemy import String
from sqlalchemy import ForeignKey

from database.database import Base

from core.base_model import TimestampMixin


class User(Base, TimestampMixin):

    __tablename__ = "users"

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

    email = Column(
        String,
        unique=True,
        nullable=False,
        index=True
    )

    password_hash = Column(
        String,
        nullable=False
    )