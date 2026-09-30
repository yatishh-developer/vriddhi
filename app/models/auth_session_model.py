import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String

from core.base_model import TimestampMixin
from database.database import Base


class AuthSession(Base, TimestampMixin):
    """Server-side state for session-aware JWTs.

    Legacy JWTs have no session id and remain readable during the migration.
    New tokens reference this row, allowing a logout/revocation to take effect
    before their normal JWT expiration.
    """

    __tablename__ = "auth_sessions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    actor_type = Column(String, nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    staff_id = Column(String, ForeignKey("staff_profiles.id"), nullable=True, index=True)
    business_id = Column(String, ForeignKey("businesses.id"), nullable=False, index=True)
    device_id = Column(String, nullable=True, index=True)
    refresh_token_hash = Column(String, nullable=True, index=True)
    status = Column(String, nullable=False, default="ACTIVE", index=True)
    last_seen_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
