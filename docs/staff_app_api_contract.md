# Staff App API Contract

All staff app calls go to FastAPI. Flutter never receives Supabase credentials.

## Create Invite

```http
POST /staff/invites
Authorization: Bearer admin-token
```

```json
{
  "businessId": "biz_1",
  "branchId": "main",
  "role": "cashier",
  "permissions": {
    "canCreateBill": true,
    "canHoldBill": true,
    "canUseBarcode": true
  },
  "expiresInHours": 168,
  "maxUses": 1
}
```

```json
{
  "id": "invite_123",
  "businessId": "biz_1",
  "branchId": "main",
  "role": "cashier",
  "inviteCode": "492815",
  "inviteQrPayload": "vabos-staff-invite://biz_1/main/492815",
  "status": "active"
}
```

## Sync Products

```http
GET /staff/menu
Authorization: Bearer vabos-token
```

```json
{
  "businessId": "biz_1",
  "branchId": "main",
  "categories": [],
  "products": []
}
```

## Create KOT

```http
POST /staff/kots
Authorization: Bearer vabos-token
Idempotency-Key: idem-kot-1
```

```json
{
  "localId": "kot-local-1",
  "orderType": "dineIn",
  "tableNumber": "T4",
  "items": [
    { "productId": "p1", "name": "Tea", "quantity": 2, "price": 20 }
  ]
}
```

## Convert KOT To Bill

```http
POST /staff/kots/kot-local-1/convert-to-bill
Authorization: Bearer vabos-token
Idempotency-Key: idem-convert-1
```

```json
{
  "paymentBreakdown": { "cash": 40, "upi": 0, "card": 0 }
}
```

Rules:

- Already converted KOT cannot convert again.
- Cancelled KOT cannot convert.

## Create Bill

```http
POST /staff/bills
Authorization: Bearer vabos-token
Idempotency-Key: idem-bill-1
```

```json
{
  "localId": "bill-local-1",
  "items": [],
  "paymentBreakdown": { "cash": 120, "upi": 0, "card": 0 }
}
```

## Hold Bill

```http
POST /staff/held-bills
Authorization: Bearer vabos-token
Idempotency-Key: idem-hold-1
```

```json
{
  "localId": "hold-local-1",
  "items": [],
  "customerName": "Walk-in"
}
```

Staff app saves locally first, queues the action, then syncs in the background.
