"""Transactional domain-event helpers.

Events are intentionally added to the caller's SQLAlchemy session only.  The
domain service that changed state owns the single commit/rollback boundary.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from models.outbox_model import OutboxEvent


def _json_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


class DomainEventService:
    @staticmethod
    def enqueue(
        db: Session,
        *,
        event_type: str,
        aggregate_type: str,
        aggregate_id: str,
        business_id: str,
        branch_id: str | None,
        data: dict[str, Any] | None = None,
        actor_id: str | None = None,
    ) -> OutboxEvent:
        event_id = str(uuid4())
        occurred_at = datetime.now(timezone.utc)
        envelope = {
            "event_id": event_id,
            "type": event_type,
            "occurred_at": occurred_at.isoformat(),
            "business_id": business_id,
            "branch_id": branch_id,
            "aggregate": {"type": aggregate_type, "id": aggregate_id},
            "actor_id": actor_id,
            "data": _json_value(data or {}),
        }
        event = OutboxEvent(
            id=str(uuid4()), event_id=event_id, event_type=event_type,
            aggregate_type=aggregate_type, aggregate_id=aggregate_id,
            business_id=business_id, branch_id=branch_id, payload=envelope,
            status="PENDING", attempts=0, available_at=occurred_at,
        )
        db.add(event)
        return event
