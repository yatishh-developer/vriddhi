import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from auth.principal import ActorType, PrincipalContext
from database.database import Base
from fastapi.testclient import TestClient
from models.business_model import Business
from models.outbox_model import OutboxEvent
from models.user_model import User
from realtime.connection_manager import ConnectionManager
from services.domain_event_service import DomainEventService
from services.outbox_publisher import OutboxPublisher


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add_all([
        Business(id="business-a", name="Cafe", business_type="Restaurant"),
        User(id="owner-a", business_id="business-a", email="owner@example.com", password_hash="hash"),
    ])
    session.commit()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _event(db, event_type="order.created"):
    return DomainEventService.enqueue(
        db, event_type=event_type, aggregate_type="order", aggregate_id="order-a",
        business_id="business-a", branch_id="branch-a", data={"safe": True}, actor_id="owner-a",
    )


def test_domain_event_is_atomic_and_payload_has_no_credentials(db):
    _event(db)
    db.rollback()
    assert db.query(OutboxEvent).count() == 0

    event = _event(db)
    db.commit()
    persisted = db.get(OutboxEvent, event.id)
    assert persisted.status == "PENDING"
    assert persisted.payload["event_id"] == persisted.event_id
    assert "token" not in str(persisted.payload).lower()


def test_event_id_is_unique(db):
    first = _event(db)
    db.commit()
    duplicate = OutboxEvent(
        id="duplicate", event_id=first.event_id, event_type="order.created", aggregate_type="order",
        aggregate_id="order-b", business_id="business-a", branch_id="branch-a", payload={},
        status="PENDING", attempts=0, available_at=datetime.now(timezone.utc),
    )
    db.add(duplicate)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


class _RecordingTransport:
    def __init__(self, fail=False):
        self.fail = fail
        self.events = []

    async def publish(self, envelope):
        if self.fail:
            raise RuntimeError("redis unavailable")
        self.events.append(envelope)


def test_publisher_marks_success_and_delivery_is_at_least_once(db):
    event = _event(db)
    db.commit()
    transport = _RecordingTransport()
    publisher = OutboxPublisher(transport)
    assert asyncio.run(publisher.publish_once(db)) == 1
    persisted = db.get(OutboxEvent, event.id)
    assert persisted.status == "PUBLISHED"
    assert transport.events[0]["event_id"] == event.event_id
    # A crash after Redis accepted the message but before DB acknowledgement
    # can repeat this exact event_id; clients therefore dedupe it.
    assert transport.events[0]["event_id"] == event.event_id


def test_publisher_failure_is_retryable(db):
    event = _event(db)
    db.commit()
    publisher = OutboxPublisher(_RecordingTransport(fail=True))
    assert asyncio.run(publisher.publish_once(db)) == 0
    persisted = db.get(OutboxEvent, event.id)
    assert persisted.status == "PENDING"
    assert persisted.attempts == 1
    assert persisted.available_at is not None


def test_claim_prevents_second_worker_from_reclaiming_live_row(db):
    _event(db)
    db.commit()
    claimed = OutboxPublisher.claim(db)
    assert len(claimed) == 1
    assert OutboxPublisher.claim(db) == []


class _Socket:
    def __init__(self):
        self.messages = []
        self.closed = False

    async def accept(self):
        return None

    async def send_json(self, payload):
        self.messages.append(payload)

    async def close(self, code):
        self.closed = code == 4401


def test_local_manager_routes_only_authorized_branch_and_revokes_session():
    async def run():
        manager = ConnectionManager()
        owner = PrincipalContext(
            principal_id="owner-a", actor_type=ActorType.OWNER, business_id="business-a", branch_id="branch-a",
            role="owner", membership_id="member-a", session_id="session-a", permissions=frozenset({"*"}), capabilities=frozenset({"*"}),
        )
        foreign_branch = PrincipalContext(
            principal_id="owner-b", actor_type=ActorType.OWNER, business_id="business-a", branch_id="branch-b",
            role="owner", membership_id="member-b", session_id="session-b", permissions=frozenset({"*"}), capabilities=frozenset({"*"}),
        )
        first = await manager.connect(_Socket(), owner)
        second = await manager.connect(_Socket(), foreign_branch)
        event = {"event_id": "event-a", "type": "order.item_added", "business_id": "business-a", "branch_id": "branch-a", "data": {}}
        assert await manager.route(event) == 1
        assert len(first.websocket.messages) == 1
        assert not second.websocket.messages
        await manager.route({"event_id": "event-b", "type": "session.revoked", "business_id": "business-a", "branch_id": "branch-a", "data": {"session_id": "session-a"}})
        assert first.websocket.closed
    asyncio.run(run())


def test_unified_websocket_protocol_resync_ping_and_command_rejection(monkeypatch):
    from main import app
    import routes.realtime_routes as realtime_routes

    principal = PrincipalContext(
        principal_id="owner-a", actor_type=ActorType.OWNER, business_id="business-a", branch_id="branch-a",
        role="owner", permissions=frozenset({"*"}), capabilities=frozenset({"*"}),
    )

    class _Db:
        is_active = True
        def commit(self): pass
        def rollback(self): pass
        def close(self): pass

    monkeypatch.setattr(realtime_routes, "SessionLocal", _Db)
    monkeypatch.setattr(realtime_routes, "resolve_principal_from_token", lambda db, token: principal)
    with TestClient(app) as client:
        with client.websocket_connect("/api/v1/realtime", headers={"Authorization": "Bearer short-lived"}) as ws:
            assert ws.receive_json()["resync_required"] is True
            ws.send_json({"type": "ping"})
            assert ws.receive_json() == {"type": "pong"}
            ws.send_json({"type": "create_bill", "amount": 1})
            assert ws.receive_json()["code"] == "PROTOCOL_INVALID"
