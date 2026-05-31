from datetime import datetime, timedelta
from typing import Dict, List

from fastapi import HTTPException

from models.subscription_model import (
    Subscription,
    PLAN_FREE,
    PLAN_STARTER,
    PLAN_BUSINESS,
    PLAN_PREMIUM,
)
from schemas.subscription_schema import PlanFeatures


# ── Plan catalogue ──────────────────────────────────────────────────────
# Mirrors the strategy doc shipped with the project so backend and Flutter
# stay in lockstep. Edit one place — update both.
PLAN_DEFAULTS: Dict[str, PlanFeatures] = {
    PLAN_FREE: PlanFeatures(
        code=PLAN_FREE,
        name="Free",
        tagline="Try Vriddhi risk-free",
        monthly_price=0.0,
        yearly_price=0.0,
        invoice_limit=50,
        ai_credit_limit=0,
        staff_accounts=1,
        cloud_sync=False,
        voice_billing=False,
        whatsapp_share=False,
        advanced_analytics=False,
        multi_store=False,
        priority_support=False,
        highlights=[
            "50 invoices / month",
            "1 business",
            "Basic inventory",
            "Local storage only",
            "Vriddhi branding",
        ],
    ),
    PLAN_STARTER: PlanFeatures(
        code=PLAN_STARTER,
        name="Starter",
        tagline="For small shops getting serious",
        monthly_price=149.0,
        yearly_price=1499.0,
        invoice_limit=-1,
        ai_credit_limit=100,
        staff_accounts=1,
        cloud_sync=True,
        voice_billing=False,
        whatsapp_share=False,
        advanced_analytics=False,
        multi_store=False,
        priority_support=False,
        highlights=[
            "Unlimited invoices",
            "Cloud sync",
            "Barcode scanning",
            "GST invoices",
            "100 AI actions / month",
            "Daily sales reports",
        ],
    ),
    PLAN_BUSINESS: PlanFeatures(
        code=PLAN_BUSINESS,
        name="Business",
        tagline="The plan most growing shops pick",
        monthly_price=499.0,
        yearly_price=4999.0,
        invoice_limit=-1,
        ai_credit_limit=1000,
        staff_accounts=3,
        cloud_sync=True,
        voice_billing=True,
        whatsapp_share=True,
        advanced_analytics=True,
        multi_store=False,
        priority_support=False,
        highlights=[
            "3 staff accounts",
            "Voice billing",
            "WhatsApp invoice sharing",
            "Advanced analytics",
            "Smart inventory alerts",
            "1000 AI actions / month",
        ],
    ),
    PLAN_PREMIUM: PlanFeatures(
        code=PLAN_PREMIUM,
        name="Premium",
        tagline="For wholesalers and multi-store",
        monthly_price=1499.0,
        yearly_price=14999.0,
        invoice_limit=-1,
        ai_credit_limit=-1,  # fair-use
        staff_accounts=-1,
        cloud_sync=True,
        voice_billing=True,
        whatsapp_share=True,
        advanced_analytics=True,
        multi_store=True,
        priority_support=True,
        highlights=[
            "Unlimited staff",
            "Multi-store",
            "AI forecasting",
            "Custom branding",
            "API access",
            "Priority support",
        ],
    ),
}


def get_plan(plan_code: str) -> PlanFeatures:
    plan = PLAN_DEFAULTS.get(plan_code)
    if not plan:
        raise HTTPException(status_code=400, detail=f"Unknown plan: {plan_code}")
    return plan


def list_plans() -> List[PlanFeatures]:
    return list(PLAN_DEFAULTS.values())


def _period_end(start: datetime, billing_cycle: str) -> datetime:
    if billing_cycle == "yearly":
        return start + timedelta(days=365)
    return start + timedelta(days=30)


class SubscriptionService:

    @staticmethod
    def _ensure_subscription(db, business_id: str) -> Subscription:
        """Return the subscription for a business, creating a Free one if
        none exists yet. Idempotent — safe to call from any read endpoint.
        """
        sub = db.query(Subscription).filter(
            Subscription.business_id == business_id
        ).first()
        if sub:
            return sub

        now = datetime.utcnow()
        plan = PLAN_DEFAULTS[PLAN_FREE]
        sub = Subscription(
            business_id=business_id,
            plan_code=PLAN_FREE,
            billing_cycle="monthly",
            status="active",
            auto_renew=False,
            started_at=now,
            current_period_start=now,
            current_period_end=_period_end(now, "monthly"),
            price_amount=plan.monthly_price,
        )
        db.add(sub)
        db.commit()
        db.refresh(sub)
        return sub

    @staticmethod
    def get_subscription(db, business_id: str) -> Subscription:
        sub = SubscriptionService._ensure_subscription(db, business_id)
        # Roll forward expired periods so usage counters reset.
        SubscriptionService._roll_period_if_needed(db, sub)
        return sub

    @staticmethod
    def _roll_period_if_needed(db, sub: Subscription) -> Subscription:
        now = datetime.utcnow()
        if sub.current_period_end >= now:
            return sub

        if sub.auto_renew and sub.status == "active":
            # Renew the same plan for another period.
            sub.current_period_start = sub.current_period_end
            sub.current_period_end = _period_end(
                sub.current_period_start, sub.billing_cycle
            )
            sub.invoices_used_in_period = 0
            sub.ai_credits_used_in_period = 0
            db.commit()
            db.refresh(sub)
            return sub

        # Otherwise downgrade to Free.
        plan = PLAN_DEFAULTS[PLAN_FREE]
        sub.plan_code = PLAN_FREE
        sub.billing_cycle = "monthly"
        sub.status = "expired"
        sub.auto_renew = False
        sub.current_period_start = now
        sub.current_period_end = _period_end(now, "monthly")
        sub.invoices_used_in_period = 0
        sub.ai_credits_used_in_period = 0
        sub.price_amount = plan.monthly_price
        db.commit()
        db.refresh(sub)
        return sub

    @staticmethod
    def subscribe(db, business_id: str, plan_code: str, billing_cycle: str, auto_renew: bool):
        plan = get_plan(plan_code)
        sub = SubscriptionService._ensure_subscription(db, business_id)

        now = datetime.utcnow()
        sub.plan_code = plan.code
        sub.billing_cycle = billing_cycle
        sub.status = "active"
        sub.auto_renew = auto_renew
        sub.started_at = now if sub.plan_code != plan.code else sub.started_at
        sub.current_period_start = now
        sub.current_period_end = _period_end(now, billing_cycle)
        sub.invoices_used_in_period = 0
        sub.ai_credits_used_in_period = 0
        sub.cancelled_at = None
        sub.price_amount = (
            plan.yearly_price if billing_cycle == "yearly" else plan.monthly_price
        )

        db.commit()
        db.refresh(sub)
        return sub

    @staticmethod
    def cancel(db, business_id: str):
        sub = SubscriptionService._ensure_subscription(db, business_id)
        sub.auto_renew = False
        sub.cancelled_at = datetime.utcnow()
        sub.status = "cancelled"
        db.commit()
        db.refresh(sub)
        return sub

    @staticmethod
    def record_usage(db, business_id: str, invoices: int, ai_credits: int):
        sub = SubscriptionService.get_subscription(db, business_id)

        plan = get_plan(sub.plan_code)
        new_invoices = sub.invoices_used_in_period + max(invoices, 0)
        new_credits = sub.ai_credits_used_in_period + max(ai_credits, 0)

        if plan.invoice_limit != -1 and new_invoices > plan.invoice_limit:
            raise HTTPException(
                status_code=402,
                detail="Monthly invoice limit reached for current plan",
            )

        if plan.ai_credit_limit != -1 and new_credits > plan.ai_credit_limit:
            raise HTTPException(
                status_code=402,
                detail="AI credit limit reached for current plan",
            )

        sub.invoices_used_in_period = new_invoices
        sub.ai_credits_used_in_period = new_credits
        db.commit()
        db.refresh(sub)
        return sub
