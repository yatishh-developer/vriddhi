import hashlib
import json
import uuid
from decimal import Decimal
from typing import Callable, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from auth.authorization import require_branch_access, require_permission
from auth.errors import DomainError
from auth.principal import ActorType, PrincipalContext
from models.customer_model import Customer
from models.inventory_movement_model import InventoryMovement
from models.staff_billing_model import StaffPayment, StaffProfile
from models.transaction_item_model import TransactionItem
from models.transaction_model import Transaction
from models.user_model import User
from schemas.checkout_schema import (
    CheckoutItemInput,
    CheckoutItemResponse,
    CheckoutRequest,
    CheckoutResponse,
)
from services.billing_engine import BillingEngine, as_decimal, money
from services.inventory_service import InventoryService
from services.domain_event_service import DomainEventService
from utils.invoice import InvoiceGenerator


PAYMENT_METHOD_COMPONENTS = {
    "CASH": frozenset({"cash"}),
    "UPI": frozenset({"upi"}),
    "CARD": frozenset({"card"}),
    "OTHER": frozenset({"other"}),
    "CREDIT": frozenset({"credit"}),
}


class CheckoutService:
    """One transaction boundary for admin and worker finalized sales."""

    @staticmethod
    def checkout(
        db: Session,
        *,
        principal: PrincipalContext,
        request: CheckoutRequest,
        source_app: str,
        legacy_transaction_id: str | None = None,
        order_id: str | None = None,
        after_create: Optional[Callable[[Transaction], None]] = None,
    ) -> Transaction:
        require_branch_access(principal, request.branch_id)
        branch_id = (request.branch_id or principal.branch_id or "main").strip() or "main"
        if principal.actor_type == ActorType.WORKER:
            require_permission(principal, "billing.create")
            require_permission(principal, "payments.collect")
        if request.discount > 0 and principal.actor_type == ActorType.WORKER:
            require_permission(principal, "billing.discount")

        request_fingerprint = (
            CheckoutService.request_fingerprint(request, order_id=order_id)
            if request.idempotency_key else None
        )
        if request.idempotency_key:
            existing = CheckoutService._by_idempotency(db, principal.business_id, branch_id, source_app, request.idempotency_key)
            if existing:
                CheckoutService.validate_idempotent_result(
                    existing,
                    order_id=order_id,
                    request_fingerprint=request_fingerprint,
                )
                return existing
        if legacy_transaction_id:
            existing = db.query(Transaction).filter(
                Transaction.id == legacy_transaction_id,
                Transaction.business_id == principal.business_id,
            ).first()
            if existing:
                if (existing.branch_id or "main") != branch_id:
                    raise DomainError(403, "BRANCH_ACCESS_DENIED", "Transaction belongs to another branch.")
                return existing

        try:
            customer = CheckoutService._locked_customer(db, principal.business_id, request.customer_id)
            products = InventoryService.locked_products(
                db,
                [item.product_id for item in request.items],
                principal.business_id,
            )
            product_lines = [(products[item.product_id], item.quantity) for item in request.items]
            totals = BillingEngine.calculate(
                product_lines=product_lines,
                discount=request.discount,
                previous_balance=customer.balance_remaining if customer else Decimal("0"),
                is_intra_state=True,
            )
            CheckoutService._validate_payment(
                principal,
                request,
                totals.payable,
                customer,
                strict_method_contract=order_id is not None,
            )
            created_by = CheckoutService._audit_user_id(db, principal)
            transaction = CheckoutService._create_transaction(
                principal=principal,
                request=request,
                source_app=source_app,
                branch_id=branch_id,
                customer=customer,
                totals=totals,
                transaction_id=legacy_transaction_id or str(uuid.uuid4()),
                created_by=created_by,
                order_id=order_id,
                request_fingerprint=request_fingerprint,
            )
            db.add(transaction)
            db.flush()
            for line in totals.lines:
                db.add(
                    TransactionItem(
                        id=str(uuid.uuid4()),
                        transaction_id=transaction.id,
                        product_id=line.product.id,
                        product_name=line.product.name,
                        quantity=line.quantity,
                        price=line.unit_price,
                        subtotal=line.subtotal,
                    )
                )
                InventoryService.deduct_sale(
                    db,
                    product=line.product,
                    quantity=line.quantity,
                    business_id=principal.business_id,
                    branch_id=branch_id,
                    reference_id=transaction.id,
                    created_by=created_by,
                    created_by_staff_id=principal.staff_id,
                    source_app=source_app,
                )
                DomainEventService.enqueue(
                    db, event_type="inventory.changed", aggregate_type="product", aggregate_id=line.product.id,
                    business_id=principal.business_id, branch_id=branch_id,
                    data={"product_id": line.product.id, "change": -line.quantity, "reason": "sale", "transaction_id": transaction.id},
                    actor_id=principal.principal_id,
                )
            CheckoutService._create_payment(db, principal, transaction, request, branch_id, created_by, source_app)
            if customer:
                # The requested credit is the unpaid portion of the entire
                # payable amount, including any previous balance.
                customer.balance_remaining = request.payment.credit_amount
            if after_create:
                after_create(transaction)
            DomainEventService.enqueue(
                db, event_type="transaction.created", aggregate_type="transaction", aggregate_id=transaction.id,
                business_id=principal.business_id, branch_id=branch_id,
                data={"bill_number": transaction.bill_no, "order_id": order_id, "amount": totals.payable}, actor_id=principal.principal_id,
            )
            if customer and request.payment.credit_amount > 0:
                DomainEventService.enqueue(
                    db, event_type="customer.credit_changed", aggregate_type="customer", aggregate_id=customer.id,
                    business_id=principal.business_id, branch_id=branch_id,
                    data={"balance_remaining": request.payment.credit_amount, "transaction_id": transaction.id}, actor_id=principal.principal_id,
                )
            db.commit()
            db.refresh(transaction)
            return transaction
        except IntegrityError as exc:
            db.rollback()
            if request.idempotency_key:
                existing = CheckoutService._by_idempotency(db, principal.business_id, branch_id, source_app, request.idempotency_key)
                if existing:
                    CheckoutService.validate_idempotent_result(
                        existing,
                        order_id=order_id,
                        request_fingerprint=request_fingerprint,
                    )
                    return existing
            raise DomainError(409, "CHECKOUT_ALREADY_PROCESSED", "Checkout was already processed.") from exc
        except Exception:
            db.rollback()
            raise

    @staticmethod
    def response(transaction: Transaction) -> CheckoutResponse:
        line_snapshots = CheckoutService._line_snapshots(transaction)
        items = [
            CheckoutItemResponse(
                product_id=item.product_id,
                product_name=item.product_name,
                quantity=item.quantity,
                unit_price=as_decimal(item.price),
                subtotal=as_decimal(item.subtotal),
                gst_percentage=line_snapshots.get(item.product_id, Decimal("0")),
                tax=money(
                    as_decimal(item.subtotal)
                    * line_snapshots.get(item.product_id, Decimal("0"))
                    / Decimal("100")
                ),
            )
            for item in transaction.items
        ]
        return CheckoutResponse(
            order_id=transaction.order_id,
            transaction_id=transaction.id,
            bill_number=transaction.bill_no,
            payment_method=transaction.payment_method,
            payment_option=transaction.payment_option,
            subtotal=as_decimal(transaction.subtotal),
            total_cgst=as_decimal(transaction.total_cgst),
            total_sgst=as_decimal(transaction.total_sgst),
            total_igst=as_decimal(transaction.total_igst),
            total_tax=as_decimal(transaction.total_tax),
            discount=as_decimal(transaction.discount),
            previous_balance=as_decimal(transaction.old_balance),
            payable=as_decimal(transaction.total_amount),
            cash_amount=as_decimal(transaction.cash_amount),
            upi_amount=as_decimal(transaction.upi_amount),
            card_amount=as_decimal(transaction.card_amount),
            other_paid_amount=as_decimal(transaction.other_paid_amount),
            credit_amount=as_decimal(transaction.credit_amount),
            change=Decimal("0"),
            customer_id=transaction.customer_id,
            items=items,
            created_at=transaction.created_at,
        )

    @staticmethod
    def _by_idempotency(db, business_id, branch_id, source_app, key):
        return db.query(Transaction).filter(
            Transaction.business_id == business_id,
            Transaction.branch_id == branch_id,
            Transaction.source_app == source_app,
            Transaction.idempotency_key == key,
        ).first()

    @staticmethod
    def request_fingerprint(request: CheckoutRequest, *, order_id: str | None) -> str:
        """Create a durable fingerprint of the client checkout intent.

        Product prices and taxes are deliberately excluded because the server
        resolves them authoritatively.  A repeated mutation key must carry the
        same client intent; otherwise returning an old financial result would
        be ambiguous and unsafe.
        """
        payment = request.payment
        payload = {
            "order_id": order_id,
            "branch_id": request.branch_id or "main",
            "customer_id": request.customer_id,
            "discount": str(money(as_decimal(request.discount))),
            "is_parcel": bool(request.is_parcel),
            "items": sorted(
                [
                    {
                        "product_id": item.product_id,
                        "quantity": item.quantity,
                        "notes": item.notes,
                        "variant_id": item.variant_id,
                        "addons": list(item.addons),
                    }
                    for item in request.items
                ],
                key=lambda item: (
                    item["product_id"], item["quantity"], item["notes"] or "",
                    item["variant_id"] or "", tuple(item["addons"]),
                ),
            ),
            "payment": {
                "cash_amount": str(money(as_decimal(payment.cash_amount))),
                "upi_amount": str(money(as_decimal(payment.upi_amount))),
                "card_amount": str(money(as_decimal(payment.card_amount))),
                "other_paid_amount": str(money(as_decimal(payment.other_paid_amount))),
                "credit_amount": str(money(as_decimal(payment.credit_amount))),
                "payment_method": str(payment.payment_method or "").strip().upper(),
                "payment_option": str(payment.payment_option or "").strip().upper(),
            },
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    @staticmethod
    def validate_idempotent_result(
        transaction: Transaction,
        *,
        order_id: str | None,
        request_fingerprint: str | None,
    ) -> None:
        if order_id is not None and transaction.order_id != order_id:
            raise DomainError(
                409,
                "IDEMPOTENCY_CONFLICT",
                "This checkout key belongs to a different order.",
            )
        if (
            request_fingerprint
            and transaction.checkout_request_hash
            and transaction.checkout_request_hash != request_fingerprint
        ):
            raise DomainError(
                409,
                "IDEMPOTENCY_CONFLICT",
                "This checkout key was already used with different checkout details.",
            )

    @staticmethod
    def _line_snapshots(transaction: Transaction) -> dict[str, Decimal]:
        """Recover immutable line tax rates from the server-created snapshot."""
        try:
            raw_lines = json.loads(transaction.items_json or "[]")
        except (TypeError, ValueError, json.JSONDecodeError):
            raw_lines = []
        if not isinstance(raw_lines, list):
            return {}
        return {
            str(line["product_id"]): as_decimal(line.get("gst_percentage", 0))
            for line in raw_lines
            if isinstance(line, dict) and line.get("product_id")
        }

    @staticmethod
    def _locked_customer(db: Session, business_id: str, customer_id: str | None) -> Customer | None:
        if not customer_id:
            return None
        customer = db.query(Customer).filter(
            Customer.id == customer_id,
            Customer.business_id == business_id,
            Customer.is_deleted == False,
        ).with_for_update().first()
        if not customer:
            raise DomainError(404, "CUSTOMER_NOT_FOUND", "Customer was not found for this business.")
        return customer

    @staticmethod
    def _validate_payment(
        principal: PrincipalContext,
        request: CheckoutRequest,
        payable: Decimal,
        customer: Customer | None,
        *,
        strict_method_contract: bool,
    ) -> None:
        payment = request.payment
        values = [payment.cash_amount, payment.upi_amount, payment.card_amount, payment.other_paid_amount, payment.credit_amount]
        if any(value < 0 for value in values):
            raise DomainError(400, "PAYMENT_INVALID", "Payment amounts cannot be negative.")
        paid = money(payment.cash_amount + payment.upi_amount + payment.card_amount + payment.other_paid_amount)
        credit = money(payment.credit_amount)
        allocated = money(paid + credit)
        if allocated < payable:
            raise DomainError(400, "PAYMENT_INSUFFICIENT", "Payment does not cover the payable amount.")
        if allocated > payable:
            raise DomainError(400, "PAYMENT_INVALID", "Payment allocation exceeds the payable amount; change is not supported.")
        if strict_method_contract:
            CheckoutService._validate_payment_method(payment)
        if credit > 0:
            if not customer:
                raise DomainError(400, "CUSTOMER_REQUIRED_FOR_CREDIT", "Credit payment requires a customer.")
            if principal.actor_type == ActorType.WORKER:
                if "*" not in principal.permissions and "credit.create" not in principal.permissions:
                    raise DomainError(403, "CREDIT_NOT_ALLOWED", "You do not have permission to create a credit sale.")

    @staticmethod
    def _validate_payment_method(payment) -> None:
        method = str(payment.payment_method or "").strip().upper()
        amounts = {
            "cash": money(as_decimal(payment.cash_amount)),
            "upi": money(as_decimal(payment.upi_amount)),
            "card": money(as_decimal(payment.card_amount)),
            "other": money(as_decimal(payment.other_paid_amount)),
            "credit": money(as_decimal(payment.credit_amount)),
        }
        active_components = {name for name, amount in amounts.items() if amount > 0}
        if method == "SPLIT":
            if len(active_components) < 2:
                raise DomainError(400, "PAYMENT_INVALID", "Split payment requires at least two payment components.")
            return
        expected_components = PAYMENT_METHOD_COMPONENTS.get(method)
        if not expected_components or active_components != expected_components:
            raise DomainError(
                400,
                "PAYMENT_INVALID",
                "Payment method does not match the submitted payment allocation.",
            )

    @staticmethod
    def _create_transaction(*, principal, request, source_app, branch_id, customer, totals, transaction_id, created_by, order_id=None, request_fingerprint=None):
        payment = request.payment
        items_json = json.dumps([
            {
                "product_id": line.product.id,
                "product_name": line.product.name,
                "quantity": line.quantity,
                "price": str(line.unit_price),
                "subtotal": str(line.subtotal),
                "gst_percentage": str(line.gst_percentage),
            }
            for line in totals.lines
        ])
        return Transaction(
            id=transaction_id,
            business_id=principal.business_id,
            branch_id=branch_id,
            order_id=order_id,
            customer_id=customer.id if customer else None,
            flow="Staff" if principal.actor_type == ActorType.WORKER else "Quick",
            bill_no=request.bill_no or f"{InvoiceGenerator.generate_invoice_number()}-{transaction_id[:8].upper()}",
            bill_date=request.bill_date,
            bill_date_text=request.bill_date_text,
            customer_name=customer.name if customer else "",
            customer_phone=customer.phone if customer else "",
            customer_address=customer.address if customer else "",
            payment_method=payment.payment_method,
            payment_option=payment.payment_option,
            cash_amount=money(payment.cash_amount),
            upi_amount=money(payment.upi_amount),
            card_amount=money(payment.card_amount),
            other_paid_amount=money(payment.other_paid_amount),
            credit_amount=money(payment.credit_amount),
            discount=totals.discount,
            is_parcel=request.is_parcel,
            is_hold=False,
            items_json=items_json,
            total_amount=totals.payable,
            subtotal=totals.subtotal,
            total_cgst=totals.total_cgst,
            total_sgst=totals.total_sgst,
            total_igst=totals.total_igst,
            total_tax=totals.total_tax,
            old_balance=totals.previous_balance,
            is_intra_state=True,
            status="completed",
            created_by=created_by,
            created_by_staff_id=principal.staff_id,
            source_app=source_app,
            sync_status="pending" if principal.actor_type == ActorType.WORKER else "synced",
            idempotency_key=request.idempotency_key,
            checkout_request_hash=request_fingerprint,
            device_id=request.device_id or principal.device_id,
        )

    @staticmethod
    def _audit_user_id(db: Session, principal: PrincipalContext) -> str:
        if principal.user_id:
            return principal.user_id
        staff = db.query(StaffProfile).filter(StaffProfile.id == principal.staff_id).first()
        if staff and staff.created_by:
            return staff.created_by
        user = db.query(User).filter(User.business_id == principal.business_id).first()
        if not user:
            raise DomainError(409, "PAYMENT_INVALID", "Checkout requires a business owner account.")
        return user.id

    @staticmethod
    def _create_payment(db, principal, transaction, request, branch_id, created_by, source_app):
        payment = request.payment
        paid = money(payment.cash_amount + payment.upi_amount + payment.card_amount + payment.other_paid_amount)
        db.add(
            StaffPayment(
                id=str(uuid.uuid4()),
                business_id=principal.business_id,
                branch_id=branch_id,
                staff_id=principal.staff_id,
                staff_name=None,
                bill_transaction_id=transaction.id,
                cash_amount=money(payment.cash_amount),
                upi_amount=money(payment.upi_amount),
                card_amount=money(payment.card_amount),
                other_paid_amount=money(payment.other_paid_amount),
                credit_amount=money(payment.credit_amount),
                total_paid_amount=paid,
                payment_json=json.dumps({
                    "payment_method": payment.payment_method,
                    "payment_option": payment.payment_option,
                }),
                created_by=created_by,
                created_by_staff_id=principal.staff_id,
                source_app=source_app,
                sync_status="pending" if principal.actor_type == ActorType.WORKER else "synced",
            )
        )
