from models.customer_model import Customer


class CustomerRepository:

    @staticmethod
    def get_all(db, business_id):
        return (
            db.query(Customer)
            .filter(
                Customer.business_id == business_id,
                Customer.is_deleted == False
            )
            .all()
        )

    @staticmethod
    def get_by_id(db, customer_id, business_id, include_deleted=False):
        q = db.query(Customer).filter(
            Customer.id == customer_id,
            Customer.business_id == business_id
        )
        if not include_deleted:
            q = q.filter(Customer.is_deleted == False)
        return q.first()
