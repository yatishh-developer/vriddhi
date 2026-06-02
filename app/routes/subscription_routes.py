from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from auth.dependencies import get_current_user
from database.dependencies import get_db
from schemas.subscription_schema import (
    PlanFeatures,
    SubscriptionResponse,
    SubscribeRequest,
    UsageRecordRequest,
    CreateOrderRequest,
    CreateOrderResponse,
    VerifyPaymentRequest,
)
from services.subscription_service import SubscriptionService, get_plan, list_plans
from services.payment_service import PaymentService


router = APIRouter(prefix="/subscriptions", tags=["Subscriptions"])


def _to_response(sub) -> SubscriptionResponse:
    """Hydrate a Subscription model into the SubscriptionResponse schema
    (including the computed days_remaining / is_expired / nested plan).
    """
    plan = get_plan(sub.plan_code)
    now = datetime.now(timezone.utc)
    end = sub.current_period_end
    # Normalise to timezone-aware UTC so the subtraction never raises a
    # naive/aware TypeError regardless of how the value came back from the DB.
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    delta = end - now
    days_remaining = max(delta.days, 0) if delta.total_seconds() > 0 else 0
    is_expired = end < now or sub.status == "expired"
    is_active = sub.status == "active" and not is_expired

    return SubscriptionResponse(
        id=sub.id,
        business_id=sub.business_id,
        plan_code=sub.plan_code,
        billing_cycle=sub.billing_cycle,
        status=sub.status,
        auto_renew=sub.auto_renew,
        started_at=sub.started_at,
        current_period_start=sub.current_period_start,
        current_period_end=sub.current_period_end,
        trial_ends_at=sub.trial_ends_at,
        cancelled_at=sub.cancelled_at,
        invoices_used_in_period=sub.invoices_used_in_period,
        ai_credits_used_in_period=sub.ai_credits_used_in_period,
        price_amount=sub.price_amount,
        currency=sub.currency,
        days_remaining=days_remaining,
        is_active=is_active,
        is_expired=is_expired,
        plan=plan,
    )


@router.get("/plans", response_model=List[PlanFeatures])
def get_plans():
    """Public list of available plans — used by the Flutter pricing screen."""
    return list_plans()


@router.get("/me", response_model=SubscriptionResponse)
def get_my_subscription(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    sub = SubscriptionService.get_subscription(db, current_user.business_id)
    return _to_response(sub)


@router.post("/subscribe", response_model=SubscriptionResponse)
def subscribe(
    payload: SubscribeRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    sub = SubscriptionService.subscribe(
        db,
        current_user.business_id,
        payload.plan_code,
        payload.billing_cycle,
        payload.auto_renew,
    )
    return _to_response(sub)


@router.post("/cancel", response_model=SubscriptionResponse)
def cancel(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    sub = SubscriptionService.cancel(db, current_user.business_id)
    return _to_response(sub)


@router.post("/usage", response_model=SubscriptionResponse)
def record_usage(
    payload: UsageRecordRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    sub = SubscriptionService.record_usage(
        db,
        current_user.business_id,
        payload.invoices,
        payload.ai_credits,
    )
    return _to_response(sub)


# ── Razorpay payment flow ─────────────────────────────────────────────────
# 1. The app asks for an order (server talks to Razorpay, returns order id).
# 2. The app opens Razorpay checkout with that order id.
# 3. The app sends the checkout result back; the server verifies the HMAC
#    signature and only THEN activates the plan. The plan is never activated
#    on the client's word alone.


@router.post("/create-order", response_model=CreateOrderResponse)
def create_payment_order(
    payload: CreateOrderRequest,
    current_user=Depends(get_current_user),
):
    """Create a Razorpay order for a paid plan and return the checkout params."""
    # Reject free plans early — they don't need a payment.
    plan = get_plan(payload.plan_code)
    price = plan.yearly_price if payload.billing_cycle == "yearly" else plan.monthly_price
    if price <= 0:
        raise HTTPException(
            status_code=400,
            detail="This plan is free — use /subscribe instead.",
        )

    return PaymentService.create_order(
        business_id=current_user.business_id,
        plan_code=payload.plan_code,
        billing_cycle=payload.billing_cycle,
    )


@router.post("/verify-payment", response_model=SubscriptionResponse)
def verify_payment(
    payload: VerifyPaymentRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Verify a Razorpay payment and activate the subscription on success."""
    ok = PaymentService.verify_signature(
        order_id=payload.razorpay_order_id,
        payment_id=payload.razorpay_payment_id,
        signature=payload.razorpay_signature,
    )
    if not ok:
        raise HTTPException(
            status_code=400,
            detail="Payment verification failed. Plan was not activated.",
        )

    # Signature valid → activate the plan for this business.
    sub = SubscriptionService.subscribe(
        db,
        current_user.business_id,
        payload.plan_code,
        payload.billing_cycle,
        payload.auto_renew,
    )
    return _to_response(sub)
