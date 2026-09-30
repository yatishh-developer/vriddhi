import asyncio
from dataclasses import dataclass, field
from typing import Any

from fastapi import WebSocket

from auth.principal import PrincipalContext


@dataclass(eq=False)
class RealtimeConnection:
    websocket: WebSocket
    principal: PrincipalContext
    subscriptions: set[str] = field(default_factory=set)


class ConnectionManager:
    """Tracks only sockets owned by this process; Redis distributes globally."""

    def __init__(self) -> None:
        self._connections: set[RealtimeConnection] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, principal: PrincipalContext) -> RealtimeConnection:
        await websocket.accept()
        connection = RealtimeConnection(websocket=websocket, principal=principal)
        async with self._lock:
            self._connections.add(connection)
        return connection

    async def disconnect(self, connection: RealtimeConnection) -> None:
        async with self._lock:
            self._connections.discard(connection)

    async def route(self, envelope: dict[str, Any]) -> int:
        """Deliver only to matching business/branch sockets, best-effort."""
        business_id = envelope.get("business_id")
        branch_id = envelope.get("branch_id")
        event_type = envelope.get("type", "")
        async with self._lock:
            connections = list(self._connections)
        delivered = 0
        for connection in connections:
            principal = connection.principal
            if principal.business_id != business_id:
                continue
            if principal.branch_id and branch_id and principal.branch_id != branch_id:
                continue
            data = envelope.get("data") or {}
            if event_type == "membership.permissions_changed" and data.get("membership_id") != principal.membership_id:
                continue
            if event_type == "session.revoked" and data.get("session_id") != principal.session_id:
                continue
            if event_type.startswith("kot.") and connection.subscriptions and "kitchen" not in connection.subscriptions:
                continue
            try:
                await connection.websocket.send_json(envelope)
                delivered += 1
                if event_type == "session.revoked":
                    await connection.websocket.close(code=4401)
                    await self.disconnect(connection)
            except Exception:
                await self.disconnect(connection)
        return delivered
