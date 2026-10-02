from decimal import Decimal
import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from auth.errors import ApiError
from auth.principal import ActorType, PrincipalContext
from database.database import Base
from models.business_model import Business
from models.inventory_movement_model import InventoryMovement
from models.kot_model import KitchenOrderTicket
from models.order_model import Order
from models.outbox_model import OutboxEvent
from models.product_model import Product
from models.staff_billing_model import StaffProfile
from models.table_management_model import RestaurantTable, TableSession
from models.transaction_model import Transaction
from models.user_model import User
from schemas.order_schema import OrderCheckoutRequest, OrderItemCreate, OrderItemsCreate
from schemas.kot_schema import KOTCreateRequest
from schemas.table_management_schema import (
    RestaurantTableCreate,
    TableSessionAttachTableRequest,
    TableSessionBillRequest,
    TableSessionCancelRequest,
    TableSessionCreate,
    TableSessionMoveRequest,
    TableSessionUpdate,
)
from services.order_service import OrderService
from services.kot_service import KotService
from services.staff_billing_service import StaffBillingService
from services.table_management_service import TableManagementService


TABLE_PERMISSIONS = {
    "tables.view": True, "tables.create": True, "tables.update": True,
    "tables.open": True, "tables.close": True, "tables.move": True,
    "tables.merge": True, "create_bill": True,
}


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    cafe = Business(id="cafe-a", name="Pilot Cafe", business_type="Restaurant / Cafe")
    retail = Business(id="retail-b", name="Retail", business_type="Retail")
    owner = User(id="owner-a", business_id=cafe.id, email="owner@example.com", password_hash="hash")
    worker = StaffProfile(
        id="worker-a", business_id=cafe.id, branch_id="branch-a", staff_name="Manager", role="cashier",
        permissions_json=json.dumps(TABLE_PERMISSIONS), allowed_apps='["staff_billing_app"]',
        status="active", created_by=owner.id,
    )
    limited_worker = StaffProfile(
        id="worker-limited", business_id=cafe.id, branch_id="branch-a", staff_name="Cashier", role="cashier",
        permissions_json='{"create_bill": true}', allowed_apps='["staff_billing_app"]', status="active", created_by=owner.id,
    )
    coffee = Product(id="coffee", business_id=cafe.id, name="Coffee", price=Decimal("50.00"), gst_percentage=Decimal("0.00"), stock_quantity=20, in_stock=True, is_stockless=False)
    sandwich = Product(id="sandwich", business_id=cafe.id, name="Sandwich", price=Decimal("100.00"), gst_percentage=Decimal("0.00"), stock_quantity=20, in_stock=True, is_stockless=False)
    session.add_all([cafe, retail, owner, worker, limited_worker, coffee, sandwich])
    session.commit()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _owner(business_id="cafe-a"):
    return PrincipalContext(
        principal_id="owner-a", actor_type=ActorType.OWNER, business_id=business_id, role="owner", user_id="owner-a",
        permissions=frozenset({"*"}), capabilities=frozenset({"*"}),
    )


def _worker(db, worker_id="worker-a"):
    return StaffBillingService._principal_for_staff(db, db.get(StaffProfile, worker_id))


def _error(callable_):
    with pytest.raises(ApiError) as exc:
        callable_()
    return exc.value.code


def _table(db, name="T1", principal=None):
    return TableManagementService.create_table(
        db, principal or _owner(), "cafe-a", "branch-a", RestaurantTableCreate(name=name, capacity=4),
    )


def _open(db, table_id, principal=None, guests=3):
    return TableManagementService.open_session(
        db, principal or _owner(), "cafe-a", "branch-a", table_id, TableSessionCreate(guest_count=guests),
    )


def test_admin_and_authorized_worker_create_tables_but_unauthorized_worker_cannot(db):
    admin = _table(db, "T1")
    worker = _table(db, "T2", _worker(db))

    assert admin.state == worker.state == "AVAILABLE"
    assert _error(lambda: _table(db, "T3", _worker(db, "worker-limited"))) == "PERMISSION_DENIED"


def test_retail_tms_and_cross_branch_access_are_rejected(db):
    assert _error(lambda: TableManagementService.create_table(
        db, _owner("retail-b"), "retail-b", "branch-a", RestaurantTableCreate(name="R1", capacity=2),
    )) == "CAPABILITY_NOT_AVAILABLE"
    table = _table(db)
    wrong_branch_worker = PrincipalContext(
        principal_id="worker-a", actor_type=ActorType.WORKER, business_id="cafe-a", role="cashier", staff_id="worker-a",
        branch_id="branch-b", permissions=frozenset(TABLE_PERMISSIONS), capabilities=frozenset({"orders", "table_management", "billing"}),
    )
    assert _error(lambda: TableManagementService.open_session(
        db, wrong_branch_worker, "cafe-a", "branch-a", table.id, TableSessionCreate(guest_count=2),
    )) == "BRANCH_ACCESS_DENIED"
    foreign_table = RestaurantTable(id="retail-table", business_id="retail-b", branch_id="branch-a", name="R1", capacity=2)
    db.add(foreign_table)
    db.commit()
    assert _error(lambda: TableManagementService.get_table(
        db, _owner(), "cafe-a", "branch-a", foreign_table.id,
    )) == "TABLE_NOT_FOUND"


def test_table_list_and_open_session_provide_occupancy_and_dine_in_order(db):
    table = _table(db)
    assert TableManagementService.list_tables(db, _owner(), "cafe-a", "branch-a")[0].state == "AVAILABLE"
    opened = _open(db, table.id)
    active = TableManagementService.active_session(db, _owner(), "cafe-a", "branch-a", table.id)

    assert opened.session.status == active.status == "OPEN"
    assert opened.order.order_type == "DINE_IN"
    assert opened.order.table_session_id == opened.session.id
    listed = TableManagementService.list_tables(db, _owner(), "cafe-a", "branch-a")[0]
    assert listed.state == "OCCUPIED"
    assert listed.active_session.order_id == opened.order.id
    assert listed.active_session.order_status == "ACTIVE"
    assert listed.active_session.order_version == opened.order.version
    assert db.query(OutboxEvent).filter(OutboxEvent.event_type == "table.session_opened").count() == 1
    assert db.query(OutboxEvent).filter(OutboxEvent.event_type == "order.created").count() == 1
    assert _error(lambda: _open(db, table.id)) == "TABLE_ALREADY_OCCUPIED"


def test_open_session_idempotency_recovers_response_loss_and_rejects_changed_intent(db):
    table = _table(db)
    payload = TableSessionCreate(guest_count=3, notes="Window", idempotency_key="open-response-loss")
    first = TableManagementService.open_session(db, _owner(), "cafe-a", "branch-a", table.id, payload)
    db.expunge_all()
    retry = TableManagementService.open_session(db, _owner(), "cafe-a", "branch-a", table.id, payload)

    assert first.session.id == retry.session.id
    assert first.order.id == retry.order.id
    assert db.query(TableSession).count() == 1
    assert db.query(Order).filter(Order.table_session_id == first.session.id).count() == 1
    assert db.query(OutboxEvent).filter(OutboxEvent.event_type == "table.session_opened").count() == 1
    assert _error(lambda: TableManagementService.open_session(
        db,
        _owner(),
        "cafe-a",
        "branch-a",
        table.id,
        TableSessionCreate(guest_count=4, notes="Window", idempotency_key="open-response-loss"),
    )) == "IDEMPOTENCY_CONFLICT"


def test_existing_order_api_adds_items_and_session_versioning_and_bill_request_work(db):
    opened = _open(db, _table(db).id)
    order = OrderService.add_items(
        db, _owner(), "cafe-a", "branch-a", opened.order.id,
        OrderItemsCreate(items=[OrderItemCreate(product_id="coffee", quantity=2)]),
    )
    updated = TableManagementService.update_session(
        db, _owner(), "cafe-a", "branch-a", opened.session.id,
        TableSessionUpdate(guest_count=4, expected_version=opened.session.version),
    )
    assert order.items[0].quantity == 2
    assert updated.guest_count == 4
    assert _error(lambda: TableManagementService.update_session(
        db, _owner(), "cafe-a", "branch-a", opened.session.id,
        TableSessionUpdate(guest_count=5, expected_version=opened.session.version),
    )) == "VERSION_CONFLICT"
    requested = TableManagementService.request_bill(
        db, _owner(), "cafe-a", "branch-a", opened.session.id,
        TableSessionBillRequest(expected_version=updated.version),
    )
    assert requested.status == "BILL_REQUESTED"

    customer_updated = TableManagementService.update_session(
        db,
        _owner(),
        "cafe-a",
        "branch-a",
        opened.session.id,
        TableSessionUpdate(customer_id=None, expected_version=requested.version),
    )
    assert customer_updated.order.version == order.version + 1


def test_successful_checkout_closes_session_and_makes_table_available(db):
    table = _table(db)
    opened = _open(db, table.id)
    OrderService.add_items(db, _owner(), "cafe-a", "branch-a", opened.order.id, OrderItemsCreate(items=[OrderItemCreate(product_id="coffee", quantity=1)]))
    request = OrderCheckoutRequest(payment={"cash_amount": "50.00"}, idempotency_key="table-checkout-retry")
    result = OrderService.checkout(
        db, _owner(), "cafe-a", "branch-a", opened.order.id,
        request,
    )
    retry = OrderService.checkout(db, _owner(), "cafe-a", "branch-a", opened.order.id, request)

    assert result.order.status == "COMPLETED"
    assert retry.checkout.transaction_id == result.checkout.transaction_id
    assert db.get(TableSession, opened.session.id).status == "CLOSED"
    assert TableManagementService.get_table(db, _owner(), "cafe-a", "branch-a", table.id).state == "AVAILABLE"
    assert db.query(Transaction).filter(Transaction.order_id == opened.order.id).count() == 1
    assert db.query(OutboxEvent).filter(OutboxEvent.event_type == "table.session_closed").count() == 1


def test_failed_checkout_keeps_session_occupied_and_open(db):
    table = _table(db)
    opened = _open(db, table.id)
    OrderService.add_items(db, _owner(), "cafe-a", "branch-a", opened.order.id, OrderItemsCreate(items=[OrderItemCreate(product_id="coffee", quantity=1)]))
    db.get(Product, "coffee").stock_quantity = 0
    db.get(Product, "coffee").in_stock = False
    db.commit()

    assert _error(lambda: OrderService.checkout(
        db, _owner(), "cafe-a", "branch-a", opened.order.id, OrderCheckoutRequest(payment={"cash_amount": "50.00"}),
    )) == "INSUFFICIENT_STOCK"
    assert db.get(TableSession, opened.session.id).status == "OPEN"
    assert TableManagementService.get_table(db, _owner(), "cafe-a", "branch-a", table.id).state == "OCCUPIED"


def test_empty_session_cancel_and_move_and_merge_operations(db):
    source = _table(db, "T1")
    destination = _table(db, "T2")
    extra = _table(db, "T3")
    opened = _open(db, source.id)
    moved = TableManagementService.move_session(
        db, _owner(), "cafe-a", "branch-a", opened.session.id,
        TableSessionMoveRequest(destination_table_id=destination.id, expected_version=opened.session.version),
    )
    assert moved.primary_table_id == destination.id
    assert TableManagementService.get_table(db, _owner(), "cafe-a", "branch-a", source.id).state == "AVAILABLE"
    assert TableManagementService.get_table(db, _owner(), "cafe-a", "branch-a", destination.id).state == "OCCUPIED"
    attached = TableManagementService.attach_table(
        db, _owner(), "cafe-a", "branch-a", opened.session.id,
        TableSessionAttachTableRequest(table_id=extra.id, expected_version=moved.version),
    )
    assert {row.table_id for row in attached.tables} == {destination.id, extra.id}
    assert _error(lambda: TableManagementService.attach_table(
        db, _owner(), "cafe-a", "branch-a", opened.session.id, TableSessionAttachTableRequest(table_id=extra.id),
    )) == "TABLE_ALREADY_ATTACHED"
    assert _error(lambda: TableManagementService.move_session(
        db, _owner(), "cafe-a", "branch-a", opened.session.id, TableSessionMoveRequest(destination_table_id=extra.id),
    )) == "DESTINATION_TABLE_OCCUPIED"
    detached = TableManagementService.detach_table(
        db, _owner(), "cafe-a", "branch-a", opened.session.id, extra.id, attached.version,
    )
    assert {row.table_id for row in detached.tables} == {destination.id}
    assert TableManagementService.get_table(db, _owner(), "cafe-a", "branch-a", extra.id).state == "AVAILABLE"

    empty = _open(db, source.id)
    cancelled = TableManagementService.cancel_session(
        db, _owner(), "cafe-a", "branch-a", empty.session.id, TableSessionCancelRequest(reason="No guests"),
    )
    assert cancelled.status == "CANCELLED"
    assert TableManagementService.get_table(db, _owner(), "cafe-a", "branch-a", source.id).state == "AVAILABLE"


def test_move_to_occupied_target_leaves_original_session_untouched(db):
    source = _table(db, "T1")
    occupied_target = _table(db, "T2")
    original = _open(db, source.id)
    target_session = _open(db, occupied_target.id)

    assert _error(lambda: TableManagementService.move_session(
        db,
        _owner(),
        "cafe-a",
        "branch-a",
        original.session.id,
        TableSessionMoveRequest(destination_table_id=occupied_target.id, expected_version=original.session.version),
    )) == "DESTINATION_TABLE_OCCUPIED"
    assert TableManagementService.active_session(db, _owner(), "cafe-a", "branch-a", source.id).id == original.session.id
    assert TableManagementService.active_session(db, _owner(), "cafe-a", "branch-a", occupied_target.id).id == target_session.session.id


def test_multi_table_checkout_releases_every_link_and_kot_snapshots_table_names(db):
    source = _table(db, "T1")
    destination = _table(db, "T4")
    extra = _table(db, "T2")
    opened = _open(db, source.id)
    first_items = OrderService.add_items(
        db,
        _owner(),
        "cafe-a",
        "branch-a",
        opened.order.id,
        OrderItemsCreate(items=[OrderItemCreate(product_id="coffee", quantity=1)]),
    )
    kot_one = KotService.create(
        db,
        _owner(),
        "cafe-a",
        "branch-a",
        opened.order.id,
        KOTCreateRequest(idempotency_key="table-kot-one", expected_order_version=first_items.version),
    )
    moved = TableManagementService.move_session(
        db,
        _owner(),
        "cafe-a",
        "branch-a",
        opened.session.id,
        TableSessionMoveRequest(destination_table_id=destination.id, expected_version=opened.session.version),
    )
    attached = TableManagementService.attach_table(
        db,
        _owner(),
        "cafe-a",
        "branch-a",
        opened.session.id,
        TableSessionAttachTableRequest(table_id=extra.id, expected_version=moved.version),
    )
    second_items = OrderService.add_items(
        db,
        _owner(),
        "cafe-a",
        "branch-a",
        opened.order.id,
        OrderItemsCreate(items=[OrderItemCreate(product_id="coffee", quantity=1)], expected_version=kot_one.order_version),
    )
    kot_two = KotService.create(
        db,
        _owner(),
        "cafe-a",
        "branch-a",
        opened.order.id,
        KOTCreateRequest(idempotency_key="table-kot-two", expected_order_version=second_items.version),
    )

    assert KotService.get(db, _owner(), "cafe-a", "branch-a", kot_one.id).table.table_names == ["T1"]
    assert kot_two.table.table_names == ["T4", "T2"]
    assert db.query(KitchenOrderTicket).filter(KitchenOrderTicket.order_id == opened.order.id).count() == 2

    OrderService.checkout(
        db,
        _owner(),
        "cafe-a",
        "branch-a",
        opened.order.id,
        OrderCheckoutRequest(payment={"cash_amount": "100.00"}, idempotency_key="multi-table-checkout"),
    )
    assert {TableManagementService.get_table(db, _owner(), "cafe-a", "branch-a", table.id).state for table in (destination, extra)} == {"AVAILABLE"}
    assert attached.order.id == opened.order.id


def test_cafe_pilot_workflow_end_to_end(db):
    table = _table(db, "T1")
    opened = _open(db, table.id, guests=3)
    assert opened.session.guest_count == 3
    assert opened.order.order_type == "DINE_IN"

    with_coffee = OrderService.add_items(
        db, _owner(), "cafe-a", "branch-a", opened.order.id,
        OrderItemsCreate(items=[OrderItemCreate(product_id="coffee", quantity=2)]),
    )
    OrderService.add_items(
        db, _owner(), "cafe-a", "branch-a", opened.order.id,
        OrderItemsCreate(items=[OrderItemCreate(product_id="sandwich", quantity=1),], expected_version=with_coffee.version),
    )
    active = TableManagementService.active_session(db, _owner(), "cafe-a", "branch-a", table.id)
    assert active.order.id == opened.order.id
    assert len(active.order.items) == 2
    TableManagementService.request_bill(db, _owner(), "cafe-a", "branch-a", opened.session.id, TableSessionBillRequest(expected_version=active.version))
    checkout = OrderService.checkout(
        db, _owner(), "cafe-a", "branch-a", opened.order.id,
        OrderCheckoutRequest(payment={"cash_amount": "200.00"}),
    )

    assert checkout.order.status == "COMPLETED"
    assert db.query(Transaction).filter(Transaction.order_id == opened.order.id).count() == 1
    assert db.get(TableSession, opened.session.id).status == "CLOSED"
    assert TableManagementService.get_table(db, _owner(), "cafe-a", "branch-a", table.id).state == "AVAILABLE"
    assert db.get(Product, "coffee").stock_quantity == 18
    assert db.get(Product, "sandwich").stock_quantity == 19
    assert db.query(InventoryMovement).count() == 2
