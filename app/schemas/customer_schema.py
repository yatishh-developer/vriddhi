from pydantic import BaseModel
from pydantic import EmailStr
from typing import Optional
from datetime import datetime


class CustomerCreate(BaseModel):
    id: str
    name: str
    phone: Optional[str] = ""
    email: Optional[str] = None
    address: Optional[str] = ""
    balance_remaining: Optional[float] = 0.0
    loyal_customer: Optional[bool] = False
    preset_discount: Optional[float] = 0.0


class CustomerUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    balance_remaining: Optional[float] = None
    loyal_customer: Optional[bool] = None
    preset_discount: Optional[float] = None


class CustomerResponse(BaseModel):
    id: str
    business_id: str
    name: str
    phone: Optional[str] = ""
    email: Optional[str] = None
    address: Optional[str] = ""
    balance_remaining: Optional[float] = 0.0
    loyal_customer: Optional[bool] = False
    preset_discount: Optional[float] = 0.0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
