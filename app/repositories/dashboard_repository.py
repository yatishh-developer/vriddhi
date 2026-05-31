from sqlalchemy.orm import Session
from sqlalchemy import func

from models.product_model import Product
from models.customer_model import Customer
from models.transaction_model import Transaction


class DashboardRepository:

    @staticmethod
    def get_total_products(
        db: Session,
        business_id: str
    ):
        return (
            db.query(Product)
            .filter(
                Product.business_id == business_id,
                Product.is_deleted == False
            )
            .count()
        )

    @staticmethod
    def get_total_customers(
        db: Session,
        business_id: str
    ):
        return (
            db.query(Customer)
            .filter(
                Customer.business_id == business_id
            )
            .count()
        )

    @staticmethod
    def get_total_transactions(
        db: Session,
        business_id: str
    ):
        return (
            db.query(Transaction)
            .filter(
                Transaction.business_id == business_id
            )
            .count()
        )

    @staticmethod
    def get_total_sales(
        db: Session,
        business_id: str
    ):
        total = (
            db.query(func.sum(Transaction.total_amount))
            .filter(
                Transaction.business_id == business_id
            )
            .scalar()
        )

        return total or 0

    @staticmethod
    def get_low_stock_products(
        db: Session,
        business_id: str
    ):
        return (
            db.query(Product)
            .filter(
                Product.business_id == business_id,
                Product.stock_quantity <= 5,
                Product.is_deleted == False
            )
            .all()
        )