from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
from enum import Enum


class InventoryMovementType(str, Enum):
    SALE = "SALE"
    REFUND = "REFUND"
    MANUAL_ADD = "MANUAL_ADD"
    MANUAL_REMOVE = "MANUAL_REMOVE"
    PURCHASE = "PURCHASE"


class InventoryAdjustRequest(BaseModel):
    product_id: str
    quantity: int = Field(gt=0)
    movement_type: InventoryMovementType
    notes: Optional[str] = None
    reference_id: Optional[str] = None


class InventoryMovementResponse(BaseModel):
    id: str
    business_id: str
    product_id: str
    movement_type: InventoryMovementType
    quantity: int
    before_stock: int
    after_stock: int
    reference_id: Optional[str]
    notes: Optional[str]
    created_by: str
    created_at: datetime

    class Config:
        from_attributes = True