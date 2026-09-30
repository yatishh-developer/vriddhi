from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from auth.errors import ApiError
from auth.principal import ActorType, PrincipalContext
from database.database import Base
from models.business_model import Business
from models.customer_model import Customer
from models.inventory_movement_model import InventoryMovement
from models.order_model import Order, OrderItem
from models.product_model import Product
from models.staff_billing_model import StaffPayment, StaffProfile
from models.transaction_model import Transaction
from models.user_model import User
from schemas.order_schema import (
    OrderCancelRequest,
    OrderCheckoutRequest,
    OrderCreate,
    OrderHoldRequest,
    OrderItemCreate,
    OrderItemUpdate,
    OrderItemsCreate,
)
from services.order_service import OrderService
from services.staff_billing_service import StaffBillingService


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    business = Business(id="business-a", name="Cafe", business_type="Restaurant")
    other_business = Business(id="business-b", name="Other", business_type="Retail")
    owner = User(id="owner-a", business_id="business-a", email="owner@example.com", password_hash="hash")
    worker = StaffProfile(
        id="worker-a", business_id="business-a", branch_id="branch-a", staff_name="Counter", role="cashier",
        permissions_json='{"create_bill": true, "hold_bill": true, "resume_held_bill": true}',
        allowed_apps='["staff_billing_app"]', status="active", created_by="owner-a",
    )
    product = Product(
        id="product-a", business_id="business-a", name="Tea", price=Decimal("100.00"),
        gst_percentage=Decimal("18.00"), stock_quantity=10, in_stock=True, is_stockless=False,
    )
    other_product = Product(
        id="product-b", business_id="business-b", name="Other", price=Decimal("1.00"),
        gst_percentage=Decimal("0.00"), stock_quantity=10, in_stock=True, is_stockless=False,
    )
    customer = Customer(id="customer-a", business_id="business-a", name="Asha", phone="1")
    session.add_all([business, other_business, owner, worker, product, other_product, customer])
    session.commit()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _owner():
    return PrincipalContext(
        principal_id="owner-a", actor_type=ActorType.OWNER, business_id="business-a", role="owner",
        user_id="owner-a", permissions=frozenset({"*"}), capabilities=frozenset({"*"}),
    )


def _worker(db):
    return StaffBillingService._principal_for_staff(db, db.get(StaffProfile, "worker-a"))


def _error(callable_):
    with pytest.raises(ApiError) as exc:
        callable_()
    return exc.value.code


def _order_with_item(db, *, principal=None, product_id="product-a"):
    principal = principal or _owner()
    order = OrderService.create(db, principal, "business-a", "branch-a", OrderCreate(order_type="QUICK"))
    return OrderService.add_items(
        db, principal, "business-a", "branch-a", order.id,
        OrderItemsCreate(items=[OrderItemCreate(product_id=product_id, quantity=1, notes="No onion")]),
    )


def _checkout(db, order_id, *, key=None):
    return OrderService.checkout(
        db, _owner(), "business-a", "branch-a", order_id,
        OrderCheckoutRequest(payment={"cash_amount": "118.00"}, idempotency_key=key),
    )


def test_admin_and_worker_create_orders_through_same_domain_path(db):
    admin_order = OrderService.create(db, _owner(), "business-a", "branch-a", OrderCreate(order_type="QUICK"))
    worker_order = OrderService.create(db, _worker(db), "business-a", "branch-a", OrderCreate(order_type="TAKEAWAY"))

    assert admin_order.status == worker_order.status == "ACTIVE"
    assert {admin_order.order_type, worker_order.order_type} == {"QUICK", "TAKEAWAY"}
    assert db.query(Order).count() == 2


def test_business_and_branch_isolation_are_enforced(db):
    assert _error(lambda: OrderService.create(
        db, _owner(), "business-b", "branch-a", OrderCreate(),
    )) == "BUSINESS_ACCESS_DENIED"
    assert _error(lambda: OrderService.create(
        db, _worker(db), "business-a", "branch-b", OrderCreate(),
    )) == "BRANCH_ACCESS_DENIED"


def test_order_item_snapshots_server_price_and_rejects_fake_price_and_inactive_product(db):
    order = _order_with_item(db)
    item = order.items[0]
    assert item.unit_price_snapshot == Decimal("100.00")
    assert item.tax_rate_snapshot == Decimal("18.00")
    with pytest.raises(ValidationError):
        OrderItemCreate(product_id="product-a", quantity=1, unit_price_snapshot="1.00")

    inactive = db.get(Product, "product-a")
    inactive.is_deleted = True
    db.commit()
    fresh = OrderService.create(db, _owner(), "business-a", "branch-a", OrderCreate())
    assert _error(lambda: OrderService.add_items(
        db, _owner(), "business-a", "branch-a", fresh.id,
        OrderItemsCreate(items=[OrderItemCreate(product_id="product-a", quantity=1)]),
    )) == "PRODUCT_NOT_FOUND"
    with pytest.raises(ValidationError):
        OrderItemCreate(product_id="product-a", quantity=0)


def test_order_item_update_hold_resume_cancel_and_mutability_rules(db):
    order = _order_with_item(db)
    item = order.items[0]
    updated = OrderService.update_item(
        db, _owner(), "business-a", "branch-a", order.id, item.id,
        OrderItemUpdate(quantity=2, notes="Less sugar", expected_version=order.version),
    )
    assert updated.items[0].quantity == 2
    held = OrderService.hold(db, _owner(), "business-a", "branch-a", order.id, OrderHoldRequest(expected_version=updated.version))
    assert held.status == "HELD"
    assert _error(lambda: OrderService.hold(
        db, _owner(), "business-a", "branch-a", order.id, OrderHoldRequest(),
    )) == "ORDER_TRANSITION_INVALID"
    resumed = OrderService.resume(db, _owner(), "business-a", "branch-a", order.id, OrderHoldRequest(expected_version=held.version))
    assert resumed.status == "ACTIVE"
    cancelled = OrderService.cancel(
        db, _owner(), "business-a", "branch-a", order.id,
        OrderCancelRequest(reason="Customer left", expected_version=resumed.version),
    )
    assert cancelled.status == "CANCELLED"
    assert _error(lambda: OrderService.update_item(
        db, _owner(), "business-a", "branch-a", order.id, item.id, OrderItemUpdate(quantity=1),
    )) == "ORDER_NOT_MODIFIABLE"


def test_order_checkout_uses_checkout_service_and_completes_atomically(db):
    order = _order_with_item(db)
    result = _checkout(db, order.id, key="order-checkout-1")
    stored_order = db.get(Order, order.id)
    transaction = db.query(Transaction).filter(Transaction.order_id == order.id).one()

    assert result.order.status == stored_order.status == "COMPLETED"
    assert transaction.id == result.checkout.transaction_id
    assert transaction.total_amount == Decimal("118.00")
    assert db.get(Product, "product-a").stock_quantity == 9
    assert db.query(InventoryMovement).count() == 1
    assert db.query(StaffPayment).count() == 1
    assert db.query(OrderItem).filter_by(order_id=order.id).one().status == "BILLED"
    item_id = db.query(OrderItem).filter_by(order_id=order.id).one().id
    assert _error(lambda: OrderService.update_item(
        db, _owner(), "business-a", "branch-a", order.id, item_id, OrderItemUpdate(quantity=2),
    )) == "ORDER_NOT_MODIFIABLE"


def test_failed_checkout_leaves_order_active_without_stock_deduction(db):
    order = _order_with_item(db)
    product = db.get(Product, "product-a")
    product.stock_quantity = 0
    product.in_stock = False
    db.commit()

    assert _error(lambda: _checkout(db, order.id)) == "INSUFFICIENT_STOCK"
    assert db.get(Order, order.id).status == "ACTIVE"
    assert db.get(Product, "product-a").stock_quantity == 0
    assert db.query(Transaction).count() == 0
    assert db.query(InventoryMovement).count() == 0


def test_checkout_retry_and_second_device_attempt_create_one_transaction_and_one_deduction(db):
    order = _order_with_item(db)
    first = _checkout(db, order.id, key="retry-1")
    retry = _checkout(db, order.id, key="retry-1")
    second_attempt = _checkout(db, order.id, key="different-client-key")

    assert first.checkout.transaction_id == retry.checkout.transaction_id == second_attempt.checkout.transaction_id
    assert db.query(Transaction).count() == 1
    assert db.query(InventoryMovement).count() == 1
    assert db.get(Product, "product-a").stock_quantity == 9


def test_order_financial_result_matches_direct_checkout_engine_output(db):
    order = _order_with_item(db)
    order_result = _checkout(db, order.id)
    direct_product = Product(
        id="product-copy", business_id="business-a", name="Tea copy", price=Decimal("100.00"),
        gst_percentage=Decimal("18.00"), stock_quantity=10, in_stock=True, is_stockless=False,
    )
    db.add(direct_product)
    db.commit()
    comparison_order = _order_with_item(db, product_id=direct_product.id)
    comparison = _checkout(db, comparison_order.id)

    assert order_result.checkout.payable == comparison.checkout.payable == Decimal("118.00")
    assert order_result.checkout.total_tax == comparison.checkout.total_tax == Decimal("18.00")
