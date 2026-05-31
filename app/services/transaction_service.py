import uuid

from fastapi import HTTPException

from models.transaction_model import Transaction
from models.transaction_item_model import TransactionItem
from repositories.product_repository import ProductRepository
from services.inventory_service import InventoryService


class TransactionService:

    @staticmethod
    def create_transaction(db, current_user, payload):
        """
        Create (or upsert) a transaction.
        Accepts full Flutter payload including items_json snapshot.
        Product-based items list (payload.items) is used for stock deduction;
        if empty, only the JSON snapshot is stored (offline-first support).
        """

        # Upsert: if already exists, just update totals
        existing = db.query(Transaction).filter(
            Transaction.id == payload.id
        ).first()

        if existing:
            TransactionService._apply_payload(existing, payload)
            db.commit()
            db.refresh(existing)
            return existing

        transaction = Transaction(
            id=payload.id,
            business_id=current_user.business_id,
            customer_id=payload.customer_id,
            payment_method=payload.payment_method or "Cash",
            total_amount=payload.total or 0.0,
            status="completed"
        )
        TransactionService._apply_payload(transaction, payload)

        db.add(transaction)

        # If product items were supplied, deduct stock
        total_amount = payload.total or 0.0

        if payload.items:
            total_amount = 0
            for item in payload.items:
                product = ProductRepository.get_by_id(
                    db, item.product_id, current_user.business_id
                )
                if not product:
                    raise HTTPException(status_code=404, detail=f"Product {item.product_id} not found")

                subtotal = product.price * item.quantity
                total_amount += subtotal

                if not product.is_stockless:
                    InventoryService.reduce_stock(
                        db, current_user.business_id, product, item.quantity
                    )

                transaction_item = TransactionItem(
                    id=str(uuid.uuid4()),
                    transaction_id=transaction.id,
                    product_id=product.id,
                    product_name=product.name,
                    quantity=item.quantity,
                    price=product.price,
                    subtotal=subtotal
                )
                db.add(transaction_item)

            transaction.total_amount = total_amount

        db.commit()
        db.refresh(transaction)
        return transaction

    @staticmethod
    def _apply_payload(transaction, payload):
        """Map Flutter payload fields onto the SQLAlchemy model."""
        transaction.flow = payload.flow or "Quick"
        transaction.bill_no = payload.bill_no
        transaction.bill_date = payload.bill_date
        transaction.bill_date_text = payload.bill_date_text
        transaction.due_date = payload.due_date
        transaction.customer_name = payload.customer_name or ""
        transaction.customer_phone = payload.customer_phone or ""
        transaction.customer_address = payload.customer_address or ""
        transaction.payment_option = payload.payment_option or payload.payment_method or "Cash"
        transaction.cash_amount = payload.cash_amount or 0.0
        transaction.upi_amount = payload.upi_amount or 0.0
        transaction.credit_amount = payload.credit_amount or 0.0
        transaction.discount = payload.discount or 0.0
        transaction.is_parcel = payload.is_parcel or False
        transaction.is_hold = payload.is_hold or False
        transaction.items_json = payload.items_json or "[]"
        transaction.subtotal = payload.subtotal or 0.0
        transaction.total_cgst = payload.total_cgst or 0.0
        transaction.total_sgst = payload.total_sgst or 0.0
        transaction.total_igst = payload.total_igst or 0.0
        transaction.total_tax = payload.total_tax or 0.0
        transaction.old_balance = payload.old_balance or 0.0
        transaction.is_intra_state = payload.is_intra_state if payload.is_intra_state is not None else True
        if payload.total:
            transaction.total_amount = payload.total

    @staticmethod
    def handle_queue_item(db, current_user, action: str, payload: dict):
        """Handle a queued offline transaction operation from the Flutter sync queue."""
        from schemas.transaction_schema import CreateTransactionRequest

        if action == "create":
            try:
                data = CreateTransactionRequest(**payload)
                TransactionService.create_transaction(db, current_user, data)
            except Exception as e:
                raise e

        elif action == "delete":
            transaction_id = payload.get("id")
            if not transaction_id:
                return
            transaction = db.query(Transaction).filter(
                Transaction.id == transaction_id,
                Transaction.business_id == current_user.business_id,
            ).first()
            if transaction:
                db.delete(transaction)
                db.commit()
