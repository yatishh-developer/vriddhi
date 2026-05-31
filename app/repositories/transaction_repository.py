from models.transaction_model import Transaction


class TransactionRepository:

    @staticmethod
    def get_all(db, business_id):
        return (
            db.query(Transaction)
            .filter(Transaction.business_id == business_id)
            .order_by(Transaction.created_at.desc())
            .all()
        )

    @staticmethod
    def get_by_id(db, transaction_id, business_id):
        return (
            db.query(Transaction)
            .filter(
                Transaction.id == transaction_id,
                Transaction.business_id == business_id
            )
            .first()
        )

    @staticmethod
    def delete(db, transaction):
        db.delete(transaction)
        db.commit()
