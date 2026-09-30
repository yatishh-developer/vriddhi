from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from auth.errors import ApiError, DomainError
from auth.principal import ActorType, PrincipalContext
from database.database import Base
from models.business_model import Business
from models.customer_model import Customer
from models.inventory_movement_model import InventoryMovement
from models.product_model import Product
from models.staff_billing_model import StaffKot, StaffPayment, StaffProfile
from models.transaction_item_model import TransactionItem
from models.transaction_model import Transaction
from models.outbox_model import OutboxEvent
from models.user_model import User
from routes.transaction_routes import delete_transaction
from schemas.checkout_schema import CheckoutItemInput, CheckoutPaymentInput, CheckoutRequest
from schemas.customer_schema import CustomerUpdate
from schemas.inventory_schema import InventoryAdjustRequest, InventoryMovementType
from schemas.staff_billing_schema import StaffBillCreate, StaffBillItemPayload
from schemas.transaction_schema import CreateTransactionRequest, TransactionItemPayload
from services.checkout_service import CheckoutService
from services.customer_service import CustomerService
from services.inventory_service import InventoryService
from services.staff_billing_service import StaffBillingService
from services.transaction_service import TransactionService


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    business = Business(id="business-a", name="Cafe A", business_type="Restaurant")
    other_business = Business(id="business-b", name="Cafe B", business_type="Retail")
    owner = User(id="owner-a", business_id=business.id, email="owner@example.com", password_hash="hash")
    worker = StaffProfile(
        id="worker-a",
        business_id=business.id,
        branch_id="branch-a",
        staff_name="Counter",
        role="cashier",
        permissions_json='{"create_bill": true, "collect_payment": true, "convert_kot_to_bill": true}',
        allowed_apps='["staff_billing_app"]',
        status="active",
        created_by=owner.id,
    )
    product = Product(
        id="product-a", business_id=business.id, name="Tea", price=Decimal("100.00"),
        gst_percentage=Decimal("18.00"), stock_quantity=20, in_stock=True, is_stockless=False,
    )
    plain_product = Product(
        id="product-plain", business_id=business.id, name="Water", price=Decimal("50.00"),
        gst_percentage=Decimal("0.00"), stock_quantity=20, in_stock=True, is_stockless=False,
    )
    other_product = Product(
        id="product-b", business_id=other_business.id, name="Other", price=Decimal("10.00"),
        gst_percentage=Decimal("0.00"), stock_quantity=20, in_stock=True, is_stockless=False,
    )
    customer = Customer(id="customer-a", business_id=business.id, name="Asha", phone="1")
    other_customer = Customer(id="customer-b", business_id=other_business.id, name="Bina", phone="2")
    session.add_all([business, other_business, owner, worker, product, plain_product, other_product, customer, other_customer])
    session.commit()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _owner() -> PrincipalContext:
    return PrincipalContext(
        principal_id="owner-a", actor_type=ActorType.OWNER, business_id="business-a",
        role="owner", user_id="owner-a", permissions=frozenset({"*"}), capabilities=frozenset({"*"}),
    )


def _checkout(product_id="product-a", *, cash="118.00", credit="0.00", customer_id=None, discount="0.00", branch="branch-a", key=None):
    return CheckoutRequest(
        items=[CheckoutItemInput(product_id=product_id, quantity=1)],
        payment=CheckoutPaymentInput(cash_amount=Decimal(cash), credit_amount=Decimal(credit)),
        customer_id=customer_id,
        discount=Decimal(discount),
        branch_id=branch,
        idempotency_key=key,
    )


def _error_code(callable_):
    with pytest.raises(ApiError) as exc:
        callable_()
    return exc.value.code


def test_admin_legacy_checkout_uses_authoritative_price_and_ignores_fake_totals(db):
    payload = CreateTransactionRequest(
        id="admin-legacy-1", branch_id="branch-a", cash_amount=118, subtotal=1, total_tax=0, total=1,
        items=[TransactionItemPayload(product_id="product-a", quantity=1)],
    )
    transaction = TransactionService.create_transaction(db, db.get(User, "owner-a"), payload, _owner())

    assert transaction.subtotal == Decimal("100.00")
    assert transaction.total_tax == Decimal("18.00")
    assert transaction.total_amount == Decimal("118.00")
    assert db.query(TransactionItem).one().price == Decimal("100.00")


def test_checkout_emits_transaction_and_inventory_events_in_its_single_commit(db):
    CheckoutService.checkout(
        db, principal=_owner(), request=_checkout(key="outbox-checkout"), source_app="admin_app",
    )
    event_types = {row.event_type for row in db.query(OutboxEvent).all()}
    assert {"transaction.created", "inventory.changed"}.issubset(event_types)


def test_worker_legacy_checkout_uses_authoritative_price_and_same_totals_as_admin(db):
    staff = db.get(StaffProfile, "worker-a")
    worker_bill = StaffBillingService.create_bill(
        db,
        staff,
        StaffBillCreate(
            id="worker-legacy-1", cash_amount=118, subtotal=1, total=1,
            items=[StaffBillItemPayload(product_id="product-a", product_name="Tea", quantity=1, price=1, subtotal=1)],
        ),
    )
    admin_bill = CheckoutService.checkout(
        db, principal=_owner(), request=_checkout("product-a", key="admin-same-total"), source_app="admin_app",
    )

    assert worker_bill.subtotal == admin_bill.subtotal == Decimal("100.00")
    assert worker_bill.total_tax == admin_bill.total_tax == Decimal("18.00")
    assert worker_bill.total_amount == admin_bill.total_amount == Decimal("118.00")
    assert db.query(TransactionItem).filter_by(transaction_id=worker_bill.id).one().price == Decimal("100.00")


def test_billing_engine_gst_discount_and_strict_item_input(db):
    transaction = CheckoutService.checkout(
        db,
        principal=_owner(),
        request=_checkout(cash="108.00", discount="10.00", key="gst-discount"),
        source_app="admin_app",
    )
    response = CheckoutService.response(transaction)

    assert (response.subtotal, response.total_cgst, response.total_sgst, response.total_tax, response.discount, response.payable) == (
        Decimal("100.00"), Decimal("9.00"), Decimal("9.00"), Decimal("18.00"), Decimal("10.00"), Decimal("108.00"),
    )
    assert response.items[0].unit_price == Decimal("100.00")
    assert _error_code(lambda: CheckoutService.checkout(
        db, principal=_owner(), request=_checkout(cash="1.00", discount="101.00"), source_app="admin_app",
    )) == "INVALID_DISCOUNT"


def test_insufficient_stock_never_goes_negative_and_checkout_rolls_back_all_writes(db):
    first = db.get(Product, "product-a")
    second = Product(
        id="product-empty", business_id="business-a", name="Empty", price=Decimal("1.00"),
        gst_percentage=Decimal("0.00"), stock_quantity=0, in_stock=False, is_stockless=False,
    )
    db.add(second)
    db.commit()
    request = CheckoutRequest(
        items=[CheckoutItemInput(product_id=first.id, quantity=1), CheckoutItemInput(product_id=second.id, quantity=1)],
        payment=CheckoutPaymentInput(cash_amount=Decimal("119.00")), branch_id="branch-a",
    )

    assert _error_code(lambda: CheckoutService.checkout(
        db, principal=_owner(), request=request, source_app="admin_app",
    )) == "INSUFFICIENT_STOCK"
    assert db.get(Product, first.id).stock_quantity == 20
    assert db.query(Transaction).count() == 0
    assert db.query(InventoryMovement).count() == 0
    assert db.query(StaffPayment).count() == 0


def test_each_sale_creates_movement_and_idempotency_prevents_every_duplicate_side_effect(db):
    request = _checkout(customer_id="customer-a", cash="100.00", credit="18.00", key="retry-1")
    first = CheckoutService.checkout(db, principal=_owner(), request=request, source_app="admin_app")
    second = CheckoutService.checkout(db, principal=_owner(), request=request, source_app="admin_app")

    assert first.id == second.id
    assert db.query(Transaction).count() == 1
    assert db.query(TransactionItem).count() == 1
    assert db.query(InventoryMovement).count() == 1
    assert db.query(StaffPayment).count() == 1
    assert db.get(Product, "product-a").stock_quantity == 19
    assert db.get(Customer, "customer-a").balance_remaining == Decimal("18.00")


def test_payment_credit_and_customer_rules_are_enforced(db):
    assert _error_code(lambda: CheckoutService.checkout(
        db, principal=_owner(), request=_checkout(cash="119.00"), source_app="admin_app",
    )) == "PAYMENT_INVALID"
    assert _error_code(lambda: CheckoutService.checkout(
        db, principal=_owner(), request=_checkout(cash="100.00"), source_app="admin_app",
    )) == "PAYMENT_INSUFFICIENT"
    assert _error_code(lambda: CheckoutService.checkout(
        db, principal=_owner(), request=_checkout(cash="100.00", credit="18.00"), source_app="admin_app",
    )) == "CUSTOMER_REQUIRED_FOR_CREDIT"

    worker = StaffBillingService._principal_for_staff(db, db.get(StaffProfile, "worker-a"))
    assert _error_code(lambda: CheckoutService.checkout(
        db, principal=worker, request=_checkout(cash="100.00", credit="18.00", customer_id="customer-a"), source_app="staff_billing_app",
    )) == "CREDIT_NOT_ALLOWED"


def test_customer_profile_updates_cannot_overwrite_checkout_managed_credit(db):
    CheckoutService.checkout(
        db, principal=_owner(),
        request=_checkout(customer_id="customer-a", cash="100.00", credit="18.00", key="credit-balance"),
        source_app="admin_app",
    )
    CustomerService.update_customer(
        db, db.get(User, "owner-a"), "customer-a", CustomerUpdate(balance_remaining=999),
    )
    assert db.get(Customer, "customer-a").balance_remaining == Decimal("18.00")


def test_tenant_and_worker_branch_scopes_are_enforced(db):
    assert _error_code(lambda: CheckoutService.checkout(
        db, principal=_owner(), request=_checkout("product-b"), source_app="admin_app",
    )) == "PRODUCT_NOT_FOUND"
    assert _error_code(lambda: CheckoutService.checkout(
        db, principal=_owner(), request=_checkout(customer_id="customer-b"), source_app="admin_app",
    )) == "CUSTOMER_NOT_FOUND"

    worker = StaffBillingService._principal_for_staff(db, db.get(StaffProfile, "worker-a"))
    assert _error_code(lambda: CheckoutService.checkout(
        db, principal=worker, request=_checkout(branch="branch-b"), source_app="staff_billing_app",
    )) == "BRANCH_ACCESS_DENIED"


def test_manual_inventory_adjustment_is_atomic_when_movement_write_fails(db, monkeypatch):
    original_add = db.add

    def fail_movement(entity):
        if isinstance(entity, InventoryMovement):
            raise RuntimeError("movement store unavailable")
        return original_add(entity)

    monkeypatch.setattr(db, "add", fail_movement)
    with pytest.raises(RuntimeError):
        InventoryService.adjust_inventory(
            db,
            InventoryAdjustRequest(product_id="product-plain", quantity=1, movement_type=InventoryMovementType.MANUAL_REMOVE),
            db.get(User, "owner-a"),
        )
    assert db.get(Product, "product-plain").stock_quantity == 20
    assert db.query(InventoryMovement).count() == 0


def test_finalized_transactions_cannot_be_hard_deleted(db):
    transaction = CheckoutService.checkout(
        db, principal=_owner(), request=_checkout(key="delete-protected"), source_app="admin_app",
    )

    assert _error_code(lambda: delete_transaction(transaction.id, db, db.get(User, "owner-a"))) == "TRANSACTION_FINALIZED"
    assert db.get(Transaction, transaction.id) is not None


def test_kot_conversion_uses_checkout_and_failure_leaves_no_partial_bill(db):
    staff = db.get(StaffProfile, "worker-a")
    kot = StaffKot(
        id="kot-success", business_id="business-a", branch_id="branch-a", staff_id=staff.id,
        status="pending", items_json='[{"product_id": "product-a", "quantity": 1, "price": 1}]',
        created_by="owner-a",
    )
    db.add(kot)
    db.commit()
    bill = StaffBillingService.convert_kot_to_bill(
        db, staff, kot.id, StaffBillCreate(cash_amount=118), StaffBillingService._principal_for_staff(db, staff),
    )
    assert bill.subtotal == Decimal("100.00")
    assert db.get(StaffKot, kot.id).status == "converted"
    assert db.get(StaffKot, kot.id).bill_transaction_id == bill.id

    db.get(Product, "product-plain").stock_quantity = 0
    db.get(Product, "product-plain").in_stock = False
    failed_kot = StaffKot(
        id="kot-failure", business_id="business-a", branch_id="branch-a", staff_id=staff.id,
        status="pending", items_json='[{"product_id": "product-plain", "quantity": 1}]', created_by="owner-a",
    )
    db.add(failed_kot)
    db.commit()
    assert _error_code(lambda: StaffBillingService.convert_kot_to_bill(
        db, staff, failed_kot.id, StaffBillCreate(cash_amount=50), StaffBillingService._principal_for_staff(db, staff),
    )) == "INSUFFICIENT_STOCK"
    assert db.get(StaffKot, failed_kot.id).status == "pending"
    assert db.query(Transaction).filter(Transaction.id != bill.id).count() == 0
