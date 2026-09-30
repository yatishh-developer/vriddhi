import uuid

from sqlalchemy import Column, DateTime, Index, Integer, JSON, String, Text

from core.base_model import TimestampMixin
from database.database import Base


class OutboxEvent(Base, TimestampMixin):
    """A durable, transactionally-created event waiting for realtime delivery."""

    __tablename__ = "outbox_events"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    event_id = Column(String, nullable=False, unique=True, index=True)
    event_type = Column(String, nullable=False, index=True)
    aggregate_type = Column(String, nullable=False)
    aggregate_id = Column(String, nullable=False, index=True)
    business_id = Column(String, nullable=False, index=True)
    branch_id = Column(String, nullable=True, index=True)
    payload = Column(JSON, nullable=False)
    status = Column(String, nullable=False, default="PENDING", index=True)
    attempts = Column(Integer, nullable=False, default=0)
    available_at = Column(DateTime(timezone=True), nullable=False, index=True)
    locked_at = Column(DateTime(timezone=True), nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(Text, nullable=True)

    __table_args__ = (
        Index("ix_outbox_status_available", "status", "available_at"),
        Index("ix_outbox_business_branch_type", "business_id", "branch_id", "event_type"),
    )
