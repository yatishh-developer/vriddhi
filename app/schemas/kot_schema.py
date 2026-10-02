from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class KOTCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    notes: Optional[str] = Field(default=None, max_length=1000)
    idempotency_key: Optional[str] = Field(default=None, max_length=128)
    expected_order_version: Optional[int] = Field(default=None, ge=1)


class KOTStatusUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str = Field(pattern="^(PREPARING|READY|SERVED|CANCELLED)$")
    expected_version: Optional[int] = Field(default=None, ge=1)


class OrderItemCancelQuantityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    quantity: int = Field(gt=0)
    reason: str = Field(min_length=1, max_length=1000)
    expected_version: Optional[int] = Field(default=None, ge=1)


class KOTItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    order_item_id: str
    product_id: str
    product_name_snapshot: str
    quantity: int
    notes_snapshot: Optional[str] = None


class KOTTableContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    table_names: list[str]


class KOTPrintPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    business_name: str
    kot_number: str
    created_at: datetime
    order_type: str
    table_names: list[str]
    notes: Optional[str] = None
    items: list[KOTItemResponse]


class KOTResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    business_id: str
    branch_id: str
    order_id: str
    order_status: str
    order_version: int
    table_session_id: Optional[str] = None
    kot_number: str
    status: str
    notes: Optional[str] = None
    created_by_principal_id: str
    version: int
    created_at: datetime
    updated_at: datetime
    preparing_at: Optional[datetime] = None
    ready_at: Optional[datetime] = None
    served_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    items: list[KOTItemResponse]
    table: Optional[KOTTableContext] = None
    print_payload: KOTPrintPayload


class KOTListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[KOTResponse]
    total: int
    page: int
    page_size: int


class KOTCancellationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    order_id: str
    order_item_id: str
    kot_id: Optional[str] = None
    quantity: int
    reason: str
    created_by_principal_id: str
    created_at: datetime
