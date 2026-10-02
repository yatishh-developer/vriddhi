import uuid

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from auth.authorization import require_permission
from auth.errors import DomainError
from auth.principal import PrincipalContext
from models.customer_model import Customer
from repositories.customer_repository import CustomerRepository
from services.domain_event_service import DomainEventService
from services.order_service import OrderService


class CustomerService:

    @staticmethod
    def create_scoped_v1(
        db,
        principal: PrincipalContext,
        business_id: str,
        branch_id: str,
        payload,
        *,
        request_id: str | None,
    ):
        OrderService._scope(principal, business_id, branch_id)
        require_permission(principal, "customers.create")
        return CustomerService.create_v1(
            db, principal, business_id, branch_id, payload, request_id=request_id
        )

    @staticmethod
    def create_v1(
        db,
        principal: PrincipalContext,
        business_id: str,
        branch_id: str,
        payload,
        *,
        request_id: str | None,
    ):
        """Create one business-owned customer with a retry-safe client key."""
        existing = CustomerService._by_client_mutation(
            db, business_id, payload.client_mutation_id
        )
        if existing:
            return existing

        customer = Customer(
            id=str(uuid.uuid4()),
            business_id=business_id,
            name=payload.name,
            phone=payload.phone or "",
            email=payload.email,
            address=payload.address or "",
            balance_remaining=0,
            loyal_customer=payload.loyal_customer,
            preset_discount=payload.preset_discount,
            client_mutation_id=payload.client_mutation_id,
        )
        try:
            db.add(customer)
            DomainEventService.enqueue(
                db,
                event_type="customer.created",
                aggregate_type="customer",
                aggregate_id=customer.id,
                business_id=business_id,
                branch_id=branch_id,
                actor_id=principal.principal_id,
                data={
                    "client_mutation_id": payload.client_mutation_id,
                    "request_id": request_id,
                },
            )
            db.commit()
            db.refresh(customer)
            return customer
        except IntegrityError as exc:
            db.rollback()
            existing = CustomerService._by_client_mutation(
                db, business_id, payload.client_mutation_id
            )
            if existing:
                return existing
            raise DomainError(
                409,
                "CUSTOMER_CREATE_CONFLICT",
                "Customer creation could not be completed.",
            ) from exc

    @staticmethod
    def _by_client_mutation(db, business_id: str, client_mutation_id: str):
        return (
            db.query(Customer)
            .filter(
                Customer.business_id == business_id,
                Customer.client_mutation_id == client_mutation_id,
                Customer.is_deleted == False,
            )
            .first()
        )

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
            # Kept in the compatibility schema for old clients, but customer
            # profile writes must never overwrite the checkout-managed credit
            # balance. A ledger/reconciliation flow is a later phase.
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
            balance_remaining=0,
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
