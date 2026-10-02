from pydantic import BaseModel, ConfigDict, Field
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


class V1CustomerCreate(BaseModel):
    """Strict, scoped customer-create contract for offline POS retries."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=255)
    phone: Optional[str] = Field(default="", max_length=64)
    email: Optional[str] = Field(default=None, max_length=255)
    address: Optional[str] = Field(default="", max_length=1000)
    loyal_customer: bool = False
    preset_discount: float = Field(default=0.0, ge=0)
    client_mutation_id: str = Field(min_length=1, max_length=128)


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
