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
from models.order_model import Order, OrderItem, OrderItemMutation
from models.outbox_model import OutboxEvent
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


def test_add_items_idempotency_recovers_response_loss_before_stale_version_check(db):
    order = OrderService.create(db, _owner(), "business-a", "branch-a", OrderCreate(order_type="QUICK"))
    payload = OrderItemsCreate(
        items=[OrderItemCreate(product_id="product-a", quantity=2, notes="Less sugar")],
        expected_version=1,
        idempotency_key="item-response-loss-key",
    )

    first = OrderService.add_items(db, _owner(), "business-a", "branch-a", order.id, payload)
    # Remove all ORM identity-map state to prove recovery reads the durable
    # mutation record rather than process-local memory.
    db.expunge_all()
    retry = OrderService.add_items(db, _owner(), "business-a", "branch-a", order.id, payload)

    assert first.version == retry.version == 2
    assert [(item.product_id, item.quantity, item.notes) for item in retry.items] == [
        ("product-a", 2, "Less sugar"),
    ]
    assert db.query(OrderItem).filter(OrderItem.order_id == order.id).count() == 1
    assert db.query(OrderItem).filter(OrderItem.order_id == order.id).one().quantity == 2
    mutation = db.query(OrderItemMutation).filter(OrderItemMutation.order_id == order.id).one()
    assert mutation.result_order_version == 2


def test_add_items_same_key_changed_payload_conflicts_and_different_key_is_new_mutation(db):
    order = OrderService.create(db, _owner(), "business-a", "branch-a", OrderCreate(order_type="QUICK"))
    first = OrderService.add_items(
        db,
        _owner(),
        "business-a",
        "branch-a",
        order.id,
        OrderItemsCreate(
            items=[OrderItemCreate(product_id="product-a", quantity=2)],
            expected_version=1,
            idempotency_key="item-conflict-key",
        ),
    )
    assert _error(lambda: OrderService.add_items(
        db,
        _owner(),
        "business-a",
        "branch-a",
        order.id,
        OrderItemsCreate(
            items=[OrderItemCreate(product_id="product-a", quantity=3)],
            expected_version=1,
            idempotency_key="item-conflict-key",
        ),
    )) == "IDEMPOTENCY_CONFLICT"
    assert _error(lambda: OrderService.add_items(
        db,
        _owner(),
        "business-a",
        "branch-a",
        order.id,
        OrderItemsCreate(
            items=[OrderItemCreate(product_id="product-b", quantity=2)],
            expected_version=1,
            idempotency_key="item-conflict-key",
        ),
    )) == "IDEMPOTENCY_CONFLICT"

    second = OrderService.add_items(
        db,
        _owner(),
        "business-a",
        "branch-a",
        order.id,
        OrderItemsCreate(
            items=[OrderItemCreate(product_id="product-a", quantity=1)],
            expected_version=first.version,
            idempotency_key="item-new-key",
        ),
    )
    assert second.version == 3
    assert sorted(item.quantity for item in second.items) == [1, 2]


def test_add_items_key_is_scoped_to_order_and_finalized_retry_is_recoverable(db):
    first_order = OrderService.create(db, _owner(), "business-a", "branch-a", OrderCreate(order_type="QUICK"))
    second_order = OrderService.create(db, _owner(), "business-a", "branch-a", OrderCreate(order_type="QUICK"))
    payload = OrderItemsCreate(
        items=[OrderItemCreate(product_id="product-a", quantity=2)],
        expected_version=1,
        idempotency_key="same-key-different-order",
    )
    first = OrderService.add_items(db, _owner(), "business-a", "branch-a", first_order.id, payload)
    second = OrderService.add_items(db, _owner(), "business-a", "branch-a", second_order.id, payload)
    assert first.id != second.id
    assert all(item.quantity == 2 for item in (first.items + second.items))

    OrderService.checkout(
        db,
        _owner(),
        "business-a",
        "branch-a",
        first.id,
        OrderCheckoutRequest(
            payment={"cash_amount": "236.00", "payment_method": "CASH"},
            idempotency_key="checkout-after-items",
        ),
    )
    recovered = OrderService.add_items(db, _owner(), "business-a", "branch-a", first.id, payload)
    assert recovered.status == "COMPLETED"
    assert [(item.product_id, item.quantity) for item in recovered.items] == [("product-a", 2)]
    assert OrderService.get(db, _owner(), "business-a", "branch-a", first.id).status == "COMPLETED"
    assert _error(lambda: OrderService.add_items(
        db,
        _owner(),
        "business-a",
        "branch-a",
        first.id,
        OrderItemsCreate(items=[OrderItemCreate(product_id="product-a", quantity=1)], idempotency_key="new-after-final"),
    )) == "ORDER_NOT_MODIFIABLE"


def test_add_items_authorization_tenant_branch_product_and_read_contract(db):
    order = OrderService.create(db, _owner(), "business-a", "branch-a", OrderCreate(order_type="QUICK"))
    limited = PrincipalContext(
        principal_id="owner-a", actor_type=ActorType.OWNER, business_id="business-a", user_id="owner-a", role="owner",
        permissions=frozenset({"orders.view"}), capabilities=frozenset({"orders"}),
    )
    payload = OrderItemsCreate(items=[OrderItemCreate(product_id="product-a", quantity=1)], idempotency_key="auth-key")
    assert _error(lambda: OrderService.add_items(db, limited, "business-a", "branch-a", order.id, payload)) == "PERMISSION_DENIED"
    assert _error(lambda: OrderService.add_items(db, _owner(), "business-b", "branch-a", order.id, payload)) == "BUSINESS_ACCESS_DENIED"

    branch_limited = PrincipalContext(
        principal_id="worker-a", actor_type=ActorType.WORKER, business_id="business-a", staff_id="worker-a", branch_id="branch-a",
        role="cashier", permissions=frozenset({"orders.modify"}), capabilities=frozenset({"orders"}),
    )
    assert _error(lambda: OrderService.add_items(db, branch_limited, "business-a", "branch-b", order.id, payload)) == "BRANCH_ACCESS_DENIED"
    assert _error(lambda: OrderService.add_items(
        db,
        _owner(),
        "business-a",
        "branch-a",
        order.id,
        OrderItemsCreate(items=[OrderItemCreate(product_id="missing", quantity=1)]),
    )) == "PRODUCT_NOT_FOUND"

    added = OrderService.add_items(db, _owner(), "business-a", "branch-a", order.id, payload)
    read = OrderService.get(db, _owner(), "business-a", "branch-a", order.id)
    assert read.id == order.id
    assert read.version == added.version
    assert [(item.product_id, item.quantity) for item in read.items] == [("product-a", 1)]
    assert _error(lambda: OrderService.get(db, _owner(), "business-b", "branch-a", order.id)) == "BUSINESS_ACCESS_DENIED"

    other_owner = PrincipalContext(
        principal_id="owner-b", actor_type=ActorType.OWNER, business_id="business-b", user_id="owner-b", role="owner",
        permissions=frozenset({"*"}), capabilities=frozenset({"*"}),
    )
    db.add(User(id="owner-b", business_id="business-b", email="owner-b@example.com", password_hash="hash"))
    db.commit()
    other_order = OrderService.create(db, other_owner, "business-b", "branch-a", OrderCreate(order_type="QUICK"))
    other_result = OrderService.add_items(
        db,
        other_owner,
        "business-b",
        "branch-a",
        other_order.id,
        OrderItemsCreate(
            items=[OrderItemCreate(product_id="product-b", quantity=1)],
            idempotency_key="auth-key",
        ),
    )
    assert [(item.product_id, item.quantity) for item in other_result.items] == [("product-b", 1)]


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


def test_checkout_retry_recovers_same_result_and_different_key_is_rejected(db):
    order = _order_with_item(db)
    first = _checkout(db, order.id, key="retry-1")
    retry = _checkout(db, order.id, key="retry-1")
    assert _error(lambda: _checkout(db, order.id, key="different-client-key")) == "ORDER_ALREADY_FINALIZED"

    assert first.checkout.transaction_id == retry.checkout.transaction_id
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


def test_response_loss_retry_with_stale_version_recovers_one_canonical_checkout(db):
    order = _order_with_item(db)
    original_version = order.version
    payload = OrderCheckoutRequest(
        payment={"cash_amount": "118.00", "payment_method": "CASH"},
        idempotency_key="response-loss-key",
        expected_version=original_version,
    )

    first = OrderService.checkout(db, _owner(), "business-a", "branch-a", order.id, payload)
    retry = OrderService.checkout(db, _owner(), "business-a", "branch-a", order.id, payload)

    assert first.checkout.transaction_id == retry.checkout.transaction_id
    assert first.checkout.bill_number == retry.checkout.bill_number
    assert db.query(Transaction).count() == 1
    assert db.query(InventoryMovement).count() == 1
    assert db.query(StaffPayment).count() == 1
    assert db.query(OutboxEvent).filter(OutboxEvent.event_type == "transaction.created").count() == 1
    assert db.get(Product, "product-a").stock_quantity == 9


def test_checkout_key_is_bound_to_order_and_payload(db):
    first_order = _order_with_item(db)
    second_order = _order_with_item(db)
    first = _checkout(db, first_order.id, key="bound-checkout-key")

    assert _error(lambda: _checkout(db, second_order.id, key="bound-checkout-key")) == "IDEMPOTENCY_CONFLICT"
    assert db.get(Order, second_order.id).status == "ACTIVE"
    assert db.query(Transaction).count() == 1
    assert db.query(InventoryMovement).count() == 1

    changed_payment = OrderCheckoutRequest(
        payment={"upi_amount": "118.00", "payment_method": "UPI"},
        idempotency_key="bound-checkout-key",
    )
    assert _error(lambda: OrderService.checkout(
        db, _owner(), "business-a", "branch-a", first_order.id, changed_payment,
    )) == "IDEMPOTENCY_CONFLICT"
    assert first.checkout.transaction_id == db.query(Transaction).one().id


@pytest.mark.parametrize(
    ("payment", "customer_id"),
    [
        ({"cash_amount": "118.00", "payment_method": "CASH"}, None),
        ({"upi_amount": "118.00", "payment_method": "UPI"}, None),
        ({"card_amount": "118.00", "payment_method": "CARD"}, None),
        ({"other_paid_amount": "118.00", "payment_method": "OTHER"}, None),
        ({"cash_amount": "50.00", "upi_amount": "68.00", "payment_method": "SPLIT"}, None),
        ({"credit_amount": "118.00", "payment_method": "CREDIT"}, "customer-a"),
    ],
)
def test_quick_checkout_accepts_supported_exact_payment_allocations(db, payment, customer_id):
    order = OrderService.create(
        db,
        _owner(),
        "business-a",
        "branch-a",
        OrderCreate(order_type="QUICK", customer_id=customer_id),
    )
    order = OrderService.add_items(
        db,
        _owner(),
        "business-a",
        "branch-a",
        order.id,
        OrderItemsCreate(items=[OrderItemCreate(product_id="product-a", quantity=1)]),
    )

    result = OrderService.checkout(
        db,
        _owner(),
        "business-a",
        "branch-a",
        order.id,
        OrderCheckoutRequest(payment=payment, idempotency_key=f"payment-{payment['payment_method']}"),
    )

    assert result.order.status == "COMPLETED"
    assert result.checkout.payment_method.upper() == payment["payment_method"]
    assert result.checkout.change == Decimal("0")


def test_quick_checkout_rejects_invalid_split_and_over_credit_without_side_effects(db):
    split_order = _order_with_item(db)
    assert _error(lambda: OrderService.checkout(
        db,
        _owner(),
        "business-a",
        "branch-a",
        split_order.id,
        OrderCheckoutRequest(
            payment={"cash_amount": "118.00", "payment_method": "SPLIT"},
            idempotency_key="invalid-split",
        ),
    )) == "PAYMENT_INVALID"
    assert db.get(Order, split_order.id).status == "ACTIVE"

    credit_order = OrderService.create(
        db,
        _owner(),
        "business-a",
        "branch-a",
        OrderCreate(order_type="QUICK", customer_id="customer-a"),
    )
    credit_order = OrderService.add_items(
        db,
        _owner(),
        "business-a",
        "branch-a",
        credit_order.id,
        OrderItemsCreate(items=[OrderItemCreate(product_id="product-a", quantity=1)]),
    )
    assert _error(lambda: OrderService.checkout(
        db,
        _owner(),
        "business-a",
        "branch-a",
        credit_order.id,
        OrderCheckoutRequest(
            payment={"cash_amount": "100.00", "credit_amount": "100.00", "payment_method": "SPLIT"},
            idempotency_key="over-credit",
        ),
    )) == "PAYMENT_INVALID"
    assert db.get(Customer, "customer-a").balance_remaining == Decimal("0")
    assert db.get(Order, credit_order.id).status == "ACTIVE"
    assert db.query(Transaction).count() == 0


def test_credit_checkout_requires_customer_and_is_applied_exactly_once_on_retry(db):
    missing_customer_order = _order_with_item(db)
    assert _error(lambda: OrderService.checkout(
        db,
        _owner(),
        "business-a",
        "branch-a",
        missing_customer_order.id,
        OrderCheckoutRequest(
            payment={"credit_amount": "118.00", "payment_method": "CREDIT"},
            idempotency_key="credit-customer-required",
        ),
    )) == "CUSTOMER_REQUIRED_FOR_CREDIT"

    order = OrderService.create(
        db,
        _owner(),
        "business-a",
        "branch-a",
        OrderCreate(order_type="QUICK", customer_id="customer-a"),
    )
    order = OrderService.add_items(
        db,
        _owner(),
        "business-a",
        "branch-a",
        order.id,
        OrderItemsCreate(items=[OrderItemCreate(product_id="product-a", quantity=1)]),
    )
    payload = OrderCheckoutRequest(
        payment={"cash_amount": "100.00", "credit_amount": "18.00", "payment_method": "SPLIT"},
        idempotency_key="credit-once",
        expected_version=order.version,
    )
    first = OrderService.checkout(db, _owner(), "business-a", "branch-a", order.id, payload)
    retry = OrderService.checkout(db, _owner(), "business-a", "branch-a", order.id, payload)

    assert first.checkout.transaction_id == retry.checkout.transaction_id
    assert db.get(Customer, "customer-a").balance_remaining == Decimal("18.00")
    assert db.query(Transaction).count() == 1
    assert db.query(InventoryMovement).count() == 1
    assert db.query(StaffPayment).count() == 1
    assert db.query(OutboxEvent).filter(OutboxEvent.event_type == "customer.credit_changed").count() == 1


def test_checkout_schema_rejects_client_totals_and_checkout_requires_billing_permission(db):
    with pytest.raises(ValidationError):
        OrderCheckoutRequest(payment={"cash_amount": "118.00"}, total="1.00")

    order = _order_with_item(db)
    limited = PrincipalContext(
        principal_id="owner-a",
        actor_type=ActorType.OWNER,
        business_id="business-a",
        user_id="owner-a",
        role="owner",
        permissions=frozenset({"orders.create"}),
        capabilities=frozenset({"orders", "billing"}),
    )
    assert _error(lambda: OrderService.checkout(
        db,
        limited,
        "business-a",
        "branch-a",
        order.id,
        OrderCheckoutRequest(payment={"cash_amount": "118.00", "payment_method": "CASH"}, idempotency_key="blocked"),
    )) == "PERMISSION_DENIED"


def test_previous_balance_is_settled_in_current_payable_and_response_is_canonical(db):
    customer = db.get(Customer, "customer-a")
    customer.balance_remaining = Decimal("50.00")
    db.commit()
    order = OrderService.create(
        db,
        _owner(),
        "business-a",
        "branch-a",
        OrderCreate(order_type="QUICK", customer_id=customer.id),
    )
    order = OrderService.add_items(
        db,
        _owner(),
        "business-a",
        "branch-a",
        order.id,
        OrderItemsCreate(items=[OrderItemCreate(product_id="product-a", quantity=1)]),
    )

    result = OrderService.checkout(
        db,
        _owner(),
        "business-a",
        "branch-a",
        order.id,
        OrderCheckoutRequest(
            payment={"cash_amount": "168.00", "payment_method": "CASH"},
            idempotency_key="previous-balance-settlement",
        ),
    )

    assert result.checkout.order_id == order.id
    assert result.checkout.transaction_id == result.order.transaction_id
    assert result.checkout.bill_number and result.checkout.bill_number.startswith("INV-")
    assert result.checkout.previous_balance == Decimal("50.00")
    assert result.checkout.payable == Decimal("168.00")
    assert result.checkout.items[0].gst_percentage == Decimal("18.00")
    assert result.checkout.items[0].tax == Decimal("18.00")
    assert db.get(Customer, "customer-a").balance_remaining == Decimal("0.00")
