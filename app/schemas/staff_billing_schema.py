from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import AliasChoices
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field


class StaffInviteCreate(BaseModel):
    staff_name: str
    staff_role: str = "cashier"
    branch_id: str = "main"
    code_length: int = 6
    expires_in_seconds: int = 60
    max_uses: int = 1
    permissions: Dict[str, Any] = Field(default_factory=dict)
    allowed_apps: List[str] = Field(default_factory=lambda: ["staff_billing_app"])


class StaffInviteUpdate(BaseModel):
    staff_name: Optional[str] = None
    staff_role: Optional[str] = None
    branch_id: Optional[str] = None
    permissions: Optional[Dict[str, Any]] = None
    allowed_apps: Optional[List[str]] = None
    expires_in_seconds: Optional[int] = None
    max_uses: Optional[int] = None


class StaffInviteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    business_id: str
    business_name: Optional[str] = None
    business_type: Optional[str] = None
    branch_id: str
    staff_name: str
    staff_role: str
    invite_code: Optional[str] = None
    code_length: int = 6
    allowed_apps: List[str] = Field(default_factory=lambda: ["staff_billing_app"])
    permissions: Dict[str, Any] = Field(default_factory=dict)
    feature_flags: Dict[str, Any] = Field(default_factory=dict)
    expires_at: datetime
    max_uses: int
    used_count: int
    status: str
    created_by: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class StaffProfileAdminResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    business_id: str
    branch_id: str
    invite_id: Optional[str] = None
    staff_name: str
    role: str
    permissions: Dict[str, Any] = Field(default_factory=dict)
    allowed_apps: List[str] = Field(default_factory=lambda: ["staff_billing_app"])
    status: str
    last_seen_at: Optional[datetime] = None
    created_by: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class StaffProfileAdminUpdate(BaseModel):
    staff_name: Optional[str] = None
    role: Optional[str] = None
    branch_id: Optional[str] = None
    permissions: Optional[Dict[str, Any]] = None
    allowed_apps: Optional[List[str]] = None
    status: Optional[str] = None


class StaffInviteVerifyRequest(BaseModel):
    invite_code: str
    device_id: Optional[str] = None


class StaffFirebaseLoginRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    uid: Optional[str] = None
    id_token: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("id_token", "idToken"),
    )
    email: Optional[str] = None
    display_name: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("display_name", "displayName"),
    )
    phone_number: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("phone_number", "phoneNumber"),
    )
    provider: Optional[str] = None


class StaffFirebaseInviteAcceptRequest(StaffFirebaseLoginRequest):
    invite_code: str = Field(
        validation_alias=AliasChoices("invite_code", "inviteCode"),
    )


class StaffAuthResponse(BaseModel):
    staff_id: str
    staff_name: str
    business_id: str
    business_name: str
    business_type: str
    branch_id: str
    role: str
    permissions: Dict[str, Any]
    feature_flags: Dict[str, Any]
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class StaffRefreshRequest(BaseModel):
    refresh_token: str


class StaffTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class StaffMeResponse(BaseModel):
    staff_id: str
    staff_name: str
    business_id: str
    business_name: str
    business_type: str
    branch_id: str
    role: str
    permissions: Dict[str, Any]
    feature_flags: Dict[str, Any]
    allowed_apps: List[str]
    status: str


class StaffBillItemPayload(BaseModel):
    product_id: Optional[str] = None
    product_name: str
    quantity: int = 1
    price: float = 0.0
    gst_percentage: float = 0.0
    subtotal: float = 0.0


class StaffBillCreate(BaseModel):
    id: Optional[str] = None
    bill_no: Optional[str] = None
    bill_date: Optional[str] = None
    bill_date_text: Optional[str] = None
    customer_id: Optional[str] = None
    customer_name: Optional[str] = ""
    customer_phone: Optional[str] = ""
    customer_address: Optional[str] = ""
    payment_method: str = "Cash"
    payment_option: str = "Cash"
    cash_amount: float = 0.0
    upi_amount: float = 0.0
    card_amount: float = 0.0
    other_paid_amount: float = 0.0
    credit_amount: float = 0.0
    discount: float = 0.0
    is_parcel: bool = False
    subtotal: float = 0.0
    total_cgst: float = 0.0
    total_sgst: float = 0.0
    total_igst: float = 0.0
    total_tax: float = 0.0
    total: float = 0.0
    old_balance: float = 0.0
    is_intra_state: bool = True
    items: List[StaffBillItemPayload] = Field(default_factory=list)
    items_json: Optional[Any] = None
    idempotency_key: Optional[str] = None
    device_id: Optional[str] = None
    sync_status: str = "pending"


class StaffBillResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    business_id: str
    branch_id: Optional[str] = "main"
    created_by_staff_id: Optional[str] = None
    source_app: str = "staff_billing_app"
    status: str
    bill_no: Optional[str] = None
    payment_method: str
    cash_amount: float = 0.0
    upi_amount: float = 0.0
    card_amount: float = 0.0
    other_paid_amount: float = 0.0
    credit_amount: float = 0.0
    subtotal: float = 0.0
    total_tax: float = 0.0
    total_amount: float = 0.0
    idempotency_key: Optional[str] = None
    created_at: datetime


class StaffKotCreate(BaseModel):
    id: Optional[str] = None
    order_type: Optional[str] = None
    table_token: Optional[str] = None
    items: List[StaffBillItemPayload] = Field(default_factory=list)
    items_json: Optional[Any] = None
    subtotal: float = 0.0
    total_tax: float = 0.0
    total_amount: float = 0.0
    idempotency_key: Optional[str] = None
    device_id: Optional[str] = None


class StaffKotUpdate(BaseModel):
    status: Optional[str] = None
    order_type: Optional[str] = None
    table_token: Optional[str] = None
    items: Optional[List[StaffBillItemPayload]] = None
    items_json: Optional[Any] = None
    subtotal: Optional[float] = None
    total_tax: Optional[float] = None
    total_amount: Optional[float] = None


class StaffKotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    business_id: str
    branch_id: str
    staff_id: Optional[str] = None
    staff_name: Optional[str] = None
    status: str
    order_type: Optional[str] = None
    table_token: Optional[str] = None
    items_json: str
    subtotal: float
    total_tax: float
    total_amount: float
    bill_transaction_id: Optional[str] = None
    idempotency_key: Optional[str] = None
    created_at: datetime


class StaffHeldBillCreate(BaseModel):
    id: Optional[str] = None
    customer_id: Optional[str] = None
    customer_name: Optional[str] = None
    items: List[StaffBillItemPayload] = Field(default_factory=list)
    items_json: Optional[Any] = None
    subtotal: float = 0.0
    total_tax: float = 0.0
    total_amount: float = 0.0
    idempotency_key: Optional[str] = None


class StaffHeldBillResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    business_id: str
    branch_id: str
    staff_id: Optional[str] = None
    staff_name: Optional[str] = None
    status: str
    customer_id: Optional[str] = None
    customer_name: Optional[str] = None
    items_json: str
    subtotal: float
    total_tax: float
    total_amount: float
    bill_transaction_id: Optional[str] = None
    idempotency_key: Optional[str] = None
    created_at: datetime


class StaffProcessClaimRequest(BaseModel):
    process_id: Optional[str] = None
    process_type: str
    entity_id: str
    ttl_seconds: int = 120


class StaffProcessReleaseRequest(BaseModel):
    process_id: str
    status: str = "released"


class StaffProcessHeartbeatRequest(BaseModel):
    process_id: str
    ttl_seconds: int = 120


class StaffProcessLockResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    process_id: str
    process_type: str
    entity_id: str
    business_id: str
    branch_id: str
    handled_by_staff_id: Optional[str] = None
    handled_by_staff_name: Optional[str] = None
    status: str
    locked_at: datetime
    last_heartbeat_at: datetime
    expires_at: datetime


class RealtimeEventEnvelope(BaseModel):
    event_id: str
    event_type: str
    entity_type: str
    entity_id: str
    business_id: Optional[str] = None
    branch_id: Optional[str] = None
    staff_id: Optional[str] = None
    device_id: Optional[str] = None
    occurred_at: Optional[datetime] = None
    payload: Dict[str, Any] = Field(default_factory=dict)


class StaffSyncPushRequest(BaseModel):
    events: List[RealtimeEventEnvelope] = Field(default_factory=list)


class StaffSyncPushResponse(BaseModel):
    accepted: int
    duplicates: int
    errors: List[str] = Field(default_factory=list)


class StaffSyncPullResponse(BaseModel):
    products: List[Dict[str, Any]]
    kots: List[Dict[str, Any]]
    held_bills: List[Dict[str, Any]]
    bills: List[Dict[str, Any]]
    events: List[Dict[str, Any]]
