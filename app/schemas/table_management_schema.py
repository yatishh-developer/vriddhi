from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from schemas.order_schema import OrderResponse


class RestaurantTableCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    code: Optional[str] = Field(default=None, max_length=50)
    capacity: int = Field(gt=0, le=100)
    section: Optional[str] = Field(default=None, max_length=100)
    sort_order: Optional[int] = None
    x_position: Optional[int] = None
    y_position: Optional[int] = None
    shape: Optional[str] = Field(default=None, max_length=30)


class RestaurantTableUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    code: Optional[str] = Field(default=None, max_length=50)
    capacity: Optional[int] = Field(default=None, gt=0, le=100)
    section: Optional[str] = Field(default=None, max_length=100)
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None
    x_position: Optional[int] = None
    y_position: Optional[int] = None
    shape: Optional[str] = Field(default=None, max_length=30)
    expected_version: Optional[int] = Field(default=None, ge=1)


class TableActiveSessionSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    guest_count: int
    opened_at: datetime
    order_id: Optional[str] = None
    item_count: int


class RestaurantTableResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    business_id: str
    branch_id: str
    name: str
    code: Optional[str] = None
    capacity: int
    section: Optional[str] = None
    is_active: bool
    sort_order: Optional[int] = None
    x_position: Optional[int] = None
    y_position: Optional[int] = None
    shape: Optional[str] = None
    state: str
    active_session: Optional[TableActiveSessionSummary] = None
    version: int
    created_at: datetime
    updated_at: datetime


class TableSessionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    guest_count: int = Field(gt=0, le=100)
    customer_id: Optional[str] = None
    notes: Optional[str] = Field(default=None, max_length=1000)


class TableSessionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    guest_count: Optional[int] = Field(default=None, gt=0, le=100)
    customer_id: Optional[str] = None
    notes: Optional[str] = Field(default=None, max_length=1000)
    expected_version: Optional[int] = Field(default=None, ge=1)


class TableSessionTableResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    table_id: str
    name: str
    is_primary: bool
    attached_at: datetime


class TableSessionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    business_id: str
    branch_id: str
    primary_table_id: str
    status: str
    guest_count: int
    customer_id: Optional[str] = None
    opened_by_principal_id: str
    opened_at: datetime
    closed_at: Optional[datetime] = None
    notes: Optional[str] = None
    version: int
    tables: list[TableSessionTableResponse]
    order: Optional[OrderResponse] = None


class TableSessionOpenResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session: TableSessionResponse
    order: OrderResponse


class TableSessionMoveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    destination_table_id: str
    expected_version: Optional[int] = Field(default=None, ge=1)


class TableSessionAttachTableRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    table_id: str
    expected_version: Optional[int] = Field(default=None, ge=1)


class TableSessionCancelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=1000)
    expected_version: Optional[int] = Field(default=None, ge=1)


class TableSessionBillRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: Optional[int] = Field(default=None, ge=1)
