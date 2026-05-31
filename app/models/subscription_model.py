import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import Column, String, DateTime, Boolean, Float, Integer, ForeignKey

from database.database import Base
from core.base_model import TimestampMixin


def _utcnow() -> datetime:
    """Timezone-aware UTC now, so values stored in DateTime(timezone=True)
    columns are consistent and never trigger naive/aware comparison errors."""
    return datetime.now(timezone.utc)


# ── Plan codes — keep in sync with SubscriptionService.PLAN_DEFAULTS ───────
PLAN_FREE = "free"
PLAN_STARTER = "starter"
PLAN_BUSINESS = "business"
PLAN_PREMIUM = "premium"


class Subscription(Base, TimestampMixin):
    """A subscription belongs to a business and tracks plan/period state.

    The subscription is the source of truth for the user's plan, when it
    expires, and the AI usage credits remaining for the current period.
    """

    __tablename__ = "subscriptions"

    id = Column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    business_id = Column(
        String,
        ForeignKey("businesses.id"),
        nullable=False,
        unique=True,
        index=True,
    )

    plan_code = Column(String, nullable=False, default=PLAN_FREE)
    billing_cycle = Column(String, nullable=False, default="monthly")
    status = Column(String, nullable=False, default="active")
    auto_renew = Column(Boolean, default=False, nullable=False)

    # ── Period window ────────────────────────────────────────────────────
    started_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    current_period_start = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    current_period_end = Column(DateTime(timezone=True), nullable=False)
    trial_ends_at = Column(DateTime(timezone=True), nullable=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)

    # ── Counters reset per billing period ────────────────────────────────
    invoices_used_in_period = Column(Integer, default=0, nullable=False)
    ai_credits_used_in_period = Column(Integer, default=0, nullable=False)

    # ── Pricing snapshot (in INR) for audit / display ────────────────────
    price_amount = Column(Float, default=0.0, nullable=False)
    currency = Column(String, default="INR", nullable=False)

    # ── Last reminder / notification book-keeping (so reminders aren't
    # spammed twice for the same threshold) ──────────────────────────────
    last_expiry_reminder_at = Column(DateTime(timezone=True), nullable=True)
