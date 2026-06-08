# Staff Invite Authentication Flow

Staff identity is verified by Firebase Auth. Admin invite codes only authorize joining a business/branch.

## Flow

1. Admin creates an invite in VRIDDHI Billing.
2. Backend generates a 6-digit invite code and QR payload.
3. Staff opens VRIDDHI Staff Billing.
4. Staff signs in with Google or Apple via Firebase Auth.
5. Staff app sends Firebase ID token to FastAPI.
6. If the Firebase user is not linked, staff enters invite code or scans QR.
7. Backend verifies invite status, expiry, usage count, business, and branch.
8. Backend links Firebase UID/email to a staff account.
9. Backend returns VABOS tokens, staff profile, business profile, permissions, and feature flags.

## Firebase Login

```http
POST /staff/auth/firebase-login
Content-Type: application/json
```

```json
{
  "idToken": "firebase-id-token",
  "uid": "firebase-uid",
  "email": "staff@example.com",
  "displayName": "Staff Member",
  "provider": "google"
}
```

Unlinked response:

```json
{
  "status": "invite_required",
  "requiresInvite": true
}
```

Linked response:

```json
{
  "accessToken": "vabos-access-token",
  "refreshToken": "vabos-refresh-token",
  "staff": {
    "staffId": "12",
    "staffName": "Staff Member",
    "businessId": "biz_1",
    "branchId": "main",
    "role": "cashier"
  },
  "permissions": {
    "canCreateBill": true,
    "canCreateKot": false,
    "canUseBarcode": true
  },
  "featureFlags": {
    "kotEnabled": false,
    "barcodeEnabled": true,
    "holdBillEnabled": true
  }
}
```

## Accept Invite

```http
POST /staff/auth/accept-invite
Content-Type: application/json
```

```json
{
  "idToken": "firebase-id-token",
  "uid": "firebase-uid",
  "email": "staff@example.com",
  "displayName": "Staff Member",
  "provider": "google",
  "inviteCode": "492815"
}
```

Invalid invite:

```json
{
  "detail": "Invite is expired, used, or revoked"
}
```

Tokens are stored only in `flutter_secure_storage`. Database credentials never go to Flutter.
