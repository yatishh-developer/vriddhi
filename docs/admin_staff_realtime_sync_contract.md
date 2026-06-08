# Admin Staff Realtime Sync Contract

Connections are VABOS token based. Clients join scoped rooms only after authentication.

## Rooms

```text
business:{businessId}
branch:{branchId}
staff:{staffId}
device:{deviceId}
```

## Requirements

- Reconnect with backoff.
- Heartbeat/ping.
- Event idempotency through `eventId`.
- Local event log.
- Offline fallback through sync queue.
- No duplicate bills/KOTs; every mutating action must carry an idempotency key.

## Admin To Staff Events

```json
{
  "eventId": "evt_001",
  "type": "business.feature_flags.updated",
  "businessId": "biz_1",
  "branchId": "main",
  "payload": {
    "featureFlags": {
      "kotEnabled": false,
      "barcodeEnabled": true
    }
  },
  "createdAt": "2026-06-07T10:00:00Z"
}
```

Supported event types:

- `staff.invite.created`
- `staff.permissions.updated`
- `staff.revoked`
- `business.feature_flags.updated`
- `product.created`
- `product.updated`
- `product.deleted`
- `menu.updated`
- `price.updated`
- `kot.updated`
- `bill.updated`
- `sync.required`

## Staff To Admin Events

```json
{
  "eventId": "evt_101",
  "type": "kot.created",
  "businessId": "biz_1",
  "branchId": "main",
  "staffId": "12",
  "payload": {
    "localId": "kot-local-1",
    "idempotencyKey": "idem-1"
  },
  "createdAt": "2026-06-07T10:02:00Z"
}
```

Supported event types:

- `staff.online`
- `staff.offline`
- `kot.created`
- `kot.updated`
- `kot.converted_to_bill`
- `bill.created`
- `held_bill.created`
- `held_bill.resumed`
- `payment.collected`
- `sync.status.changed`
