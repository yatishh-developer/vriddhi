"""PostgreSQL-only checks for the F6A authoritative checkout contract.

Run after ``alembic upgrade head`` with F6A_TEST_DATABASE_URL pointed at a
disposable migrated PostgreSQL database.  SQLite cannot prove FOR UPDATE
serialization, so this test deliberately skips unless that database is given.
"""

from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
import os
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from auth.errors import ApiError
from auth.principal import ActorType, PrincipalContext
from models.business_model import Business
from models.inventory_movement_model import InventoryMovement
from models.kot_model import KitchenOrderTicket, KitchenOrderTicketItem
from models.order_model import Order, OrderItem, OrderItemMutation
from models.outbox_model import OutboxEvent
from models.product_model import Product
from models.staff_billing_model import StaffPayment
from models.table_management_model import TableSession, TableSessionTable
from models.transaction_model import Transaction
from models.user_model import User
from schemas.kot_schema import KOTCreateRequest
from schemas.order_schema import OrderCheckoutRequest, OrderCreate, OrderItemCreate, OrderItemsCreate
from schemas.table_management_schema import RestaurantTableCreate, TableSessionCreate, TableSessionMoveRequest
from services.kot_service import KotService
from services.order_service import OrderService
from services.table_management_service import TableManagementService


TEST_DATABASE_URL = os.getenv("F6A_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL or not TEST_DATABASE_URL.startswith("postgresql"),
    reason="requires a disposable PostgreSQL database in F6A_TEST_DATABASE_URL",
)


def _principal(business_id: str, user_id: str) -> PrincipalContext:
    return PrincipalContext(
        principal_id=user_id,
        actor_type=ActorType.OWNER,
        business_id=business_id,
        user_id=user_id,
        role="owner",
        permissions=frozenset({"*"}),
        capabilities=frozenset({"*"}),
    )


def test_concurrent_same_key_checkout_commits_one_authoritative_sale():
    engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    sessions = sessionmaker(bind=engine)
    suffix = uuid4().hex
    business_id = f"f6a-business-{suffix}"
    owner_id = f"f6a-owner-{suffix}"
    product_id = f"f6a-product-{suffix}"
    principal = _principal(business_id, owner_id)

    setup = sessions()
    try:
        setup.add_all([
            Business(id=business_id, name="F6A Test", business_type="Retail"),
            User(id=owner_id, business_id=business_id, email=f"{suffix}@example.test", password_hash="hash"),
            Product(
                id=product_id,
                business_id=business_id,
                name="Authoritative product",
                price=Decimal("100.00"),
                gst_percentage=Decimal("18.00"),
                stock_quantity=10,
                in_stock=True,
                is_stockless=False,
            ),
        ])
        setup.commit()
        order = OrderService.create(
            setup,
            principal,
            business_id,
            "main",
            OrderCreate(order_type="QUICK", idempotency_key=f"order-{suffix}"),
        )
        order = OrderService.add_items(
            setup,
            principal,
            business_id,
            "main",
            order.id,
            OrderItemsCreate(items=[OrderItemCreate(product_id=product_id, quantity=1)]),
        )
        order_id = order.id
    finally:
        setup.close()

    barrier = Barrier(2)
    request = OrderCheckoutRequest(
        payment={"cash_amount": "118.00", "payment_method": "CASH"},
        idempotency_key=f"checkout-{suffix}",
    )

    def checkout_once() -> str:
        session = sessions()
        try:
            barrier.wait(timeout=10)
            result = OrderService.checkout(session, principal, business_id, "main", order_id, request)
            return result.checkout.transaction_id
        finally:
            session.close()

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            transaction_ids = list(executor.map(lambda _: checkout_once(), range(2)))

        verify = sessions()
        try:
            transaction = verify.query(Transaction).filter(Transaction.order_id == order_id).one()
            assert transaction_ids == [transaction.id, transaction.id]
            assert verify.query(Transaction).filter(Transaction.order_id == order_id).count() == 1
            assert verify.query(InventoryMovement).filter(InventoryMovement.reference_id == transaction.id).count() == 1
            assert verify.query(StaffPayment).filter(StaffPayment.bill_transaction_id == transaction.id).count() == 1
            assert verify.query(OutboxEvent).filter(
                OutboxEvent.event_type == "transaction.created",
                OutboxEvent.aggregate_id == transaction.id,
            ).count() == 1
            assert verify.get(Product, product_id).stock_quantity == 9
            assert verify.get(Order, order_id).status == "COMPLETED"
        finally:
            verify.close()
    finally:
        engine.dispose()


def test_concurrent_same_key_add_items_materializes_one_cart_mutation():
    engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    sessions = sessionmaker(bind=engine)
    suffix = uuid4().hex
    business_id = f"f6a-items-business-{suffix}"
    owner_id = f"f6a-items-owner-{suffix}"
    product_id = f"f6a-items-product-{suffix}"
    principal = _principal(business_id, owner_id)

    setup = sessions()
    try:
        setup.add_all([
            Business(id=business_id, name="F6A Items Test", business_type="Retail"),
            User(id=owner_id, business_id=business_id, email=f"items-{suffix}@example.test", password_hash="hash"),
            Product(id=product_id, business_id=business_id, name="Replay-safe tea", price=Decimal("100.00"), gst_percentage=Decimal("18.00"), stock_quantity=10, in_stock=True, is_stockless=False),
        ])
        setup.commit()
        order = OrderService.create(setup, principal, business_id, "main", OrderCreate(order_type="QUICK"))
        order_id = order.id
    finally:
        setup.close()

    barrier = Barrier(2)
    request = OrderItemsCreate(
        items=[OrderItemCreate(product_id=product_id, quantity=2, notes="replay-safe")],
        expected_version=1,
        idempotency_key=f"items-{suffix}",
    )

    def add_once():
        session = sessions()
        try:
            barrier.wait(timeout=10)
            return OrderService.add_items(session, principal, business_id, "main", order_id, request)
        finally:
            session.close()

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: add_once(), range(2)))
        verify = sessions()
        try:
            assert [result.version for result in results] == [2, 2]
            assert verify.query(OrderItem).filter(OrderItem.order_id == order_id).count() == 1
            assert verify.query(OrderItem).filter(OrderItem.order_id == order_id).one().quantity == 2
            assert verify.query(OrderItemMutation).filter(OrderItemMutation.order_id == order_id).count() == 1
            assert verify.get(Order, order_id).version == 2
        finally:
            verify.close()
    finally:
        engine.dispose()


def test_concurrent_kot_keys_never_duplicate_unsent_kitchen_quantity():
    engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    sessions = sessionmaker(bind=engine)
    suffix = uuid4().hex
    business_id = f"f7a-kot-business-{suffix}"
    owner_id = f"f7a-kot-owner-{suffix}"
    product_id = f"f7a-kot-product-{suffix}"
    principal = _principal(business_id, owner_id)

    setup = sessions()
    try:
        setup.add_all([
            Business(id=business_id, name="F7A KOT Test", business_type="Restaurant / Cafe"),
            User(id=owner_id, business_id=business_id, email=f"kot-{suffix}@example.test", password_hash="hash"),
            Product(id=product_id, business_id=business_id, name="Kitchen tea", price=Decimal("100.00"), gst_percentage=Decimal("0.00"), stock_quantity=10, in_stock=True, is_stockless=False),
        ])
        setup.commit()
        order = OrderService.create(setup, principal, business_id, "main", OrderCreate(order_type="QUICK"))
        order = OrderService.add_items(
            setup,
            principal,
            business_id,
            "main",
            order.id,
            OrderItemsCreate(items=[OrderItemCreate(product_id=product_id, quantity=2)]),
        )
        order_id = order.id
        original_version = order.version
    finally:
        setup.close()

    def concurrently_create(keys: list[str]):
        barrier = Barrier(2)

        def create_once(key: str):
            session = sessions()
            try:
                barrier.wait(timeout=10)
                result = KotService.create(
                    session,
                    principal,
                    business_id,
                    "main",
                    order_id,
                    KOTCreateRequest(idempotency_key=key, expected_order_version=original_version),
                )
                return ("ok", result.id)
            except ApiError as exc:
                return ("error", exc.code)
            finally:
                session.close()

        with ThreadPoolExecutor(max_workers=2) as executor:
            return list(executor.map(create_once, keys))

    try:
        same_key_results = concurrently_create([f"same-{suffix}", f"same-{suffix}"])
        assert same_key_results[0] == same_key_results[1]

        verify = sessions()
        try:
            assert verify.query(KitchenOrderTicket).filter(KitchenOrderTicket.order_id == order_id).count() == 1
            assert verify.query(KitchenOrderTicketItem).join(KitchenOrderTicket).filter(KitchenOrderTicket.order_id == order_id).one().quantity == 2
        finally:
            verify.close()

        setup_next = sessions()
        try:
            next_order = OrderService.create(setup_next, principal, business_id, "main", OrderCreate(order_type="QUICK"))
            next_order = OrderService.add_items(
                setup_next,
                principal,
                business_id,
                "main",
                next_order.id,
                OrderItemsCreate(items=[OrderItemCreate(product_id=product_id, quantity=2)]),
            )
            order_id = next_order.id
            original_version = next_order.version
        finally:
            setup_next.close()

        different_key_results = concurrently_create([f"first-{suffix}", f"second-{suffix}"])
        assert sum(result[0] == "ok" for result in different_key_results) == 1
        assert {result[1] for result in different_key_results if result[0] == "error"} <= {"VERSION_CONFLICT", "NO_UNSENT_KOT_ITEMS"}

        verify = sessions()
        try:
            items = verify.query(KitchenOrderTicketItem).join(KitchenOrderTicket).filter(KitchenOrderTicket.order_id == order_id).all()
            assert len(items) == 1
            assert items[0].quantity == 2
        finally:
            verify.close()
    finally:
        engine.dispose()


def test_concurrent_table_open_and_dine_checkout_recovery():
    engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    sessions = sessionmaker(bind=engine)
    suffix = uuid4().hex
    business_id = f"f8a-tms-business-{suffix}"
    owner_id = f"f8a-tms-owner-{suffix}"
    product_id = f"f8a-tms-product-{suffix}"
    principal = _principal(business_id, owner_id)

    setup = sessions()
    try:
        setup.add_all([
            Business(id=business_id, name="F8A TMS Test", business_type="Restaurant / Cafe"),
            User(id=owner_id, business_id=business_id, email=f"tms-{suffix}@example.test", password_hash="hash"),
            Product(id=product_id, business_id=business_id, name="Table coffee", price=Decimal("50.00"), gst_percentage=Decimal("0.00"), stock_quantity=10, in_stock=True, is_stockless=False),
        ])
        setup.commit()
        table_one = TableManagementService.create_table(setup, principal, business_id, "main", RestaurantTableCreate(name="T1", capacity=4))
        table_two = TableManagementService.create_table(setup, principal, business_id, "main", RestaurantTableCreate(name="T2", capacity=4))
        table_three = TableManagementService.create_table(setup, principal, business_id, "main", RestaurantTableCreate(name="T3", capacity=4))
        table_four = TableManagementService.create_table(setup, principal, business_id, "main", RestaurantTableCreate(name="T4", capacity=4))
    finally:
        setup.close()

    def concurrently_open(table_id: str, keys: list[str]):
        barrier = Barrier(2)

        def open_once(key: str):
            session = sessions()
            try:
                barrier.wait(timeout=10)
                result = TableManagementService.open_session(
                    session,
                    principal,
                    business_id,
                    "main",
                    table_id,
                    TableSessionCreate(guest_count=2, idempotency_key=key),
                )
                return ("ok", result.session.id, result.order.id)
            except ApiError as exc:
                return ("error", exc.code)
            finally:
                session.close()

        with ThreadPoolExecutor(max_workers=2) as executor:
            return list(executor.map(open_once, keys))

    try:
        same_key = concurrently_open(table_one.id, [f"open-same-{suffix}", f"open-same-{suffix}"])
        assert same_key[0] == same_key[1]
        session_id, order_id = same_key[0][1:]

        different_keys = concurrently_open(table_two.id, [f"open-a-{suffix}", f"open-b-{suffix}"])
        assert sum(result[0] == "ok" for result in different_keys) == 1
        assert {result[1] for result in different_keys if result[0] == "error"} == {"TABLE_ALREADY_OCCUPIED"}

        verify = sessions()
        try:
            assert verify.query(TableSession).filter(TableSession.id == session_id).count() == 1
            assert verify.query(TableSessionTable).filter(TableSessionTable.session_id == session_id, TableSessionTable.is_active == True).count() == 1
            assert verify.query(Order).filter(Order.id == order_id, Order.table_session_id == session_id).count() == 1
        finally:
            verify.close()

        working = sessions()
        try:
            order = OrderService.add_items(
                working,
                principal,
                business_id,
                "main",
                order_id,
                OrderItemsCreate(items=[OrderItemCreate(product_id=product_id, quantity=1)]),
            )
            checkout_request = OrderCheckoutRequest(
                payment={"cash_amount": "50.00", "payment_method": "CASH"},
                idempotency_key=f"table-checkout-{suffix}",
                expected_version=order.version,
            )
            first = OrderService.checkout(working, principal, business_id, "main", order_id, checkout_request)
            retry = OrderService.checkout(working, principal, business_id, "main", order_id, checkout_request)
            assert first.checkout.transaction_id == retry.checkout.transaction_id
            assert working.get(TableSession, session_id).status == "CLOSED"
            assert TableManagementService.get_table(working, principal, business_id, "main", table_one.id).state == "AVAILABLE"
            assert working.query(Transaction).filter(Transaction.order_id == order_id).count() == 1
        finally:
            working.close()

        move_setup = sessions()
        try:
            source = TableManagementService.open_session(move_setup, principal, business_id, "main", table_three.id, TableSessionCreate(guest_count=2))
            target = TableManagementService.open_session(move_setup, principal, business_id, "main", table_four.id, TableSessionCreate(guest_count=2))
            with pytest.raises(ApiError) as exc:
                TableManagementService.move_session(
                    move_setup,
                    principal,
                    business_id,
                    "main",
                    source.session.id,
                    TableSessionMoveRequest(destination_table_id=table_four.id, expected_version=source.session.version),
                )
            assert exc.value.code == "DESTINATION_TABLE_OCCUPIED"
            assert TableManagementService.active_session(move_setup, principal, business_id, "main", table_three.id).id == source.session.id
            assert TableManagementService.active_session(move_setup, principal, business_id, "main", table_four.id).id == target.session.id
        finally:
            move_setup.close()
    finally:
        engine.dispose()
