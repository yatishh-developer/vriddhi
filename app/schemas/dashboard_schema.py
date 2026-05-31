from pydantic import BaseModel
from typing import List


class DashboardSummaryResponse(BaseModel):
    total_products: int
    total_customers: int
    total_transactions: int
    total_sales: float
    low_stock_products: int


class TopProductResponse(BaseModel):
    product_id: str
    product_name: str
    total_quantity_sold: int


class LowStockProductResponse(BaseModel):
    product_id: str
    product_name: str
    stock_quantity: int