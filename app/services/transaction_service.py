import json
from decimal import Decimal

from auth.principal import ActorType, PrincipalContext
from schemas.checkout_schema import CheckoutItemInput, CheckoutPaymentInput, CheckoutRequest
from services.checkout_service import CheckoutService


class TransactionService:
    """Compatibility adapter for the legacy admin transaction route."""

    @staticmethod
    def create_transaction(db, current_user, payload, principal: PrincipalContext | None = None):
        principal = principal or PrincipalContext(
            principal_id=current_user.id,
            actor_type=ActorType.OWNER,
            business_id=current_user.business_id,
            user_id=current_user.id,
            role="owner",
            permissions=frozenset({"*"}),
            capabilities=frozenset({"*"}),
        )
        request = TransactionService._legacy_request(payload)
        return CheckoutService.checkout(
            db,
            principal=principal,
            request=request,
            source_app="admin_app",
            legacy_transaction_id=payload.id,
        )

    @staticmethod
    def _legacy_request(payload) -> CheckoutRequest:
        items = [CheckoutItemInput(product_id=item.product_id, quantity=item.quantity) for item in (payload.items or [])]
        if not items and payload.items_json:
            try:
                raw_items = json.loads(payload.items_json) if isinstance(payload.items_json, str) else payload.items_json
            except (TypeError, ValueError, json.JSONDecodeError):
                raw_items = []
            items = [
                CheckoutItemInput(product_id=str(item["product_id"]), quantity=int(item.get("quantity", 1)))
                for item in raw_items if isinstance(item, dict) and item.get("product_id")
            ]
        return CheckoutRequest(
            items=items,
            payment=CheckoutPaymentInput(
                cash_amount=Decimal(str(payload.cash_amount or 0)),
                upi_amount=Decimal(str(payload.upi_amount or 0)),
                card_amount=Decimal(str(payload.card_amount or 0)),
                other_paid_amount=Decimal(str(payload.other_paid_amount or 0)),
                credit_amount=Decimal(str(payload.credit_amount or 0)),
                payment_method=payload.payment_method or "Cash",
                payment_option=payload.payment_option or payload.payment_method or "Cash",
            ),
            customer_id=payload.customer_id,
            discount=Decimal(str(payload.discount or 0)),
            branch_id=payload.branch_id,
            idempotency_key=payload.idempotency_key,
            device_id=payload.device_id,
            bill_no=payload.bill_no,
            bill_date=payload.bill_date,
            bill_date_text=payload.bill_date_text,
            is_parcel=payload.is_parcel or False,
        )

    @staticmethod
    def handle_queue_item(db, current_user, action: str, payload: dict):
        from auth.errors import DomainError
        from schemas.transaction_schema import CreateTransactionRequest

        if action == "create":
            TransactionService.create_transaction(db, current_user, CreateTransactionRequest(**payload))
        elif action == "delete":
            raise DomainError(409, "TRANSACTION_FINALIZED", "Finalized transactions cannot be deleted.")
