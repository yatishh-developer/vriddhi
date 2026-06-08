from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class TransactionItemPayload(BaseModel):
    product_id: str
    quantity: int


class CreateTransactionRequest(BaseModel):
    id: str
    customer_id: Optional[str] = None

    # Full Flutter transaction fields
    flow: Optional[str] = "Quick"
    bill_no: Optional[str] = None
    bill_date: Optional[str] = None
    bill_date_text: Optional[str] = None
    due_date: Optional[str] = None

    customer_name: Optional[str] = ""
    customer_phone: Optional[str] = ""
    customer_address: Optional[str] = ""

    payment_method: Optional[str] = "Cash"
    payment_option: Optional[str] = "Cash"

    cash_amount: Optional[float] = 0.0
    upi_amount: Optional[float] = 0.0
    card_amount: Optional[float] = 0.0
    other_paid_amount: Optional[float] = 0.0
    credit_amount: Optional[float] = 0.0
    discount: Optional[float] = 0.0

    is_parcel: Optional[bool] = False
    is_hold: Optional[bool] = False

    items_json: Optional[str] = "[]"

    # Product-based items (for stock deduction)
    items: Optional[List[TransactionItemPayload]] = []

    subtotal: Optional[float] = 0.0
    total_cgst: Optional[float] = 0.0
    total_sgst: Optional[float] = 0.0
    total_igst: Optional[float] = 0.0
    total_tax: Optional[float] = 0.0
    total: Optional[float] = 0.0
    old_balance: Optional[float] = 0.0
    is_intra_state: Optional[bool] = True
    branch_id: Optional[str] = "main"
    source_app: Optional[str] = "admin_app"
    sync_status: Optional[str] = "synced"
    idempotency_key: Optional[str] = None
    device_id: Optional[str] = None


class TransactionItemResponse(BaseModel):
    id: str
    product_id: str
    product_name: str
    quantity: int
    price: float
    subtotal: float

    class Config:
        from_attributes = True


class TransactionResponse(BaseModel):
    id: str
    business_id: str
    customer_id: Optional[str] = None

    flow: Optional[str] = "Quick"
    bill_no: Optional[str] = None
    bill_date: Optional[str] = None
    bill_date_text: Optional[str] = None
    due_date: Optional[str] = None

    customer_name: Optional[str] = ""
    customer_phone: Optional[str] = ""
    customer_address: Optional[str] = ""

    payment_method: str
    payment_option: Optional[str] = "Cash"

    cash_amount: Optional[float] = 0.0
    upi_amount: Optional[float] = 0.0
    card_amount: Optional[float] = 0.0
    other_paid_amount: Optional[float] = 0.0
    credit_amount: Optional[float] = 0.0
    discount: Optional[float] = 0.0

    is_parcel: Optional[bool] = False
    is_hold: Optional[bool] = False
    items_json: Optional[str] = "[]"

    total_amount: float
    subtotal: Optional[float] = 0.0
    total_cgst: Optional[float] = 0.0
    total_sgst: Optional[float] = 0.0
    total_igst: Optional[float] = 0.0
    total_tax: Optional[float] = 0.0
    old_balance: Optional[float] = 0.0
    is_intra_state: Optional[bool] = True

    status: str
    branch_id: Optional[str] = "main"
    created_by: Optional[str] = None
    created_by_staff_id: Optional[str] = None
    source_app: Optional[str] = "admin_app"
    sync_status: Optional[str] = "synced"
    idempotency_key: Optional[str] = None
    device_id: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
