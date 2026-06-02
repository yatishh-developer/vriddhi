import hashlib
import hmac
import logging
from typing import Optional

from fastapi import HTTPException

from core.config import settings
from services.subscription_service import get_plan

logger = logging.getLogger("vriddhi.payment")


def _amount_paise(plan_code: str, billing_cycle: str) -> int:
    """Resolve the charge amount (in paise) for a plan + billing cycle.

    Razorpay works in the smallest currency unit, so INR amounts are
    multiplied by 100.
    """
    plan = get_plan(plan_code)
    price = plan.yearly_price if billing_cycle == "yearly" else plan.monthly_price
    return int(round(price * 100))


class PaymentService:
    """Razorpay integration for subscription payments.

    Flow (server-verified, never trust the client):
      1. create_order()  → backend asks Razorpay for an order id, returns it
                            plus the public key id to the app.
      2. app opens the Razorpay checkout with that order id.
      3. verify_payment() → backend re-computes the HMAC signature over
                            (order_id|payment_id) using the SECRET key and
                            only activates the plan if it matches.
    """

    @staticmethod
    def _client():
        if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
            raise HTTPException(
                status_code=503,
                detail="Payments are not configured on the server.",
            )
        try:
            import razorpay  # lazy import so the app boots without the SDK
        except ImportError:
            raise HTTPException(
                status_code=503,
                detail="Payment SDK is not installed on the server.",
            )
        return razorpay.Client(
            auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
        )

    @staticmethod
    def create_order(
        business_id: str,
        plan_code: str,
        billing_cycle: str,
    ) -> dict:
        amount = _amount_paise(plan_code, billing_cycle)
        if amount <= 0:
            raise HTTPException(
                status_code=400,
                detail="This plan is free — no payment required.",
            )

        client = PaymentService._client()
        try:
            order = client.order.create(
                {
                    "amount": amount,
                    "currency": "INR",
                    "receipt": f"sub_{business_id[:18]}",
                    "notes": {
                        "business_id": business_id,
                        "plan_code": plan_code,
                        "billing_cycle": billing_cycle,
                    },
                }
            )
        except Exception as e:
            logger.exception("Razorpay order creation failed")
            raise HTTPException(
                status_code=502,
                detail=f"Could not create payment order: {e}",
            )

        return {
            "order_id": order["id"],
            "amount": amount,
            "currency": "INR",
            "key_id": settings.RAZORPAY_KEY_ID,
            "plan_code": plan_code,
            "billing_cycle": billing_cycle,
        }

    @staticmethod
    def verify_signature(
        order_id: str,
        payment_id: str,
        signature: str,
    ) -> bool:
        """Verify the Razorpay payment signature locally with HMAC-SHA256.

        signature == HMAC_SHA256(order_id + "|" + payment_id, key_secret)
        """
        if not settings.RAZORPAY_KEY_SECRET:
            return False

        message = f"{order_id}|{payment_id}".encode("utf-8")
        expected = hmac.new(
            settings.RAZORPAY_KEY_SECRET.encode("utf-8"),
            message,
            hashlib.sha256,
        ).hexdigest()

        # Constant-time comparison to avoid timing attacks.
        return hmac.compare_digest(expected, signature or "")
