from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from schemas.checkout_schema import CheckoutPaymentInput, CheckoutResponse


OrderType = Literal["QUICK", "TAKEAWAY", "DINE_IN", "DELIVERY"]
OrderStatus = Literal["DRAFT", "ACTIVE", "HELD", "CHECKOUT_PENDING", "COMPLETED", "CANCELLED"]


class OrderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order_type: OrderType = "QUICK"
    customer_id: Optional[str] = None
    idempotency_key: Optional[str] = Field(default=None, max_length=128)


class OrderItemCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: str
    quantity: int = Field(gt=0)
    notes: Optional[str] = Field(default=None, max_length=1000)


class OrderItemsCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[OrderItemCreate] = Field(min_length=1)
    expected_version: Optional[int] = Field(default=None, ge=1)


class OrderItemUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    quantity: Optional[int] = Field(default=None, ge=0)
    notes: Optional[str] = Field(default=None, max_length=1000)
    expected_version: Optional[int] = Field(default=None, ge=1)


class OrderTransitionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: Optional[int] = Field(default=None, ge=1)


class OrderHoldRequest(OrderTransitionRequest):
    pass


class OrderCancelRequest(OrderTransitionRequest):
    reason: str = Field(min_length=1, max_length=1000)


class OrderCheckoutRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    payment: CheckoutPaymentInput
    discount: Decimal = Decimal("0.00")
    idempotency_key: Optional[str] = Field(default=None, max_length=128)
    expected_version: Optional[int] = Field(default=None, ge=1)
    is_parcel: bool = False


class OrderItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    product_id: str
    product_name_snapshot: str
    unit_price_snapshot: Decimal
    tax_rate_snapshot: Decimal
    quantity: int
    notes: Optional[str] = None
    status: str
    kot_sent_quantity: int
    cancelled_quantity: int
    billed_quantity: int
    version: int
    created_at: datetime
    updated_at: datetime


class OrderCustomerSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    phone: str


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    business_id: str
    branch_id: str
    order_type: str
    status: str
    customer_id: Optional[str] = None
    customer: Optional[OrderCustomerSummary] = None
    table_session_id: Optional[str] = None
    transaction_id: Optional[str] = None
    cancellation_reason: Optional[str] = None
    version: int
    created_by: Optional[str] = None
    created_by_staff_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    items: list[OrderItemResponse] = Field(default_factory=list)


class OrderListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[OrderResponse]
    total: int
    page: int
    page_size: int


class OrderCheckoutResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order: OrderResponse
    checkout: CheckoutResponse
