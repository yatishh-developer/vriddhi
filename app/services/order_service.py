from datetime import datetime, timezone
from decimal import Decimal
import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from auth.authorization import require_branch_access, require_business_access, require_capability, require_permission
from auth.errors import DomainError
from auth.principal import PrincipalContext
from models.customer_model import Customer
from models.order_model import Order, OrderItem
from models.product_model import Product
from models.transaction_model import Transaction
from schemas.checkout_schema import CheckoutItemInput, CheckoutRequest
from schemas.order_schema import (
    OrderCancelRequest,
    OrderCheckoutRequest,
    OrderCheckoutResponse,
    OrderCreate,
    OrderHoldRequest,
    OrderItemResponse,
    OrderItemUpdate,
    OrderItemsCreate,
    OrderListResponse,
    OrderResponse,
)
from services.checkout_service import CheckoutService
from services.billing_engine import as_decimal
from services.domain_event_service import DomainEventService


V1_SOURCE_APP = "unified_api_v1"
MUTABLE_ORDER_STATUSES = {"DRAFT", "ACTIVE"}


class OrderService:
    """Actor-neutral order domain; final financial work remains in CheckoutService."""

    @staticmethod
    def _scope(principal: PrincipalContext, business_id: str, branch_id: str) -> None:
        require_business_access(principal, business_id)
        require_branch_access(principal, branch_id)
        require_capability(principal, "orders")

    @staticmethod
    def _customer(db: Session, business_id: str, customer_id: str | None) -> Customer | None:
        if not customer_id:
            return None
        customer = db.query(Customer).filter(
            Customer.id == customer_id,
            Customer.business_id == business_id,
            Customer.is_deleted == False,
        ).first()
        if not customer:
            raise DomainError(404, "CUSTOMER_NOT_FOUND", "Customer was not found for this business.")
        return customer

    @staticmethod
    def _order(db: Session, principal: PrincipalContext, business_id: str, branch_id: str, order_id: str, *, lock: bool = False) -> Order:
        OrderService._scope(principal, business_id, branch_id)
        query = db.query(Order).filter(
            Order.id == order_id,
            Order.business_id == business_id,
            Order.branch_id == branch_id,
        )
        if lock:
            query = query.with_for_update()
        order = query.first()
        if not order:
            raise DomainError(404, "ORDER_NOT_FOUND", "Order was not found for this business and branch.")
        return order

    @staticmethod
    def _check_version(order: Order, expected_version: int | None) -> None:
        if expected_version is not None and expected_version != order.version:
            raise DomainError(409, "VERSION_CONFLICT", f"Order version is {order.version}.")

    @staticmethod
    def _increment_version(order: Order) -> None:
        order.version += 1

    @staticmethod
    def _response(db: Session, order: Order) -> OrderResponse:
        customer = OrderService._customer(db, order.business_id, order.customer_id)
        transaction = db.query(Transaction).filter(Transaction.order_id == order.id).first()
        return OrderResponse(
            id=order.id,
            business_id=order.business_id,
            branch_id=order.branch_id,
            order_type=order.order_type,
            status=order.status,
            customer_id=order.customer_id,
            customer=(
                {"id": customer.id, "name": customer.name, "phone": customer.phone}
                if customer else None
            ),
            table_session_id=order.table_session_id,
            transaction_id=transaction.id if transaction else None,
            cancellation_reason=order.cancellation_reason,
            version=order.version,
            created_by=order.created_by,
            created_by_staff_id=order.created_by_staff_id,
            created_at=order.created_at,
            updated_at=order.updated_at,
            completed_at=order.completed_at,
            cancelled_at=order.cancelled_at,
            items=[
                OrderItemResponse.model_validate(item)
                for item in sorted(order.items, key=lambda row: (row.created_at, row.id))
            ],
        )

    @staticmethod
    def create(db: Session, principal: PrincipalContext, business_id: str, branch_id: str, payload: OrderCreate) -> OrderResponse:
        OrderService._scope(principal, business_id, branch_id)
        require_permission(principal, "orders.create")
        if payload.order_type == "DINE_IN":
            raise DomainError(400, "DINE_IN_ORDER_REQUIRES_TABLE_SESSION", "Open a table session to create a dine-in order.")
        if payload.idempotency_key:
            existing = db.query(Order).filter(
                Order.business_id == business_id,
                Order.branch_id == branch_id,
                Order.source_app == V1_SOURCE_APP,
                Order.idempotency_key == payload.idempotency_key,
            ).first()
            if existing:
                return OrderService._response(db, existing)
        OrderService._customer(db, business_id, payload.customer_id)
        order = Order(
            id=str(uuid.uuid4()),
            business_id=business_id,
            branch_id=branch_id,
            order_type=payload.order_type,
            status="ACTIVE",
            customer_id=payload.customer_id,
            created_by=CheckoutService._audit_user_id(db, principal),
            created_by_staff_id=principal.staff_id,
            source_app=V1_SOURCE_APP,
            idempotency_key=payload.idempotency_key,
            version=1,
        )
        try:
            db.add(order)
            DomainEventService.enqueue(
                db, event_type="order.created", aggregate_type="order", aggregate_id=order.id,
                business_id=business_id, branch_id=branch_id,
                data={"order_type": order.order_type, "status": order.status}, actor_id=principal.principal_id,
            )
            db.commit()
            db.refresh(order)
            return OrderService._response(db, order)
        except IntegrityError as exc:
            db.rollback()
            if payload.idempotency_key:
                existing = db.query(Order).filter(
                    Order.business_id == business_id, Order.branch_id == branch_id,
                    Order.source_app == V1_SOURCE_APP, Order.idempotency_key == payload.idempotency_key,
                ).first()
                if existing:
                    return OrderService._response(db, existing)
            raise DomainError(409, "ORDER_ALREADY_CREATED", "Order creation was already processed.") from exc

    @staticmethod
    def create_dine_in_for_session(
        db: Session,
        principal: PrincipalContext,
        business_id: str,
        branch_id: str,
        *,
        table_session_id: str,
        customer_id: str | None,
    ) -> Order:
        """Create an uncommitted DINE_IN order for TableService's UoW."""
        OrderService._scope(principal, business_id, branch_id)
        require_capability(principal, "table_management")
        require_permission(principal, "orders.create")
        OrderService._customer(db, business_id, customer_id)
        order = Order(
            id=str(uuid.uuid4()), business_id=business_id, branch_id=branch_id,
            order_type="DINE_IN", status="ACTIVE", customer_id=customer_id,
            table_session_id=table_session_id,
            created_by=CheckoutService._audit_user_id(db, principal),
            created_by_staff_id=principal.staff_id, source_app=V1_SOURCE_APP, version=1,
        )
        db.add(order)
        DomainEventService.enqueue(
            db, event_type="order.created", aggregate_type="order", aggregate_id=order.id,
            business_id=business_id, branch_id=branch_id,
            data={"order_type": order.order_type, "table_session_id": table_session_id}, actor_id=principal.principal_id,
        )
        return order

    @staticmethod
    def add_items(db: Session, principal: PrincipalContext, business_id: str, branch_id: str, order_id: str, payload: OrderItemsCreate) -> OrderResponse:
        require_permission(principal, "orders.modify")
        order = OrderService._order(db, principal, business_id, branch_id, order_id, lock=True)
        OrderService._check_version(order, payload.expected_version)
        if order.status not in MUTABLE_ORDER_STATUSES:
            raise DomainError(409, "ORDER_NOT_MODIFIABLE", "Only active draft order items can be modified.")
        product_ids = sorted({item.product_id for item in payload.items})
        products = {
            product.id: product
            for product in db.query(Product).filter(
                Product.id.in_(product_ids), Product.business_id == business_id, Product.is_deleted == False,
            ).with_for_update().all()
        }
        created_items = []
        for item in payload.items:
            product = products.get(item.product_id)
            if not product:
                raise DomainError(404, "PRODUCT_NOT_FOUND", "Product was not found for this business.")
            created = OrderItem(
                id=str(uuid.uuid4()), order_id=order.id, business_id=business_id, branch_id=branch_id,
                product_id=product.id, product_name_snapshot=product.name,
                unit_price_snapshot=as_decimal(product.price), tax_rate_snapshot=as_decimal(product.gst_percentage),
                quantity=item.quantity, notes=item.notes, status="DRAFT", version=1,
            )
            db.add(created)
            created_items.append(created)
        OrderService._increment_version(order)
        for item in created_items:
            DomainEventService.enqueue(
                db, event_type="order.item_added", aggregate_type="order", aggregate_id=order.id,
                business_id=business_id, branch_id=branch_id,
                data={"order_item_id": item.id, "product_id": item.product_id, "quantity": item.quantity}, actor_id=principal.principal_id,
            )
        db.commit()
        db.refresh(order)
        return OrderService._response(db, order)

    @staticmethod
    def update_item(db: Session, principal: PrincipalContext, business_id: str, branch_id: str, order_id: str, item_id: str, payload: OrderItemUpdate) -> OrderResponse:
        require_permission(principal, "orders.modify")
        order = OrderService._order(db, principal, business_id, branch_id, order_id, lock=True)
        OrderService._check_version(order, payload.expected_version)
        if order.status not in MUTABLE_ORDER_STATUSES:
            raise DomainError(409, "ORDER_NOT_MODIFIABLE", "Only active draft order items can be modified.")
        item = db.query(OrderItem).filter(OrderItem.id == item_id, OrderItem.order_id == order.id).with_for_update().first()
        if not item:
            raise DomainError(404, "ORDER_ITEM_NOT_FOUND", "Order item was not found.")
        if item.status != "DRAFT":
            raise DomainError(409, "ORDER_ITEM_NOT_MODIFIABLE", "Only draft items can be modified.")
        if payload.quantity == 0:
            if item.kot_sent_quantity > 0:
                raise DomainError(409, "KOT_QUANTITY_ALREADY_SENT", "Kitchen-sent items cannot be removed without a cancellation record.")
            db.delete(item)
        else:
            if payload.quantity is not None:
                minimum_quantity = item.kot_sent_quantity - item.cancelled_quantity
                if payload.quantity < minimum_quantity:
                    raise DomainError(409, "KOT_QUANTITY_ALREADY_SENT", "Quantity cannot be reduced below kitchen-sent quantity.")
                item.quantity = payload.quantity
            if payload.notes is not None:
                item.notes = payload.notes
            item.version += 1
        OrderService._increment_version(order)
        DomainEventService.enqueue(
            db, event_type="order.item_updated", aggregate_type="order", aggregate_id=order.id,
            business_id=business_id, branch_id=branch_id,
            data={"order_item_id": item_id, "quantity": payload.quantity, "removed": payload.quantity == 0}, actor_id=principal.principal_id,
        )
        db.commit()
        db.refresh(order)
        return OrderService._response(db, order)

    @staticmethod
    def hold(db: Session, principal: PrincipalContext, business_id: str, branch_id: str, order_id: str, payload: OrderHoldRequest) -> OrderResponse:
        require_permission(principal, "orders.hold")
        order = OrderService._order(db, principal, business_id, branch_id, order_id, lock=True)
        OrderService._check_version(order, payload.expected_version)
        if order.status != "ACTIVE":
            raise DomainError(409, "ORDER_TRANSITION_INVALID", "Only active orders can be held.")
        order.status = "HELD"
        OrderService._increment_version(order)
        DomainEventService.enqueue(db, event_type="order.held", aggregate_type="order", aggregate_id=order.id, business_id=business_id, branch_id=branch_id, data={"status": order.status}, actor_id=principal.principal_id)
        db.commit()
        db.refresh(order)
        return OrderService._response(db, order)

    @staticmethod
    def resume(db: Session, principal: PrincipalContext, business_id: str, branch_id: str, order_id: str, payload: OrderHoldRequest) -> OrderResponse:
        require_permission(principal, "orders.resume")
        order = OrderService._order(db, principal, business_id, branch_id, order_id, lock=True)
        OrderService._check_version(order, payload.expected_version)
        if order.status != "HELD":
            raise DomainError(409, "ORDER_TRANSITION_INVALID", "Only held orders can be resumed.")
        order.status = "ACTIVE"
        OrderService._increment_version(order)
        DomainEventService.enqueue(db, event_type="order.resumed", aggregate_type="order", aggregate_id=order.id, business_id=business_id, branch_id=branch_id, data={"status": order.status}, actor_id=principal.principal_id)
        db.commit()
        db.refresh(order)
        return OrderService._response(db, order)

    @staticmethod
    def cancel(db: Session, principal: PrincipalContext, business_id: str, branch_id: str, order_id: str, payload: OrderCancelRequest) -> OrderResponse:
        require_permission(principal, "orders.cancel")
        order = OrderService._order(db, principal, business_id, branch_id, order_id, lock=True)
        OrderService._check_version(order, payload.expected_version)
        if order.status not in {"DRAFT", "ACTIVE", "HELD"}:
            raise DomainError(409, "ORDER_TRANSITION_INVALID", "Only uncompleted orders can be cancelled.")
        order.status = "CANCELLED"
        order.cancellation_reason = payload.reason
        order.cancelled_at = datetime.now(timezone.utc)
        OrderService._increment_version(order)
        DomainEventService.enqueue(db, event_type="order.cancelled", aggregate_type="order", aggregate_id=order.id, business_id=business_id, branch_id=branch_id, data={"reason": payload.reason}, actor_id=principal.principal_id)
        db.commit()
        db.refresh(order)
        return OrderService._response(db, order)

    @staticmethod
    def checkout(db: Session, principal: PrincipalContext, business_id: str, branch_id: str, order_id: str, payload: OrderCheckoutRequest) -> OrderCheckoutResponse:
        OrderService._scope(principal, business_id, branch_id)
        require_capability(principal, "billing")
        require_permission(principal, "billing.create")
        order = OrderService._order(db, principal, business_id, branch_id, order_id, lock=True)
        OrderService._check_version(order, payload.expected_version)
        if order.status == "COMPLETED":
            transaction = db.query(Transaction).filter(Transaction.order_id == order.id).first()
            if transaction:
                return OrderCheckoutResponse(order=OrderService._response(db, order), checkout=CheckoutService.response(transaction))
        if order.status != "ACTIVE":
            raise DomainError(409, "ORDER_TRANSITION_INVALID", "Only active orders can be checked out.")
        if order.order_type == "DINE_IN":
            from models.table_management_model import TableSession

            session = db.query(TableSession).filter(
                TableSession.id == order.table_session_id,
                TableSession.business_id == business_id,
                TableSession.branch_id == branch_id,
            ).with_for_update().first()
            if not session:
                raise DomainError(404, "DINE_IN_ORDER_NOT_FOUND", "Dine-in order has no active table session.")
            if session.status in {"CLOSED", "CANCELLED"}:
                raise DomainError(409, "TABLE_SESSION_CLOSED", "Table session is no longer open.")
        items = [item for item in order.items if item.status == "DRAFT" and item.quantity > item.cancelled_quantity]
        if not items:
            raise DomainError(400, "ORDER_EMPTY", "Order has no billable items.")
        checkout_request = CheckoutRequest(
            items=[CheckoutItemInput(product_id=item.product_id, quantity=item.quantity - item.cancelled_quantity, notes=item.notes) for item in items],
            payment=payload.payment,
            customer_id=order.customer_id,
            discount=payload.discount,
            branch_id=branch_id,
            idempotency_key=payload.idempotency_key or f"order:{order.id}:checkout",
            is_parcel=payload.is_parcel or order.order_type == "TAKEAWAY",
        )

        def complete_order(transaction: Transaction) -> None:
            order.status = "COMPLETED"
            order.completed_at = datetime.now(timezone.utc)
            OrderService._increment_version(order)
            for item in items:
                item.status = "BILLED"
                item.billed_quantity = item.quantity - item.cancelled_quantity
                item.version += 1
            if order.order_type == "DINE_IN":
                from models.table_management_model import TableSession, TableSessionTable

                session = db.query(TableSession).filter(TableSession.id == order.table_session_id).with_for_update().one()
                session.status = "CLOSED"
                session.closed_at = datetime.now(timezone.utc)
                session.version += 1
                db.query(TableSessionTable).filter(
                    TableSessionTable.session_id == session.id,
                    TableSessionTable.is_active == True,
                ).update({"is_active": False}, synchronize_session=False)
                DomainEventService.enqueue(
                    db, event_type="table.session_closed", aggregate_type="table_session", aggregate_id=session.id,
                    business_id=business_id, branch_id=branch_id, data={"table_id": session.primary_table_id, "status": session.status}, actor_id=principal.principal_id,
                )
            DomainEventService.enqueue(
                db, event_type="order.completed", aggregate_type="order", aggregate_id=order.id,
                business_id=business_id, branch_id=branch_id, data={"transaction_id": transaction.id}, actor_id=principal.principal_id,
            )

        transaction = CheckoutService.checkout(
            db, principal=principal, request=checkout_request, source_app=V1_SOURCE_APP,
            order_id=order.id, after_create=complete_order,
        )
        db.refresh(order)
        return OrderCheckoutResponse(order=OrderService._response(db, order), checkout=CheckoutService.response(transaction))

    @staticmethod
    def get(db: Session, principal: PrincipalContext, business_id: str, branch_id: str, order_id: str) -> OrderResponse:
        return OrderService._response(db, OrderService._order(db, principal, business_id, branch_id, order_id))

    @staticmethod
    def list(db: Session, principal: PrincipalContext, business_id: str, branch_id: str, *, status: str | None, order_type: str | None, customer_id: str | None, created_from: datetime | None, created_to: datetime | None, page: int, page_size: int) -> OrderListResponse:
        OrderService._scope(principal, business_id, branch_id)
        require_permission(principal, "orders.view")
        query = db.query(Order).filter(Order.business_id == business_id, Order.branch_id == branch_id)
        if status:
            query = query.filter(Order.status == status)
        if order_type:
            query = query.filter(Order.order_type == order_type)
        if customer_id:
            query = query.filter(Order.customer_id == customer_id)
        if created_from:
            query = query.filter(Order.created_at >= created_from)
        if created_to:
            query = query.filter(Order.created_at <= created_to)
        total = query.count()
        orders = query.order_by(Order.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
        return OrderListResponse(items=[OrderService._response(db, order) for order in orders], total=total, page=page, page_size=page_size)
