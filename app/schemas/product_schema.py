from pydantic import BaseModel
from pydantic import field_validator

from datetime import datetime

from utils.validators import validate_barcode


class ProductBase(BaseModel):

    name: str

    barcode: str | None = None

    price: float

    gst_percentage: float = 0

    hsn_code: str | None = None

    image_url: str | None = None

    category: str | None = None

    in_stock: bool = True

    is_stockless: bool = False

    stock_quantity: int = 0

    description: str | None = None

    ingredients: str | None = None


    @field_validator("barcode")
    @classmethod
    def barcode_validator(cls, value):

        if not validate_barcode(value):
            raise ValueError("Invalid barcode")

        return value

class ProductCreate(ProductBase):

    id: str


class ProductUpdate(BaseModel):

    name: str | None = None

    barcode: str | None = None

    price: float | None = None

    gst_percentage: float | None = None

    hsn_code: str | None = None

    image_url: str | None = None

    category: str | None = None

    in_stock: bool | None = None

    is_stockless: bool | None = None

    stock_quantity: int | None = None

    description: str | None = None

    ingredients: str | None = None


class ProductResponse(ProductBase):

    id: str

    business_id: str

    created_at: datetime

    updated_at: datetime

    is_deleted: bool


    class Config:
        from_attributes = True