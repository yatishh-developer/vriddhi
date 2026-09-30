"""Unified, notification-only realtime WebSocket endpoint.

Clients authenticate with the normal short-lived access JWT in the
Authorization header.  A dedicated one-time ticket can be added later without
changing the event protocol; permanent tokens are deliberately not accepted in
the query string.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from auth.dependencies import resolve_principal_from_token
from auth.errors import AuthError
from database.database import SessionLocal


router = APIRouter()
ALLOWED_MESSAGES = {"ping", "subscribe", "unsubscribe", "ack"}
ALLOWED_SUBSCRIPTIONS = {"kitchen", "orders", "tables", "inventory"}


def _bearer_token(websocket: WebSocket) -> str:
    header = websocket.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise AuthError(401, "TOKEN_MISSING", "Bearer authentication is required.")
    return token


@router.websocket("/api/v1/realtime")
async def realtime(websocket: WebSocket) -> None:
    db = SessionLocal()
    try:
        principal = resolve_principal_from_token(db, _bearer_token(websocket))
        db.commit()
    except AuthError:
        db.rollback()
        await websocket.close(code=4401)
        return
    finally:
        db.close()

    manager = websocket.app.state.realtime_manager
    connection = await manager.connect(websocket, principal)
    await websocket.send_json({
        "type": "realtime.connected",
        "resync_required": True,
        "business_id": principal.business_id,
        "branch_id": principal.branch_id,
    })
    try:
        while True:
            message = await websocket.receive_json()
            if not isinstance(message, dict) or set(message) - {"type", "subscription", "event_id"}:
                await websocket.send_json({"type": "realtime.error", "code": "PROTOCOL_INVALID"})
                continue
            message_type = message.get("type")
            if message_type not in ALLOWED_MESSAGES:
                await websocket.send_json({"type": "realtime.error", "code": "COMMANDS_NOT_ALLOWED"})
                continue
            if message_type == "ping":
                await websocket.send_json({"type": "pong"})
                continue
            if message_type == "ack":
                continue
            subscription = message.get("subscription")
            if subscription not in ALLOWED_SUBSCRIPTIONS:
                await websocket.send_json({"type": "realtime.error", "code": "SUBSCRIPTION_DENIED"})
                continue
            # Business and branch are always derived from PrincipalContext;
            # clients cannot request an arbitrary business/order channel.
            if message_type == "subscribe":
                connection.subscriptions.add(subscription)
            else:
                connection.subscriptions.discard(subscription)
            await websocket.send_json({"type": "realtime.subscription", "subscription": subscription, "active": message_type == "subscribe"})
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(connection)
