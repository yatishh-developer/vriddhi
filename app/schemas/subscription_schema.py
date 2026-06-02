from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel


class PlanFeatures(BaseModel):
    """Marketing-style summary of what a plan offers."""

    code: str
    name: str
    tagline: str
    monthly_price: float
    yearly_price: float
    invoice_limit: int  # -1 means unlimited
    ai_credit_limit: int  # -1 means unlimited (premium uses fair-use)
    staff_accounts: int
    cloud_sync: bool
    voice_billing: bool
    whatsapp_share: bool
    advanced_analytics: bool
    multi_store: bool
    priority_support: bool
    highlights: List[str]


class SubscriptionResponse(BaseModel):
    id: str
    business_id: str
    plan_code: str
    billing_cycle: str
    status: str
    auto_renew: bool

    started_at: datetime
    current_period_start: datetime
    current_period_end: datetime
    trial_ends_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None

    invoices_used_in_period: int
    ai_credits_used_in_period: int

    price_amount: float
    currency: str

    # ── Computed fields surfaced for the UI ──────────────────────────────
    days_remaining: int
    is_active: bool
    is_expired: bool
    plan: PlanFeatures

    class Config:
        from_attributes = True


class SubscribeRequest(BaseModel):
    plan_code: str
    billing_cycle: str = "monthly"  # "monthly" | "yearly"
    auto_renew: bool = False


class UsageRecordRequest(BaseModel):
    """Used by the client to report AI credit consumption / invoice count."""

    invoices: int = 0
    ai_credits: int = 0


class CreateOrderRequest(BaseModel):
    """Ask the backend to create a Razorpay order for a plan purchase."""

    plan_code: str
    billing_cycle: str = "monthly"  # "monthly" | "yearly"


class CreateOrderResponse(BaseModel):
    order_id: str
    amount: int  # in paise
    currency: str
    key_id: str
    plan_code: str
    billing_cycle: str


class VerifyPaymentRequest(BaseModel):
    """Razorpay checkout result, sent back for server-side verification."""

    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str
    plan_code: str
    billing_cycle: str = "monthly"
    auto_renew: bool = False
