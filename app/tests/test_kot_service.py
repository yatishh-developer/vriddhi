import json
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from auth.errors import ApiError
from auth.principal import ActorType, PrincipalContext
from database.database import Base
from models.business_model import Business
from models.inventory_movement_model import InventoryMovement
from models.kot_model import KitchenKotCancellation, KitchenOrderTicket, KitchenOrderTicketItem
from models.outbox_model import OutboxEvent
from models.product_model import Product
from models.staff_billing_model import StaffProfile
from models.table_management_model import TableSession
from models.transaction_model import Transaction
from models.user_model import User
from schemas.kot_schema import KOTCreateRequest, KOTStatusUpdateRequest, OrderItemCancelQuantityRequest
from schemas.order_schema import OrderCheckoutRequest, OrderCreate, OrderItemCreate, OrderItemUpdate, OrderItemsCreate
from schemas.table_management_schema import RestaurantTableCreate, TableSessionBillRequest, TableSessionCreate
from services.kot_service import KotService
from services.order_service import OrderService
from services.staff_billing_service import StaffBillingService
from services.table_management_service import TableManagementService


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    cafe = Business(id="cafe", name="Cafe", business_type="Restaurant / Cafe")
    retail = Business(id="retail", name="Retail", business_type="Retail")
    owner = User(id="owner", business_id="cafe", email="owner@example.com", password_hash="hash")
    worker = StaffProfile(
        id="worker", business_id="cafe", branch_id="main", staff_name="Chef", role="chef",
        permissions_json=json.dumps({"create_kot": True, "kot.view": True, "kot.prepare": True, "kot.mark_ready": True, "kot.serve": True, "kot.cancel": True, "create_bill": True}),
        allowed_apps='["staff_billing_app"]', status="active", created_by="owner",
    )
    blocked = StaffProfile(
        id="blocked", business_id="cafe", branch_id="main", staff_name="No KOT", role="cashier",
        permissions_json='{"create_kot": false}', allowed_apps='["staff_billing_app"]', status="active", created_by="owner",
    )
    products = [
        Product(id="coffee", business_id="cafe", name="Coffee", price=Decimal("50.00"), gst_percentage=Decimal("0.00"), stock_quantity=30, in_stock=True, is_stockless=False),
        Product(id="sandwich", business_id="cafe", name="Sandwich", price=Decimal("100.00"), gst_percentage=Decimal("0.00"), stock_quantity=30, in_stock=True, is_stockless=False),
        Product(id="fries", business_id="cafe", name="Fries", price=Decimal("30.00"), gst_percentage=Decimal("0.00"), stock_quantity=30, in_stock=True, is_stockless=False),
    ]
    session.add_all([cafe, retail, owner, worker, blocked, *products])
    session.commit()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _owner(business_id="cafe"):
    return PrincipalContext(principal_id="owner", actor_type=ActorType.OWNER, business_id=business_id, role="owner", user_id="owner", permissions=frozenset({"*"}), capabilities=frozenset({"*"}))


def _worker(db, identifier="worker"):
    return StaffBillingService._principal_for_staff(db, db.get(StaffProfile, identifier))


def _error(callable_):
    with pytest.raises(ApiError) as exc:
        callable_()
    return exc.value.code


def _quick_order(db):
    order = OrderService.create(db, _owner(), "cafe", "main", OrderCreate(order_type="QUICK"))
    return OrderService.add_items(db, _owner(), "cafe", "main", order.id, OrderItemsCreate(items=[OrderItemCreate(product_id="coffee", quantity=2), OrderItemCreate(product_id="sandwich", quantity=1)]))


def test_admin_and_worker_create_kots_and_reject_unauthorized_or_retail(db):
    owner_order = _quick_order(db)
    first = KotService.create(db, _owner(), "cafe", "main", owner_order.id, KOTCreateRequest())
    worker_order = OrderService.create(db, _worker(db), "cafe", "main", OrderCreate(order_type="TAKEAWAY"))
    worker_order = OrderService.add_items(db, _worker(db), "cafe", "main", worker_order.id, OrderItemsCreate(items=[OrderItemCreate(product_id="fries", quantity=1)]))
    second = KotService.create(db, _worker(db), "cafe", "main", worker_order.id, KOTCreateRequest())

    assert first.kot_number == "KOT-000001"
    assert first.order_status == "ACTIVE" and first.order_version == owner_order.version + 1
    assert second.kot_number == "KOT-000002"
    assert db.query(OutboxEvent).filter(OutboxEvent.event_type == "kot.created").count() == 2
    blocked_order = OrderService.create(db, _owner(), "cafe", "main", OrderCreate())
    blocked_order = OrderService.add_items(db, _owner(), "cafe", "main", blocked_order.id, OrderItemsCreate(items=[OrderItemCreate(product_id="fries", quantity=1)]))
    assert _error(lambda: KotService.create(db, _worker(db, "blocked"), "cafe", "main", blocked_order.id, KOTCreateRequest())) == "PERMISSION_DENIED"
    assert _error(lambda: KotService.create(db, _owner(), "retail", "main", blocked_order.id, KOTCreateRequest())) == "BUSINESS_ACCESS_DENIED"
    assert _error(lambda: KotService.create(db, _worker(db), "cafe", "other-branch", blocked_order.id, KOTCreateRequest())) == "BRANCH_ACCESS_DENIED"
    assert _error(lambda: KotService.create(db, _owner("retail"), "retail", "main", "missing", KOTCreateRequest())) == "CAPABILITY_NOT_AVAILABLE"


def test_multiple_kots_send_only_new_quantities_and_history_and_list_work(db):
    order = _quick_order(db)
    first = KotService.create(db, _owner(), "cafe", "main", order.id, KOTCreateRequest())
    assert {(item.product_name_snapshot, item.quantity) for item in first.items} == {("Coffee", 2), ("Sandwich", 1)}
    added = OrderService.add_items(db, _owner(), "cafe", "main", order.id, OrderItemsCreate(items=[OrderItemCreate(product_id="coffee", quantity=1), OrderItemCreate(product_id="fries", quantity=2)], expected_version=order.version + 1))
    second = KotService.create(db, _owner(), "cafe", "main", order.id, KOTCreateRequest(expected_order_version=added.version))

    assert {(item.product_name_snapshot, item.quantity) for item in second.items} == {("Coffee", 1), ("Fries", 2)}
    assert all(item.product_name_snapshot != "Sandwich" for item in second.items)
    assert {(item.product_name_snapshot, item.quantity) for item in second.print_payload.items} == {("Coffee", 1), ("Fries", 2)}
    assert _error(lambda: KotService.create(db, _owner(), "cafe", "main", order.id, KOTCreateRequest())) == "NO_UNSENT_KOT_ITEMS"
    history = KotService.list_for_order(db, _owner(), "cafe", "main", order.id)
    assert len(history) == 2
    assert KotService.get(db, _owner(), "cafe", "main", second.id).id == second.id
    assert KotService.list(db, _owner(), "cafe", "main", status=None, order_id=order.id, table_session_id=None, created_from=None, created_to=None, page=1, page_size=25).total == 2


def test_kot_idempotency_retry_and_kot_creation_have_no_financial_side_effects(db):
    order = _quick_order(db)
    request = KOTCreateRequest(idempotency_key="thermal-retry", notes="No plastic", expected_order_version=order.version)
    first = KotService.create(db, _owner(), "cafe", "main", order.id, request)
    # Simulate a process/repository restart after the commit but before the
    # client receives the response.
    db.expunge_all()
    retry = KotService.create(db, _owner(), "cafe", "main", order.id, request)

    assert first.id == retry.id and first.kot_number == retry.kot_number
    assert db.query(KitchenOrderTicket).count() == 1
    assert db.query(KitchenOrderTicketItem).count() == 2
    assert db.query(OutboxEvent).filter(OutboxEvent.event_type == "kot.created").count() == 1
    assert db.get(Product, "coffee").stock_quantity == 30
    assert db.query(Transaction).count() == 0
    assert db.query(InventoryMovement).count() == 0
    assert {item.kot_sent_quantity for item in db.query(__import__("models.order_model", fromlist=["OrderItem"]).OrderItem).all()} == {1, 2}
    assert _error(lambda: KotService.create(
        db,
        _owner(),
        "cafe",
        "main",
        order.id,
        KOTCreateRequest(idempotency_key="thermal-retry", notes="Changed kitchen note", expected_order_version=order.version),
    )) == "IDEMPOTENCY_CONFLICT"


def test_lifecycle_and_sent_item_edit_cancellation_rules(db):
    order = _quick_order(db)
    kot = KotService.create(db, _owner(), "cafe", "main", order.id, KOTCreateRequest())
    preparing = KotService.update_status(db, _worker(db), "cafe", "main", kot.id, KOTStatusUpdateRequest(status="PREPARING", expected_version=kot.version))
    ready = KotService.update_status(db, _worker(db), "cafe", "main", kot.id, KOTStatusUpdateRequest(status="READY", expected_version=preparing.version))
    served = KotService.update_status(db, _worker(db), "cafe", "main", kot.id, KOTStatusUpdateRequest(status="SERVED", expected_version=ready.version))
    assert served.status == "SERVED"
    event_types = {row.event_type for row in db.query(OutboxEvent).all()}
    assert {"kot.created", "kot.preparing", "kot.ready"}.issubset(event_types)
    assert db.query(OutboxEvent).filter(OutboxEvent.event_type == "kot.served", OutboxEvent.aggregate_id == kot.id).count() == 1
    assert _error(lambda: KotService.update_status(db, _worker(db), "cafe", "main", kot.id, KOTStatusUpdateRequest(status="PREPARING"))) == "KOT_INVALID_TRANSITION"

    coffee_item = next(item for item in OrderService.get(db, _owner(), "cafe", "main", order.id).items if item.product_id == "coffee")
    assert _error(lambda: OrderService.update_item(db, _owner(), "cafe", "main", order.id, coffee_item.id, OrderItemUpdate(quantity=1))) == "KOT_QUANTITY_ALREADY_SENT"
    cancellation = KotService.cancel_order_item_quantity(db, _worker(db), "cafe", "main", order.id, coffee_item.id, OrderItemCancelQuantityRequest(quantity=1, reason="Changed mind"))
    assert cancellation.quantity == 1
    assert db.query(KitchenKotCancellation).count() == 1
    # Only the unsent portion may be reduced normally; the historic KOT item
    # remains immutable and auditable.
    reduced = OrderService.update_item(db, _owner(), "cafe", "main", order.id, coffee_item.id, OrderItemUpdate(quantity=1))
    assert next(item.quantity for item in reduced.items if item.id == coffee_item.id) == 1
    assert db.query(KitchenOrderTicketItem).filter(KitchenOrderTicketItem.kot_id == kot.id).count() == 2
    assert _error(lambda: OrderService.update_item(db, _owner(), "cafe", "main", order.id, coffee_item.id, OrderItemUpdate(quantity=0))) == "KOT_QUANTITY_ALREADY_SENT"


def test_cafe_kot_workflow_and_cancelled_quantity_checkout(db):
    table = TableManagementService.create_table(db, _owner(), "cafe", "main", RestaurantTableCreate(name="T4", capacity=4))
    opened = TableManagementService.open_session(db, _owner(), "cafe", "main", table.id, TableSessionCreate(guest_count=3))
    initial = OrderService.add_items(db, _owner(), "cafe", "main", opened.order.id, OrderItemsCreate(items=[OrderItemCreate(product_id="coffee", quantity=2), OrderItemCreate(product_id="sandwich", quantity=1)]))
    first = KotService.create(db, _owner(), "cafe", "main", opened.order.id, KOTCreateRequest(expected_order_version=initial.version))
    assert {(item.product_name_snapshot, item.quantity) for item in first.items} == {("Coffee", 2), ("Sandwich", 1)}
    extra = OrderService.add_items(db, _owner(), "cafe", "main", opened.order.id, OrderItemsCreate(items=[OrderItemCreate(product_id="coffee", quantity=1), OrderItemCreate(product_id="fries", quantity=2)], expected_version=initial.version + 1))
    second = KotService.create(db, _owner(), "cafe", "main", opened.order.id, KOTCreateRequest(expected_order_version=extra.version))
    assert {(item.product_name_snapshot, item.quantity) for item in second.items} == {("Coffee", 1), ("Fries", 2)}
    KotService.update_status(db, _owner(), "cafe", "main", first.id, KOTStatusUpdateRequest(status="PREPARING"))
    KotService.update_status(db, _owner(), "cafe", "main", first.id, KOTStatusUpdateRequest(status="READY"))

    coffee_initial = next(item for item in OrderService.get(db, _owner(), "cafe", "main", opened.order.id).items if item.product_id == "coffee" and item.quantity == 2)
    KotService.cancel_order_item_quantity(db, _owner(), "cafe", "main", opened.order.id, coffee_initial.id, OrderItemCancelQuantityRequest(quantity=1, reason="One coffee cancelled"))
    session = db.get(TableSession, opened.session.id)
    TableManagementService.request_bill(db, _owner(), "cafe", "main", session.id, TableSessionBillRequest(expected_version=session.version))
    checkout = OrderService.checkout(db, _owner(), "cafe", "main", opened.order.id, OrderCheckoutRequest(payment={"cash_amount": "260.00"}))

    assert checkout.order.status == "COMPLETED"
    assert db.query(Transaction).filter(Transaction.order_id == opened.order.id).count() == 1
    assert db.get(Product, "coffee").stock_quantity == 28  # 2 billed (one cancelled from the first item, plus one new item)
    assert db.get(Product, "sandwich").stock_quantity == 29
    assert db.get(Product, "fries").stock_quantity == 28
    assert db.query(InventoryMovement).count() == 4
    assert db.get(TableSession, opened.session.id).status == "CLOSED"
    assert TableManagementService.get_table(db, _owner(), "cafe", "main", table.id).state == "AVAILABLE"
