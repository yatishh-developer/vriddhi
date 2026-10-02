from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class CheckoutItemInput(BaseModel):
    """Business intent only; pricing and tax always come from the server."""

    model_config = ConfigDict(extra="forbid")

    product_id: str
    quantity: int = Field(gt=0)
    variant_id: Optional[str] = None
    addons: list[str] = Field(default_factory=list)
    notes: Optional[str] = None


class CheckoutPaymentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cash_amount: Decimal = Decimal("0.00")
    upi_amount: Decimal = Decimal("0.00")
    card_amount: Decimal = Decimal("0.00")
    other_paid_amount: Decimal = Decimal("0.00")
    credit_amount: Decimal = Decimal("0.00")
    payment_method: str = "Cash"
    payment_option: str = "Cash"


class CheckoutRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[CheckoutItemInput] = Field(min_length=1)
    payment: CheckoutPaymentInput = Field(default_factory=CheckoutPaymentInput)
    customer_id: Optional[str] = None
    discount: Decimal = Decimal("0.00")
    branch_id: Optional[str] = None
    idempotency_key: Optional[str] = None
    device_id: Optional[str] = None
    bill_no: Optional[str] = None
    bill_date: Optional[str] = None
    bill_date_text: Optional[str] = None
    is_parcel: bool = False


class CheckoutItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_id: str
    product_name: str
    quantity: int
    unit_price: Decimal
    subtotal: Decimal
    gst_percentage: Decimal
    tax: Decimal


class CheckoutResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    order_id: Optional[str] = None
    transaction_id: str
    bill_number: Optional[str] = None
    payment_method: str
    payment_option: Optional[str] = None
    subtotal: Decimal
    total_cgst: Decimal
    total_sgst: Decimal
    total_igst: Decimal
    total_tax: Decimal
    discount: Decimal
    previous_balance: Decimal
    payable: Decimal
    cash_amount: Decimal
    upi_amount: Decimal
    card_amount: Decimal
    other_paid_amount: Decimal
    credit_amount: Decimal
    change: Decimal
    customer_id: Optional[str] = None
    items: list[CheckoutItemResponse]
    created_at: datetime
