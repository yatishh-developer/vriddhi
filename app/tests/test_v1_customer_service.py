from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from auth.errors import ApiError
from auth.principal import ActorType, PrincipalContext
from database.database import Base
from models.business_model import Business
from models.customer_model import Customer
from models.outbox_model import OutboxEvent
from schemas.customer_schema import CustomerResponse, V1CustomerCreate
from services.customer_service import CustomerService


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add_all([
        Business(id="business-a", name="Cafe", business_type="Restaurant"),
        Business(id="business-b", name="Other", business_type="Retail"),
    ])
    session.commit()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _principal(*, business_id="business-a", permissions=frozenset({"customers.create"}), branch_id=None):
    return PrincipalContext(
        principal_id=f"owner-{business_id}",
        actor_type=ActorType.OWNER,
        business_id=business_id,
        role="owner",
        user_id="owner-a",
        branch_id=branch_id,
        permissions=permissions,
        capabilities=frozenset({"orders"}),
    )


def _payload(key="customer-create-1"):
    return V1CustomerCreate(
        name="New customer",
        phone="9999999999",
        address="Main Street",
        preset_discount=5,
        client_mutation_id=key,
    )


def _error(callable_):
    with pytest.raises(ApiError) as exc:
        callable_()
    return exc.value.code


def test_scoped_customer_create_is_authorized_canonical_and_audited(db):
    customer = CustomerService.create_scoped_v1(
        db, _principal(), "business-a", "branch-a", _payload(), request_id="request-1"
    )

    response = CustomerResponse.model_validate(customer)
    event = db.query(OutboxEvent).filter(OutboxEvent.aggregate_id == customer.id).one()
    assert response.id == customer.id
    assert response.business_id == "business-a"
    assert response.balance_remaining == Decimal("0")
    assert customer.client_mutation_id == "customer-create-1"
    assert event.payload["actor_id"] == "owner-business-a"
    assert event.payload["branch_id"] == "branch-a"
    assert event.payload["data"]["request_id"] == "request-1"


def test_customer_create_enforces_permission_business_and_worker_branch_scope(db):
    assert _error(lambda: CustomerService.create_scoped_v1(
        db, _principal(permissions=frozenset()), "business-a", "branch-a", _payload(), request_id=None
    )) == "PERMISSION_DENIED"
    assert _error(lambda: CustomerService.create_scoped_v1(
        db, _principal(), "business-b", "branch-a", _payload(), request_id=None
    )) == "BUSINESS_ACCESS_DENIED"

    worker = PrincipalContext(
        principal_id="worker-a", actor_type=ActorType.WORKER, business_id="business-a",
        role="cashier", staff_id="worker-a", branch_id="branch-a",
        permissions=frozenset({"customers.create"}), capabilities=frozenset({"orders"}),
    )
    assert _error(lambda: CustomerService.create_scoped_v1(
        db, worker, "business-a", "branch-b", _payload(), request_id=None
    )) == "BRANCH_ACCESS_DENIED"


def test_customer_create_schema_is_strict_and_cannot_forge_balance():
    with pytest.raises(ValidationError):
        V1CustomerCreate(name="A", client_mutation_id="key", balance_remaining=1000)


def test_customer_create_idempotency_is_tenant_scoped_and_retry_safe(db):
    first = CustomerService.create_scoped_v1(
        db, _principal(), "business-a", "branch-a", _payload("same-key"), request_id=None
    )
    retry = CustomerService.create_scoped_v1(
        db, _principal(), "business-a", "branch-a", _payload("same-key"), request_id=None
    )
    another = CustomerService.create_scoped_v1(
        db, _principal(), "business-a", "branch-a", _payload("different-key"), request_id=None
    )
    other_tenant = CustomerService.create_scoped_v1(
        db, _principal(business_id="business-b"), "business-b", "branch-a", _payload("same-key"), request_id=None
    )

    assert first.id == retry.id
    assert another.id != first.id
    assert other_tenant.id != first.id
    assert db.query(Customer).filter(Customer.client_mutation_id == "same-key").count() == 2
    assert db.query(OutboxEvent).filter(OutboxEvent.event_type == "customer.created").count() == 3


def test_concurrent_customer_create_retries_commit_one_customer(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'customer-retry.db'}",
        connect_args={"check_same_thread": False, "timeout": 5},
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    setup = sessions()
    setup.add(Business(id="business-a", name="Cafe", business_type="Restaurant"))
    setup.commit()
    setup.close()
    barrier = Barrier(2)

    def create_once():
        session = sessions()
        try:
            barrier.wait()
            return CustomerService.create_scoped_v1(
                session,
                _principal(),
                "business-a",
                "branch-a",
                _payload("concurrent-key"),
                request_id=None,
            ).id
        finally:
            session.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        ids = list(executor.map(lambda _: create_once(), range(2)))

    verify = sessions()
    try:
        assert ids[0] == ids[1]
        assert verify.query(Customer).filter(Customer.client_mutation_id == "concurrent-key").count() == 1
    finally:
        verify.close()
        engine.dispose()
