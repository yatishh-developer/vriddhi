import pytest
from fastapi import HTTPException

from schemas.staff_billing_schema import StaffBillCreate
from schemas.staff_billing_schema import StaffBillItemPayload
from services.staff_billing_service import StaffBillingService
from services.staff_billing_service import default_staff_permissions
from services.staff_billing_service import feature_flags_for_business_type
from services.staff_billing_service import hash_invite_code


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
