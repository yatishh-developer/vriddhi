# VRIDDHI Staff Billing API Contract

Flutter apps call the FastAPI backend only. They must never contain Supabase
database credentials, service keys, or direct PostgreSQL URLs.

Production database is Postgres behind FastAPI:

```env
DATABASE_URL=postgresql+asyncpg://<USER>:<PASSWORD>@<HOST>:<PORT>/<DATABASE>?ssl=require
```

Store the real password only in backend environment secrets.

## Tenant Rules

Every backend query must use the authenticated staff context:

- `business_id`
- `branch_id`
- `staff_id`
- permissions

Tables are isolated by `business_id` and `branch_id`; backend routes must filter
by both unless a branch-wide or business-wide admin route is explicitly designed.
Do not create unauthenticated public policies.

## Endpoints

### POST `/auth/staff/login`

Request:

```json
{
  "loginId": "cashier@example.com",
  "password": "staff-password"
}
```

Response:

```json
{
  "accessToken": "jwt",
  "refreshToken": "refresh-token",
  "staff": {
    "staffId": "staff_123",
    "staffName": "Cashier",
    "businessId": "biz_123",
    "branchId": "branch_123",
    "counterId": "counter_1",
    "role": "cashier",
    "permissions": {
      "canCreateKot": true,
      "canConvertKotToBill": true,
      "canCollectPayment": true,
      "canPrintBill": false,
      "canCancelKot": false,
      "canViewOwnBillsOnly": true
    }
  }
}
```

### POST `/auth/refresh`

Request:

```json
{ "refreshToken": "refresh-token" }
```

Response:

```json
{ "accessToken": "jwt", "refreshToken": "refresh-token" }
```

### GET `/staff/me`

Returns authenticated staff profile and permissions. Backend filters by token.

### GET `/staff/menu`

Returns categories and products visible to the staff member's `business_id` and
`branch_id`.

### GET `/staff/kots`

Query params: `status`, `mineOnly`, `tableNumber`.

### POST `/staff/kots`

Creates a KOT. Request must include `idempotencyKey`.

### PATCH `/staff/kots/{id}`

Updates KOT status/items if permission allows. Backend must reject updates across
business or branch boundaries.

### POST `/staff/kots/{id}/convert-to-bill`

Converts once only. Backend must reject already converted or cancelled KOTs.

### GET `/staff/bills`

Returns branch bills. If `canViewOwnBillsOnly` is true, backend filters by
authenticated `staff_id`.

### POST `/staff/bills`

Creates quick bill without KOT if permission allows.

### POST `/staff/sync/batch`

Request:

```json
{
  "items": [
    {
      "idempotencyKey": "uuid",
      "entityType": "kot",
      "entityId": "local-id",
      "action": "create",
      "payload": {}
    }
  ]
}
```

Response:

```json
{
  "results": [
    {
      "idempotencyKey": "uuid",
      "status": "synced",
      "serverId": "kot_123"
    }
  ]
}
```

### GET `/staff/sync/pull`

Pulls server changes since `syncVersion` or timestamp.

### WebSocket `/ws/staff`

Authenticated with access token. Staff joins:

- `business:{businessId}`
- `branch:{branchId}`
- `staff:{staffId}`
- `device:{deviceId}` when assigned
