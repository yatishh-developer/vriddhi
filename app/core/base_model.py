from sqlalchemy import Column, DateTime, Boolean
from sqlalchemy.sql import func


class TimestampMixin:
    """Mixin that adds created_at and updated_at timestamp columns."""

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class SoftDeleteMixin:
    """Mixin that adds a soft-delete flag."""

    is_deleted = Column(
        Boolean,
        default=False,
        nullable=False,
    )
