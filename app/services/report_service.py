from sqlalchemy import func

from models.transaction_model import Transaction
from models.transaction_item_model import TransactionItem


class ReportService:

    @staticmethod
    def get_dashboard_summary(
        db,
        business_id
    ):

        total_sales = db.query(
            func.sum(Transaction.total_amount)
        ).filter(
            Transaction.business_id == business_id
        ).scalar()

        total_transactions = db.query(
            Transaction
        ).filter(
            Transaction.business_id == business_id
        ).count()

        return {
            "total_sales": total_sales or 0,
            "total_transactions": total_transactions
        }
