import asyncio
import json
import logging
from typing import Any

from core.config import settings


logger = logging.getLogger("vriddhi.realtime")
EVENT_PATTERN = "business:*"


def channels_for(envelope: dict[str, Any]) -> list[str]:
    """Return one authoritative transport channel per event.

    The local manager does final principal/subscription filtering.  Publishing
    a branch event to several overlapping Redis channels would manufacture
    duplicate deliveries before the client even encounters normal at-least-
    once retries.
    """
    business_id = envelope["business_id"]
    branch_id = envelope.get("branch_id")
    if branch_id:
        return [f"business:{business_id}:branch:{branch_id}"]
    return [f"business:{business_id}"]


class RedisRuntime:
    """One app-managed async Redis client; no in-memory distributed fallback."""

    def __init__(self) -> None:
        self.client: Any | None = None
        self.enabled = settings.REDIS_ENABLED
        self.connected = False
        self.subscriber_healthy = not self.enabled
        self._subscriber_task: asyncio.Task | None = None

    async def start(self, manager) -> None:
        if not self.enabled:
            logger.info("Redis realtime is disabled by configuration")
            return
        try:
            import redis.asyncio as redis
            self.client = redis.from_url(settings.REDIS_URL, decode_responses=True)
            await self.client.ping()
            self.connected = True
            self._subscriber_task = asyncio.create_task(self._subscribe(manager))
        except Exception as exc:
            self.connected = False
            self.subscriber_healthy = False
            logger.error("Redis realtime unavailable: %s", exc)
            if settings.ENVIRONMENT.lower() == "production":
                raise RuntimeError("Redis is required for production realtime") from exc

    async def stop(self) -> None:
        if self._subscriber_task:
            self._subscriber_task.cancel()
            try:
                await self._subscriber_task
            except asyncio.CancelledError:
                pass
        if self.client:
            await self.client.aclose()
        self.connected = False

    async def publish(self, envelope: dict[str, Any]) -> None:
        if not self.connected or not self.client:
            raise RuntimeError("Redis realtime is unavailable")
        message = json.dumps(envelope, separators=(",", ":"), default=str)
        for channel in channels_for(envelope):
            await self.client.publish(channel, message)

    async def increment(self, key: str, window_seconds: int) -> int:
        if not self.connected or not self.client:
            raise RuntimeError("Redis rate limiter is unavailable")
        async with self.client.pipeline(transaction=True) as pipe:
            pipe.incr(key)
            pipe.expire(key, window_seconds, nx=True)
            result = await pipe.execute()
        return int(result[0])

    async def _subscribe(self, manager) -> None:
        """Reconnect on Redis interruption without taking down the API process."""
        while self.connected and self.client:
            pubsub = self.client.pubsub()
            try:
                await pubsub.psubscribe(EVENT_PATTERN)
                self.subscriber_healthy = True
                async for message in pubsub.listen():
                    if message.get("type") not in {"message", "pmessage"}:
                        continue
                    try:
                        envelope = json.loads(message["data"])
                        if envelope.get("event_id") and envelope.get("business_id"):
                            await manager.route(envelope)
                    except (TypeError, ValueError, KeyError):
                        logger.warning("Discarded malformed realtime event")
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.subscriber_healthy = False
                logger.warning("Redis subscriber disconnected: %s", exc)
                await asyncio.sleep(1)
            finally:
                await pubsub.aclose()
