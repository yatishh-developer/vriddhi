import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_
from sqlalchemy.orm import Session

from core.config import settings
from database.database import SessionLocal
from models.outbox_model import OutboxEvent


logger = logging.getLogger("vriddhi.outbox")


class OutboxPublisher:
    """Publishes committed events at-least-once; clients must dedupe event_id."""

    def __init__(self, transport) -> None:
        self.transport = transport
        self.healthy = True
        self.last_error: str | None = None

    @staticmethod
    def claim(db: Session, limit: int = 50) -> list[OutboxEvent]:
        now = datetime.now(timezone.utc)
        expired_lease = now - timedelta(seconds=settings.OUTBOX_LEASE_SECONDS)
        query = db.query(OutboxEvent).filter(
            or_(
                (OutboxEvent.status == "PENDING") & (OutboxEvent.available_at <= now),
                (OutboxEvent.status == "PROCESSING") & (OutboxEvent.locked_at <= expired_lease),
            )
        ).order_by(OutboxEvent.created_at).limit(limit)
        # PostgreSQL uses SKIP LOCKED; SQLite accepts the semantic fallback.
        rows = query.with_for_update(skip_locked=True).all()
        for row in rows:
            row.status = "PROCESSING"
            row.locked_at = now
            row.attempts += 1
        db.commit()
        return rows

    @staticmethod
    def mark_published(db: Session, event_id: str) -> None:
        row = db.query(OutboxEvent).filter(OutboxEvent.id == event_id).with_for_update().one()
        row.status = "PUBLISHED"
        row.published_at = datetime.now(timezone.utc)
        row.locked_at = None
        row.last_error = None
        db.commit()

    @staticmethod
    def mark_failed(db: Session, event_id: str, error: Exception) -> None:
        row = db.query(OutboxEvent).filter(OutboxEvent.id == event_id).with_for_update().one()
        retry_seconds = min(300, 2 ** min(row.attempts, 8))
        row.status = "PENDING"
        row.locked_at = None
        row.available_at = datetime.now(timezone.utc) + timedelta(seconds=retry_seconds)
        row.last_error = str(error)[:500]
        db.commit()

    @staticmethod
    def cleanup_published(db: Session, retention_days: int | None = None) -> int:
        """Retention is explicit and conservative; pending events are never deleted."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days or settings.OUTBOX_RETENTION_DAYS)
        deleted = db.query(OutboxEvent).filter(
            OutboxEvent.status == "PUBLISHED", OutboxEvent.published_at < cutoff,
        ).delete(synchronize_session=False)
        db.commit()
        return deleted

    async def publish_once(self, db: Session | None = None, limit: int | None = None) -> int:
        owns_session = db is None
        db = db or SessionLocal()
        count = 0
        try:
            events = self.claim(db, limit or settings.OUTBOX_BATCH_SIZE)
            for event in events:
                try:
                    await self.transport.publish(event.payload)
                    self.mark_published(db, event.id)
                    count += 1
                except Exception as exc:
                    self.healthy = False
                    self.last_error = str(exc)
                    logger.warning("Outbox publish failed event_id=%s: %s", event.event_id, exc)
                    self.mark_failed(db, event.id, exc)
            if not events or count:
                self.healthy = True
                self.last_error = None
            return count
        finally:
            if owns_session:
                db.close()

    async def run(self, stopping: asyncio.Event) -> None:
        while not stopping.is_set():
            await self.publish_once()
            try:
                await asyncio.wait_for(stopping.wait(), timeout=settings.OUTBOX_POLL_INTERVAL_SECONDS)
            except asyncio.TimeoutError:
                pass
