from fastapi import HTTPException

from models.customer_model import Customer
from repositories.customer_repository import CustomerRepository


class CustomerService:

    @staticmethod
    def handle_queue_item(db, current_user, action: str, payload: dict):
        """Handle a queued offline customer operation from the Flutter sync queue."""
        from schemas.customer_schema import CustomerCreate, CustomerUpdate

        if action == "create":
            try:
                # Tolerant create: payloads may not carry an email field.
                data = CustomerCreate(**payload)
                CustomerService.create_customer(db, current_user, data)
            except Exception as e:
                # Validation / unique-violation is non-fatal during sync.
                # Bubble the message so the route can surface it as a queue error.
                raise e

        elif action == "update":
            customer_id = payload.get("id")
            if not customer_id:
                return
            data_dict = {k: v for k, v in payload.items() if k != "id"}
            data = CustomerUpdate(**data_dict)
            try:
                CustomerService.update_customer(db, current_user, customer_id, data)
            except HTTPException as e:
                # 404 → fall back to upsert via create
                if e.status_code == 404:
                    create_payload = {"id": customer_id, **data_dict}
                    create_payload.setdefault("name", "Customer")
                    CustomerService.create_customer(
                        db, current_user, CustomerCreate(**create_payload)
                    )
                else:
                    raise

        elif action == "delete":
            customer_id = payload.get("id")
            if not customer_id:
                return
            try:
                CustomerService.delete_customer(db, current_user, customer_id)
            except HTTPException as e:
                if e.status_code != 404:
                    raise

    @staticmethod
    def create_customer(db, current_user, payload):
        # Upsert: if same id exists update it
        existing = CustomerRepository.get_by_id(
            db, payload.id, current_user.business_id, include_deleted=True
        )
        if existing:
            existing.name = payload.name
            existing.phone = payload.phone or ""
            existing.email = payload.email
            existing.address = payload.address or ""
            existing.balance_remaining = payload.balance_remaining or 0.0
            existing.loyal_customer = payload.loyal_customer or False
            existing.preset_discount = payload.preset_discount or 0.0
            existing.is_deleted = False
            db.commit()
            db.refresh(existing)
            return existing

        customer = Customer(
            id=payload.id,
            business_id=current_user.business_id,
            name=payload.name,
            phone=payload.phone or "",
            email=payload.email,
            address=payload.address or "",
            balance_remaining=payload.balance_remaining or 0.0,
            loyal_customer=payload.loyal_customer or False,
            preset_discount=payload.preset_discount or 0.0
        )
        db.add(customer)
        db.commit()
        db.refresh(customer)
        return customer

    @staticmethod
    def update_customer(db, current_user, customer_id, payload):
        customer = CustomerRepository.get_by_id(db, customer_id, current_user.business_id)
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found")

        if payload.name is not None:
            customer.name = payload.name
        if payload.phone is not None:
            customer.phone = payload.phone
        if payload.email is not None:
            customer.email = payload.email
        if payload.address is not None:
            customer.address = payload.address
        if payload.balance_remaining is not None:
            customer.balance_remaining = payload.balance_remaining
        if payload.loyal_customer is not None:
            customer.loyal_customer = payload.loyal_customer
        if payload.preset_discount is not None:
            customer.preset_discount = payload.preset_discount

        db.commit()
        db.refresh(customer)
        return customer

    @staticmethod
    def delete_customer(db, current_user, customer_id):
        customer = CustomerRepository.get_by_id(db, customer_id, current_user.business_id)
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found")
        customer.is_deleted = True
        db.commit()
        return {"message": "Customer deleted"}
