from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class BusinessUpdate(BaseModel):
    name: Optional[str] = None
    business_type: Optional[str] = None
    gst_number: Optional[str] = None
    owner_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None
    upi_id: Optional[str] = None
    is_intra_state: Optional[bool] = None
    default_discount: Optional[str] = None


class BusinessResponse(BaseModel):
    id: str
    name: str
    business_type: str
    gst_number: Optional[str] = None
    owner_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None
    upi_id: Optional[str] = None
    is_intra_state: Optional[bool] = True
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
