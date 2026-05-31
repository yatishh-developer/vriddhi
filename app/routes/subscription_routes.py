from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from auth.dependencies import get_current_user
from database.dependencies import get_db
from schemas.subscription_schema import (
    PlanFeatures,
    SubscriptionResponse,
    SubscribeRequest,
    UsageRecordRequest,
)
from services.subscription_service import SubscriptionService, get_plan, list_plans


router = APIRouter(prefix="/subscriptions", tags=["Subscriptions"])


def _to_response(sub) -> SubscriptionResponse:
    """Hydrate a Subscription model into the SubscriptionResponse schema
    (including the computed days_remaining / is_expired / nested plan).
    """
    plan = get_plan(sub.plan_code)
    now = datetime.utcnow()
    end = sub.current_period_end
    if end.tzinfo is not None:
        end = end.replace(tzinfo=None)
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
