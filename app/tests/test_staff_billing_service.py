import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy import event
from sqlalchemy.orm import sessionmaker

from database.database import Base
from models.business_model import Business
from models.product_model import Product
from models.staff_billing_model import StaffProfile
from models.staff_billing_model import StaffPayment
from models.transaction_item_model import TransactionItem
from models.transaction_model import Transaction
from models.user_model import User
from schemas.staff_billing_schema import StaffBillCreate
from schemas.staff_billing_schema import StaffBillItemPayload
from schemas.staff_billing_schema import StaffFirebaseInviteAcceptRequest
from schemas.staff_billing_schema import StaffFirebaseLoginRequest
from services.staff_billing_service import StaffBillingService
from services.staff_billing_service import default_staff_permissions
from services.staff_billing_service import feature_flags_for_business_type
from services.staff_billing_service import hash_invite_code
from services.staff_billing_service import normalize_invite_code


def test_restaurant_business_enables_kot():
    flags = feature_flags_for_business_type("Restaurant / Cafe")

    assert flags["kot"] is True
    assert flags["pending_kot"] is True
    assert flags["table_token"] is True
    assert flags["barcode_scan"] is False


def test_retail_business_hides_kot_and_enables_barcode():
    flags = feature_flags_for_business_type("Retail Kirana")

    assert flags["kot"] is False
    assert flags["pending_kot"] is False
    assert flags["barcode_scan"] is True
    assert flags["hold_bill"] is True


def test_invite_code_hash_is_stable_and_not_plaintext():
    first = hash_invite_code("123456")
    second = hash_invite_code("123 456")

    assert first == second
    assert first != "123456"


def test_invite_code_normalizes_qr_payload():
    assert normalize_invite_code("vabos-staff-invite://lookup/123456") == "123456"
    assert hash_invite_code("123456") == hash_invite_code(
        "vabos-staff-invite://lookup/123456"
    )


def test_firebase_login_payload_accepts_flutter_field_names():
    payload = StaffFirebaseLoginRequest(
        uid="firebase-user-1",
        idToken="token",
        displayName="Counter Staff",
        phoneNumber="+919999999999",
        provider="google",
    )

    assert payload.id_token == "token"
    assert payload.display_name == "Counter Staff"
    assert payload.phone_number == "+919999999999"


def test_firebase_invite_accept_payload_accepts_invite_code_alias():
    payload = StaffFirebaseInviteAcceptRequest(
        uid="firebase-user-1",
        inviteCode="123456",
    )

    assert payload.invite_code == "123456"


def test_credit_payment_requires_customer():
    flags = feature_flags_for_business_type("General")
    permissions = {
        **default_staff_permissions(flags),
        "credit_sale": True,
    }
    payload = StaffBillCreate(
        total=100,
        subtotal=100,
        credit_amount=100,
        items=[StaffBillItemPayload(product_name="Tea", quantity=1, price=100, subtotal=100)],
    )

    with pytest.raises(HTTPException) as exc:
        StaffBillingService._validate_bill_payload(payload, permissions)

    assert exc.value.status_code == 400
    assert exc.value.detail == "Credit payment requires customer"


def test_credit_payment_requires_saved_customer_id():
    flags = feature_flags_for_business_type("General")
    permissions = {
        **default_staff_permissions(flags),
        "credit_sale": True,
    }
    payload = StaffBillCreate(
        total=100,
        subtotal=100,
        credit_amount=100,
        customer_name="Walk In",
        items=[StaffBillItemPayload(product_name="Tea", quantity=1, price=100, subtotal=100)],
    )

    with pytest.raises(HTTPException) as exc:
        StaffBillingService._validate_bill_payload(payload, permissions)

    assert exc.value.status_code == 400
    assert exc.value.detail == "Credit payment requires customer"


def test_staff_billing_requires_allowed_app():
    staff = StaffProfile(
        id="staff-1",
        business_id="business-1",
        branch_id="main",
        staff_name="Counter Staff",
        role="cashier",
        allowed_apps='["staff_attendance_app"]',
        permissions_json="{}",
        status="active",
    )

    with pytest.raises(HTTPException) as exc:
        StaffBillingService._ensure_staff_billing_allowed(staff)

    assert exc.value.status_code == 403


def test_staff_bill_flushes_transaction_before_payment_fk():
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    try:
        business = Business(
            id="business-1",
            name="Coffee Date",
            business_type="Restaurant / Cafe",
        )
        user = User(
            id="user-1",
            business_id=business.id,
            email="owner@example.com",
            password_hash="hash",
        )
        staff = StaffProfile(
            id="staff-1",
            business_id=business.id,
            branch_id="main",
            staff_name="Counter Staff",
            role="cashier",
            permissions_json="{}",
            allowed_apps='["staff_billing_app"]',
            status="active",
            created_by=user.id,
        )
        product = Product(
            id="product-1",
            business_id=business.id,
            name="Tea",
            price=20,
            gst_percentage=0,
            stock_quantity=5,
            in_stock=True,
            is_stockless=False,
        )
        db.add(business)
        db.commit()

        db.add_all([user, product])
        db.commit()

        db.add(staff)
        db.commit()

        payload = StaffBillCreate(
            id="txn-1",
            bill_no="VABOS/2026-27/1",
            payment_method="Split",
            payment_option="Split",
            subtotal=20,
            total=20,
            cash_amount=20,
            idempotency_key="staff-bill-1",
            items=[
                StaffBillItemPayload(
                    product_id=product.id,
                    product_name=product.name,
                    quantity=1,
                    price=20,
                    subtotal=20,
                )
            ],
        )

        transaction = StaffBillingService.create_bill(db, staff, payload)

        assert transaction.id == "txn-1"
        assert db.query(Transaction).count() == 1
        assert db.query(StaffPayment).count() == 1
        assert db.query(TransactionItem).count() == 1
        assert db.query(Product).filter(Product.id == product.id).first().stock_quantity == 4

        duplicate = StaffBillingService.create_bill(db, staff, payload)
        assert duplicate.id == transaction.id
        assert db.query(Transaction).count() == 1
        assert db.query(StaffPayment).count() == 1
    finally:
        db.close()
        engine.dispose()


def test_negative_payment_is_rejected():
    flags = feature_flags_for_business_type("General")
    permissions = default_staff_permissions(flags)
    payload = StaffBillCreate(
        total=100,
        subtotal=100,
        cash_amount=-1,
        items=[StaffBillItemPayload(product_name="Tea", quantity=1, price=100, subtotal=100)],
    )

    with pytest.raises(HTTPException) as exc:
        StaffBillingService._validate_bill_payload(payload, permissions)

    assert exc.value.status_code == 400
    assert exc.value.detail == "Paid amount cannot be negative"


def test_uncovered_payment_split_is_rejected():
    flags = feature_flags_for_business_type("General")
    permissions = default_staff_permissions(flags)
    payload = StaffBillCreate(
        total=100,
        subtotal=100,
        cash_amount=80,
        items=[StaffBillItemPayload(product_name="Tea", quantity=1, price=100, subtotal=100)],
    )

    with pytest.raises(HTTPException) as exc:
        StaffBillingService._validate_bill_payload(payload, permissions)

    assert exc.value.status_code == 400
    assert exc.value.detail == "Payment split does not cover payable total"
