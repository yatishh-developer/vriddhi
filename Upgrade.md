# VRIDDHI Backend — Verified Repository Status

Audit date: 2026-10-01. Scope is the code under `app/` only. This is a code audit, not a claim that a deployed environment, database state, or Flutter client has been exercised. No application code was changed.

## 1. Repository overview

| Area | Verified implementation |
|---|---|
| Framework | FastAPI 0.136.3 / Starlette, served by Uvicorn |
| Python | 3.11 in `app/Dockerfile` |
| Validation | Pydantic 2.13.4 schemas; defaults do not set `extra="forbid"`, so Pydantic’s default extra-field-ignore behavior applies |
| ORM / DB | SQLAlchemy 2.0.50 synchronous ORM; PostgreSQL via psycopg 3.3.4 is the intended production database |
| Schema evolution | `Base.metadata.create_all()` at startup plus imperative PostgreSQL DDL in `services/staff_billing_migration.py`; Alembic environment exists but has zero version scripts |
| Admin authentication | Email/password, bcrypt, HS256 JWT bearer token; one access token type, default lifetime 1,440 minutes |
| Staff authentication | Invite-code flow and staff JWTs; an advertised Firebase path accepts an unverified UID or unverified JWT claims (see finding SEC-01) |
| Authorization | Per-staff JSON permission map and feature flags; ordinary authenticated-user routes have no separate role/permission layer |
| Realtime | One `/ws/staff` WebSocket and an in-process, business-keyed connection manager |
| Cache / Redis | No Redis, cache, or shared pub/sub implementation |
| Background workers | None found |
| Offline / sync | Product/customer/transaction queue upload; product timestamp pull; staff snapshot push/pull |
| Tests | pytest; one test module containing 12 tests |
| Lint / type check | No configured ruff, flake8, mypy, pyright, or formatter configuration found |
| Deployment | Slim Python Docker image, Uvicorn `--workers 2`, Docker Compose service with external environment file |

Actual layout:

```text
app/
  auth/                 JWT/password dependencies and helpers
  core/                 configuration and timestamp/soft-delete mixins
  database/             engine, session dependency
  models/               15 SQLAlchemy table models
  schemas/              Pydantic request/response models
  repositories/         basic product/customer/transaction/inventory queries
  services/             domain logic, billing, sync, subscriptions
  routes/               10 FastAPI router modules
  middleware/           logging and in-memory rate limiter
  exception_handlers/   catch-all 500 response
  alembic/              env.py only; no versions
  tests/                staff-billing service tests
```

## 2. Repository statistics

| Metric | Verified count / status |
|---|---:|
| Python files under `app/` | 64 |
| Route files | 10 |
| API paths (unique method-independent paths) | 58 |
| HTTP operations | 72 |
| GET / POST / PUT / PATCH / DELETE | 33 / 30 / 3 / 3 / 3 |
| WebSocket endpoints | 1 |
| SQLAlchemy model classes / DB tables | 15 / 15 |
| Enum classes excluded from table count | 1 (`InventoryMovementType`) |
| Alembic version migrations | 0 |
| Service modules / repository modules | 13 / 6 |
| Pydantic model classes | 54 (including shared nested request/response models) |
| Test files / test cases | 2 / 12 |
| Staff permission keys | 15 default keys; arbitrary custom keys are accepted |
| Realtime transport event types | No closed registry; event type is free-form string |
| Sync endpoints | 4 (`/products/sync`, upload, staff push, staff pull) |
| Subscription/payment endpoints | 7 subscription endpoints; 2 Razorpay subscription-payment endpoints |
| KOT endpoints | 5 staff KOT operations including admin list and conversion |
| Customer endpoints | 5 CRUD operations |
| Inventory endpoints | 2 |
| Direct POS payment endpoints | 0; staff payment is created inside staff bill creation |

Counts were derived from FastAPI decorators and model declarations, not from README material.

## 3. Complete endpoint inventory

Auth is `Admin JWT`, `Staff JWT`, `Public`, or `None`. “Permission” is the effective service check; `—` means no distinct permission beyond authentication. `Strict` means a Pydantic model is present, not that extra fields are forbidden. DB lists the principal tables touched. Status is a code-based assessment.

### Auth, root, business, dashboard

| Method | Path | Handler | Auth / permission | Request → response | DB | Status |
|---|---|---|---|---|---|---|
| GET | `/` | `read_root` | None / — | — → raw dict | — | Working |
| GET | `/health` | `health_check` | None / — | — → raw dict | DB probe | Partial |
| POST | `/auth/signup` | `signup` | Public / — | `SignupRequest` → `TokenResponse` | businesses, users | Partial |
| POST | `/auth/login` | `login` | Public / — | OAuth2 form → raw dict | users, businesses | Partial |
| GET | `/business/` | `get_business` | Admin JWT / self only | — → `BusinessResponse` | businesses | Working |
| PUT | `/business/` | `update_business` | Admin JWT / self only | `BusinessUpdate` → `BusinessResponse` | businesses | Partial |
| GET | `/dashboard/summary` | `get_dashboard_summary` | Admin JWT / tenant | — → `DashboardSummaryResponse` | products, customers, transactions | Partial |

### Products, customers, inventory, transactions

| Method | Path | Handler | Auth / permission | Request → response | DB | Status |
|---|---|---|---|---|---|---|
| GET | `/products/sync` | `get_products_for_sync` | Admin JWT / tenant | `last_sync` query → `ProductResponse[]` | products | Partial |
| POST | `/products/sync/upload` | `upload_queue` | Admin JWT / tenant | `list[dict]` → raw dict | products, customers, transactions | Unsafe |
| GET | `/products/` | `get_products` | Admin JWT / tenant | — → `ProductResponse[]` | products | Working |
| POST | `/products/` | `create_product` | Admin JWT / tenant | `ProductCreate` → `ProductResponse` | products | Partial |
| GET | `/products/barcode/{barcode}` | `get_product_by_barcode` | Admin JWT / tenant | path → `ProductResponse` | products | Working |
| GET | `/products/{product_id}` | `get_product` | Admin JWT / tenant | path → `ProductResponse` | products | Working |
| PUT | `/products/{product_id}` | `update_product` | Admin JWT / tenant | `ProductUpdate` → `ProductResponse` | products | Partial |
| DELETE | `/products/{product_id}` | `delete_product` | Admin JWT / tenant | path → raw dict | products | Partial |
| GET | `/customers/` | `get_customers` | Admin JWT / tenant | — → `CustomerResponse[]` | customers | Working |
| POST | `/customers/` | `create_customer` | Admin JWT / tenant | `CustomerCreate` → `CustomerResponse` | customers | Partial |
| GET | `/customers/{customer_id}` | `get_customer` | Admin JWT / tenant | path → `CustomerResponse` | customers | Working |
| PUT | `/customers/{customer_id}` | `update_customer` | Admin JWT / tenant | `CustomerUpdate` → `CustomerResponse` | customers | Unsafe |
| DELETE | `/customers/{customer_id}` | `delete_customer` | Admin JWT / tenant | path → raw dict | customers | Partial |
| GET | `/inventory/movements` | `get_inventory_movements` | Admin JWT / tenant | — → `InventoryMovementResponse[]` | inventory_movements | Partial |
| POST | `/inventory/adjust` | `adjust_inventory` | Admin JWT / tenant | `InventoryAdjustRequest` → `InventoryMovementResponse` | products, inventory_movements | Unsafe |
| GET | `/transactions/` | `get_transactions` | Admin JWT / tenant | — → `TransactionResponse[]` | transactions | Partial |
| POST | `/transactions/` | `create_transaction` | Admin JWT / tenant | `CreateTransactionRequest` → `TransactionResponse` | transactions, transaction_items, products | Unsafe |
| GET | `/transactions/{transaction_id}` | `get_transaction` | Admin JWT / tenant | path → `TransactionResponse` | transactions | Working |
| DELETE | `/transactions/{transaction_id}` | `delete_transaction` | Admin JWT / tenant | path → raw dict | transactions, transaction_items | Unsafe |

### Staff administration and staff authentication

| Method | Path | Handler | Auth / permission | Request → response | DB | Status |
|---|---|---|---|---|---|---|
| POST | `/staff/admin/invites` | `create_staff_invite` | Admin JWT / tenant | `StaffInviteCreate` → `StaffInviteResponse` | staff_invites, businesses | Partial |
| GET | `/staff/admin/invites` | `list_staff_invites` | Admin JWT / tenant | — → `StaffInviteResponse[]` | staff_invites | Working |
| GET | `/staff/admin/invites/{invite_id}` | `get_staff_invite` | Admin JWT / tenant | path → `StaffInviteResponse` | staff_invites | Working |
| PATCH | `/staff/admin/invites/{invite_id}` | `update_staff_invite` | Admin JWT / tenant | `StaffInviteUpdate` → `StaffInviteResponse` | staff_invites | Partial |
| POST | `/staff/admin/invites/{invite_id}/revoke` | `revoke_staff_invite` | Admin JWT / tenant | path → `StaffInviteResponse` | staff_invites | Working |
| GET | `/staff/admin/staff` | `list_admin_staff_accounts` | Admin JWT / tenant | — → `StaffProfileAdminResponse[]` | staff_profiles | Working |
| GET | `/staff/admin/staff/{staff_id}` | `get_admin_staff_account` | Admin JWT / tenant | path → `StaffProfileAdminResponse` | staff_profiles | Working |
| PATCH | `/staff/admin/staff/{staff_id}` | `update_admin_staff_account` | Admin JWT / tenant | `StaffProfileAdminUpdate` → `StaffProfileAdminResponse` | staff_profiles | Partial |
| GET | `/staff/admin/bills` | `admin_staff_bills` | Admin JWT / tenant | — → `StaffBillResponse[]` | transactions | Partial |
| GET | `/staff/admin/kots` | `admin_staff_kots` | Admin JWT / tenant | — → `StaffKotResponse[]` | staff_kots | Partial |
| GET | `/staff/admin/held-bills` | `admin_staff_held_bills` | Admin JWT / tenant | — → `StaffHeldBillResponse[]` | staff_held_bills | Partial |
| GET | `/staff/admin/payments` | `admin_staff_payments` | Admin JWT / tenant | — → raw dict[] | staff_payments | Partial |
| GET | `/staff/admin/processes` | `admin_staff_processes` | Admin JWT / tenant | — → `StaffProcessLockResponse[]` | staff_process_locks | Partial |
| GET | `/staff/admin/events` | `admin_staff_events` | Admin JWT / tenant | — → raw dict[] | staff_realtime_events | Partial |
| POST | `/staff/auth/verify-invite-code` | `verify_staff_invite_code` | Public / invite code | `StaffInviteVerifyRequest` → `StaffAuthResponse` | staff_invites, staff_profiles | Unsafe |
| POST | `/staff/auth/verify` | `verify_staff_invite_code_alias` | Public / invite code | same → `StaffAuthResponse` | same | Unsafe alias |
| POST | `/auth/staff/verify-invite-code` | `verify_staff_invite_code_legacy_alias` | Public / invite code | same → `StaffAuthResponse` | same | Unsafe alias |
| POST | `/staff/auth/firebase-login` | `firebase_staff_login` | Public / UID asserted by client | `StaffFirebaseLoginRequest` → raw dict | staff_profiles | Unsafe |
| POST | `/staff/auth/accept-invite` | `accept_staff_invite_after_firebase_auth` | Public / UID + invite | `StaffFirebaseInviteAcceptRequest` → `StaffAuthResponse` | staff_profiles, staff_invites | Unsafe |
| POST | `/staff/auth/refresh` | `refresh_staff_access_token` | Refresh JWT / staff active | `StaffRefreshRequest` → `StaffTokenResponse` | staff_profiles | Partial |
| POST | `/staff/auth/logout` | `staff_logout` | Staff JWT / active app | — → raw dict | staff_profiles | Partial |
| GET | `/staff/me` | `staff_me` | Staff JWT / active app | — → `StaffMeResponse` | staff_profiles, businesses | Working |

### Staff billing, KOT, held bills, sync, process locks, realtime

| Method | Path | Handler | Auth / permission | Request → response | DB | Status |
|---|---|---|---|---|---|---|
| GET | `/staff/products` | `staff_products` | Staff JWT / active app | — → `ProductResponse[]` | products | Partial |
| GET | `/staff/categories` | `staff_categories` | Staff JWT / active app | — → `str[]` | products | Partial |
| GET | `/staff/kots` | `staff_kots` | Staff JWT / active app | — → `StaffKotResponse[]` | staff_kots | Working |
| POST | `/staff/kots` | `create_staff_kot` | Staff JWT / `create_kot` | `StaffKotCreate` → `StaffKotResponse` | staff_kots | Unsafe |
| PATCH | `/staff/kots/{kot_id}` | `update_staff_kot` | Staff JWT / cancellation only checked | `StaffKotUpdate` → `StaffKotResponse` | staff_kots | Unsafe |
| POST | `/staff/kots/{kot_id}/convert-to-bill` | `convert_staff_kot_to_bill` | Staff JWT / `convert_kot_to_bill` | `StaffBillCreate` → `StaffBillResponse` | staff_kots, transactions, items, payments, inventory, customers | Partial |
| GET | `/staff/bills` | `staff_bills` | Staff JWT / active app | — → `StaffBillResponse[]` | transactions | Working |
| POST | `/staff/bills` | `create_staff_bill` | Staff JWT / `create_bill`, credit permission | `StaffBillCreate` → `StaffBillResponse` | transactions, transaction_items, staff_payments, inventory_movements, products, customers | Unsafe |
| GET | `/staff/held-bills` | `staff_held_bills` | Staff JWT / active app | — → `StaffHeldBillResponse[]` | staff_held_bills | Working |
| POST | `/staff/held-bills` | `create_staff_held_bill` | Staff JWT / `hold_bill` | `StaffHeldBillCreate` → `StaffHeldBillResponse` | staff_held_bills | Unsafe |
| POST | `/staff/held-bills/{held_bill_id}/resume` | `resume_staff_held_bill` | Staff JWT / `resume_held_bill` | path → `StaffHeldBillResponse` | staff_held_bills | Partial |
| POST | `/staff/sync/push` | `staff_sync_push` | Staff JWT / event owner & tenant checks | `StaffSyncPushRequest` → `StaffSyncPushResponse` | staff_realtime_events | Partial |
| GET | `/staff/sync/pull` | `staff_sync_pull` | Staff JWT / active app | `since` query → `StaffSyncPullResponse` | products, KOTs, held bills, bills, events | Unsafe |
| POST | `/staff/processes/claim` | `claim_staff_process` | Staff JWT / active app | `StaffProcessClaimRequest` → `StaffProcessLockResponse` | staff_process_locks | Partial |
| POST | `/staff/processes/release` | `release_staff_process` | Staff JWT / lock holder | `StaffProcessReleaseRequest` → `StaffProcessLockResponse` | staff_process_locks | Partial |
| POST | `/staff/processes/heartbeat` | `heartbeat_staff_process` | Staff JWT / lock holder | `StaffProcessHeartbeatRequest` → `StaffProcessLockResponse` | staff_process_locks | Partial |
| GET | `/staff/processes/active` | `active_staff_processes` | Staff JWT / active app | — → `StaffProcessLockResponse[]` | staff_process_locks | Partial |
| WS | `/ws/staff` | `staff_websocket` | JWT query token / staff or admin | free-form JSON → free-form JSON | staff_realtime_events (staff-sent envelopes) | Unsafe |

### Subscriptions

| Method | Path | Handler | Auth / permission | Request → response | DB / external | Status |
|---|---|---|---|---|---|---|
| GET | `/subscriptions/plans` | `get_plans` | Public / — | — → `PlanFeatures[]` | in-code catalog | Working |
| GET | `/subscriptions/me` | `get_my_subscription` | Admin JWT / self | — → `SubscriptionResponse` | subscriptions | Partial |
| POST | `/subscriptions/subscribe` | `subscribe` | Admin JWT / self | `SubscribeRequest` → `SubscriptionResponse` | subscriptions | Unsafe for paid plans |
| POST | `/subscriptions/cancel` | `cancel` | Admin JWT / self | — → `SubscriptionResponse` | subscriptions | Partial |
| POST | `/subscriptions/usage` | `record_usage` | Admin JWT / self | `UsageRecordRequest` → `SubscriptionResponse` | subscriptions | Unsafe |
| POST | `/subscriptions/create-order` | `create_payment_order` | Admin JWT / self | `CreateOrderRequest` → `CreateOrderResponse` | Razorpay | Partial |
| POST | `/subscriptions/verify-payment` | `verify_payment` | Admin JWT / self | `VerifyPaymentRequest` → `SubscriptionResponse` | Razorpay, subscriptions | Unsafe |

## 4. Actual workflow maps

### Admin authentication

`POST /auth/login` → `UserRepository.get_by_email` (global email lookup) → bcrypt verification → query business → HS256 JWT (`sub`, `business_id`, `exp`) → response. No refresh token, session table, token identifier, logout/revocation list, email verification, password policy, or login throttling dedicated to credentials.

### Admin transaction / billing

`POST /transactions/` → admin JWT → idempotency lookup by `(business_id, idempotency_key)` → existing ID updates payload totals without touching items/stock, otherwise create `Transaction` → if structured `items` is nonempty: read each product scoped by business, use product price to calculate only `total_amount`, create `TransactionItem`, decrement stock with `max(0, ...)` → one commit → response.

Expected but missing: authoritative tax/discount/payment calculations, stock row locks, insufficient-stock rejection, inventory movement records, customer-credit update, branch authorization, cancellation/reversal behavior, and an outbox/realtime event.

### Staff bill and payment

`POST /staff/bills` → staff JWT resolves active profile → allowed-app check → feature/permission merge → deserialize `items_json` if needed → basic amount/credit/quantity validation → lookup idempotency key → create `Transaction` → `flush()` → lock each referenced product, add `TransactionItem`, decrement stock and add `InventoryMovement` → add `StaffPayment` → lock/update customer balance when credit is supplied → one commit → response.

This is one ORM transaction and is materially stronger than the admin flow. It nevertheless stores supplied totals, item price/subtotal, tax, discount and old balance rather than deriving the full bill from product data.

### KOT and KOT → bill

`POST /staff/kots` → staff feature/`create_kot` permission → optional idempotency lookup → save free-form item snapshot, client totals, optional `table_token`, status `pending` → commit. `PATCH` permits mutable items/totals and any declared status; only cancellation is permission-gated. Conversion loads the KOT by business+branch, uses its snapshot/totals only when bill fields are omitted/zero, calls the staff bill method (which commits), then changes KOT to `converted` and commits again.

### Held bill

`POST /staff/held-bills` → staff permission → optional idempotency lookup → persist item snapshot and supplied totals → commit. Resume merely changes `status` to `resumed`; there is no endpoint that finalizes that held-bill record alongside creating a bill, so it remains disconnected from the bill flow.

### Inventory

Manual adjustment: read product by business → calculate new quantity → commit product through repository → create/commit movement through repository. These are two commits, so a movement failure leaves stock changed. Admin transactions decrement with no movement record or lock; staff bills decrement with product row locks and movement records. Product update can also directly set stock with no movement record.

### Realtime and offline sync

WebSocket: query-token JWT → accept socket → add to process-local map by business only → broadcast any received JSON to all business sockets. Staff messages carrying an event envelope are persisted first. Branch is included in the welcome message but is not a broadcast partition. With the Docker image’s two Uvicorn workers, only sockets connected to the same worker receive a broadcast.

Product pull uses `updated_at >= last_sync` if ISO parsing succeeds; malformed input is silently ignored and returns all products. Queue upload accepts arbitrary dictionaries and independently commits through lower services. Staff pull ignores `since` completely and returns bounded current snapshots (products unbounded, most staff lists/events capped), not an incremental cursor feed.

## 5. Request JSON / validation audit

All Pydantic models accept/ignore unknown fields by default; there is no `extra="forbid"`. Nested `permissions`, `feature_flags`, event `payload`, `items_json`, and upload entries are structurally open where noted.

| Mutation endpoint / group | Request classification | Extra fields | Arbitrary nested JSON | Risk |
|---|---|---|---|---|
| `/auth/signup` | PARTIALLY STRICT | ignored | no | Medium: no password policy |
| `/business/` PUT | PARTIALLY STRICT | ignored | no | Low |
| Product create/update | PARTIALLY STRICT | ignored | no | Medium: price/stock bounds not enforced |
| `/products/sync/upload` | OPEN JSON | yes | entire request | High |
| Customer create/update | PARTIALLY STRICT | ignored | no | High: balance is client-writable |
| `/inventory/adjust` | PARTIALLY STRICT | ignored | no | Medium: lacks branch/source provenance |
| `/transactions/` | PARTIALLY STRICT | ignored | `items_json` free string | Critical: financial fields are client supplied |
| Staff invite/profile create/update | PARTIALLY STRICT | ignored | `permissions: Dict[str, Any]` | Medium |
| Staff invite verification | PARTIALLY STRICT | ignored | no | High: creates identity on verification |
| Firebase staff endpoints | PARTIALLY STRICT | ignored | ID token claims used unverified | Critical |
| `/staff/bills` and KOT conversion payload | PARTIALLY STRICT | ignored | `items_json: Any`; item price/totals supplied | Critical |
| `/staff/kots` create/update | PARTIALLY STRICT | ignored | `items_json: Any` | High |
| Held-bill create | PARTIALLY STRICT | ignored | `items_json: Any` | High |
| Staff sync push | PARTIALLY STRICT | ignored | envelope `payload: Dict[str, Any]` | Medium |
| WebSocket messages | OPEN JSON | yes | entire message | High |
| Process lock mutations | PARTIALLY STRICT | ignored | no | Medium |
| Subscription mutations | PARTIALLY STRICT | ignored | no | High: paid direct subscription and client usage count |

Text columns named `*_json` are not DB JSON/JSONB and have no database-level schema. `items_json` is normalized neither for transactions nor KOT/held bill; only `TransactionItem` exists for structured admin/staff item payloads. `permissions_json`, `feature_flags_snapshot`, `payment_json`, and `payload_json` are parsed with a broad `safe_json_loads` that substitutes a default on malformed data.

## 6. Response contract audit

61/73 route decorators declare `response_model`; 12 do not. Missing contracts include login, root/health, product upload, deletion responses, staff Firebase login/logout, admin staff payments/events, WebSocket, and raw sync outcomes. Staff admin payment/event and staff sync data are generated by `_sa_to_dict`, which serializes every model column and lets the response schema use `Dict[str, Any]`; these are not stable API contracts.

ORM return values with explicit Pydantic response models use `from_attributes`. Status codes are almost entirely default `200`; successful creates do not declare `201`, deletes do not declare `204`, and conflict semantics are inconsistent. The global exception handler returns a generic safe 500, but queue endpoints catch broad exceptions and return exception strings to the caller. No source review found password hash leakage through a response model.

## 7. Authentication audit

Admin tokens use configured `JWT_SECRET`, HS256 by default, `exp`, and `sub`. `get_current_user` verifies signature/expiry then loads the user. Passwords use bcrypt. There are no refresh tokens for admins, no token IDs, deny list, session/device binding, forced revocation, or logout endpoint.

Staff access and refresh JWTs are the same signing scheme and same configured expiry. A staff profile is checked for active status and allowed app on use, so disabled/revoked profile state blocks future use. “Logout” only clears `last_seen_at`; it does not invalidate a token. Invite code hashes are SHA-256 of normalized code plus the JWT secret, are 6/8 digits, and are globally queried.

Firebase Admin is present only in requirements; no `firebase_admin.auth.verify_id_token` call exists. `_firebase_uid_from_payload` accepts `payload.uid` directly or calls `jwt.get_unverified_claims` on `id_token`. This is not Firebase authentication and permits identity assertion by a client.

## 8. Authorization and tenant isolation audit

Ordinary routes use an authenticated `User` and consistently pass `current_user.business_id` to repositories. There is no role field on `User`, no admin permission definitions, and no service-level permission checks for products, customers, inventory, transactions, business, or subscriptions; every authenticated owner-level user is equivalent.

Staff routes enforce active profile/allowed-app. Bill/KOT/held-bill permissions use a JSON map merged over defaults. Not all actions have a specific check: reading products/categories/kots/bills/held bills and editing non-cancelled KOT fields relies on broad staff authentication. Admin staff-management endpoints require an admin JWT but no distinct `manage_staff` permission.

Business filtering is present for primary object access. Staff objects usually include business+branch; admin staff list endpoints intentionally span all branches in their business. There is no `branches` table, branch membership model, branch foreign key, branch-scoped user auth, composite ownership constraint, or PostgreSQL row-level security. `branch_id` is free text and is client supplied on admin transaction writes. The WebSocket broadcasts at business scope rather than branch scope.

## 9. Database model audit

| Table | Key tenant / relationships | Financial / JSON / lifecycle notes |
|---|---|---|
| `businesses` | PK id | Profile and tax settings; no soft delete |
| `users` | PK id; business FK; globally unique email | bcrypt `password_hash`; no role/session fields |
| `products` | PK id; business FK | float price/GST, stock fields, soft delete; barcode uniqueness only added by runtime PostgreSQL DDL |
| `customers` | PK id; business FK | float balance/preset discount, soft delete |
| `transactions` | PK id; business/customer/user FKs; free-text branch | all POS money float; `items_json` Text; item relationship cascade; idempotency runtime unique index only |
| `transaction_items` | PK id; transaction/product FKs | float price/subtotal; normalized child items |
| `inventory_movements` | PK id; business/product/user FKs | branch/source/sync free text; no transaction FK (reference string only) |
| `subscriptions` | PK id; one unique business FK | float plan price; period/status/counters |
| `staff_invites` | PK id; business/user FKs | Text permissions/apps/feature snapshot; code hash globally unique |
| `staff_profiles` | PK id; business/invite/user FKs | Text permissions/apps; globally unique Firebase UID |
| `staff_kots` | PK id; business/staff/transaction/user FKs | Text item snapshot, float totals, table token, statuses; runtime idempotency index |
| `staff_held_bills` | PK id; business/staff/customer/transaction/user FKs | Text items, float totals, statuses; runtime idempotency index |
| `staff_payments` | PK id; business/staff/transaction/user FKs | float split values, Text payment snapshot |
| `staff_process_locks` | PK process id; business/staff/user FKs | leases with timestamps/status; global PK process key |
| `staff_realtime_events` | PK event id; business/staff/user FKs | free event type/entity/payload JSON-in-Text; processed flag |

All money-bearing persistent fields use `Float`; none use `Numeric`/`Decimal`. Most primary keys are client-provided strings or UUID defaults. Only `Customer` and `Product` use the provided soft-delete mixin. Most tables inherit created/updated timestamps, but `InventoryMovement` supplies only `created_at`.

## 10. Financial, inventory, KOT, billing, atomicity, idempotency audit

### Financial data

`GSTService` performs Decimal intermediate arithmetic but converts each result to float; it is not invoked by either billing creation path. Admin structured items calculate `total_amount` from product prices but trust all other totals and payment values. Admin snapshot-only transactions trust every financial field. Staff billing validates nonnegative payment amounts, payment coverage, credit customer requirement, and item quantities, but persists supplied subtotal/tax/discount/old balance/item price/item subtotal/total. It does not compare product price or GST to the request. Customer balance is directly writable in customer CRUD and only staff credit increments it; admin credit flow does not update it.

### Inventory source of truth

There are three incompatible stock writers: product update directly overwrites quantity; manual adjustment changes stock and creates a movement in two commits; admin transactions decrement in-memory with no movement and clamp negatives to zero; staff bills lock products, reject insufficient stock, and append sales movements in the same commit. Transaction delete and queue delete do not restore inventory, reverse customer credit, or append compensating movements. No cancellation/refund flow was found.

### KOT architecture

`StaffKot` has `table_token` (free text) rather than a table/session/order FK. It stores all items in `items_json` Text, not normalized KOT/order items. Lifecycle allows `pending`, `preparing`, `ready`, `served`, `converted`, `cancelled`, but does not validate legal transition order. There is no printer integration, KOT cancel endpoint, item-level status, kitchen role, outbox event, or multi-KOT parent order. KOT creation does not reserve/deduct stock; conversion invokes billing, where staff stock is deducted.

### Billing-flow comparison

| Behavior | Admin transaction | Staff bill | KOT conversion | Held bill |
|---|---|---|---|---|
| Price validation | product price only when structured items | no product-price comparison | staff behavior | none |
| GST / discount / old balance | client fields trusted | client fields trusted; simple payment arithmetic | supplied/KOT fallback | client fields stored |
| Customer credit | no balance update | locked customer balance increment | staff behavior | no action |
| Inventory | no lock, no movement, clamp to zero | locked, movement record, reject insufficient | staff behavior | none |
| Idempotency | lookup only; runtime DB index not scope-compatible with lookup | lookup plus runtime PostgreSQL index | deterministic KOT key | lookup plus runtime index |
| Payment record | none | `StaffPayment` | staff behavior | none |
| Commit behavior | one commit, no rollback wrapper | one commit | creates bill commit then KOT commit | one commit |
| Realtime event | none | none | none | none |

### Atomicity, concurrency and idempotency

The staff bill write is a single commit after `flush()` and uses `with_for_update()` on products and credit customer. KOT conversion is not atomic because `create_bill()` commits before the KOT linkage commit. Manual inventory adjustment uses two commits. Admin transaction does one commit but does not lock inventory. Generic session dependency only closes a session; it does not roll back exceptions.

PostgreSQL startup DDL creates partial unique indexes for transactions `(business_id, branch_id, source_app, idempotency_key)`, KOTs `(business_id, branch_id, idempotency_key)`, held bills `(business_id, branch_id, idempotency_key)`, event IDs, and Firebase UID. The Python model metadata does not express these indexes, tests use fresh metadata without them, and runtime migration execution is required. Admin transaction idempotency lookup omits branch and source-app despite the index scope. There is no response replay store/expiry or idempotency coverage for manual inventory, payments as independent operations, process claims, product/customer mutations, invite acceptance, or subscription payment verification. Process claims use read-then-insert/update without a row lock; concurrent claims can fail or race.

## 11. Realtime, offline sync, migrations, errors and security

**Realtime:** `StaffRealtimeConnectionManager` is in-memory, tracks only `business_id`, and has no Redis, persistence-to-delivery link, retry, acknowledgement, ordering, or reconnection cursor. Event persistence is separate from broadcasting. Multi-instance compatibility: **NO**. Even the supplied two-worker container is incompatible with complete fan-out.

**Offline:** Product pull is timestamp filtering with inclusive comparison and no cursor/version/tombstone. Product upload is a best-effort list of arbitrary dicts; each entity action may commit independently and failures include exception text. Transaction queue delete physically deletes a transaction with no compensating accounting. Staff push deduplicates only by global event ID. Staff pull ignores `since`; it returns a current bounded snapshot and is therefore a full-sync endpoint presented as incremental sync.

**Migrations:** Application lifespan first calls `create_all`, then runs manual additive PostgreSQL DDL. `alembic/env.py` imports all models but no revision scripts exist. Startup DDL drops constraints/indexes and applies schema changes at runtime, which is operationally risky under multiple workers/deploys and can drift from model metadata. No database RLS is defined in code.

**Errors:** expected failures mostly raise `HTTPException`; global unhandled failures are generic 500. There is no centralized `IntegrityError` mapping to 409. Broad exception handling silently hides invalid product `last_sync`, leaks individual sync exception strings, and sends exception detail on WebSocket `connection.error`. No structured request correlation or audit log exists.

**Security:** Parameterized SQLAlchemy queries and the fixed `SELECT 1` query show no direct SQL injection path. CORS hosts/origins are configurable, but defaults allow any host and an empty origin list (browser behavior must be deployment-tested). Rate limiting is process-local and trusts forwarded headers, so it is neither shared nor safe behind arbitrary proxies. No sensitive password logging was found. Major security/data-integrity risks are recorded below.

## 12. Test audit

Command that passed:

```text
JWT_SECRET=audit-test-secret DATABASE_URL=postgresql+psycopg://audit:audit@127.0.0.1:5432/audit pytest -q app/tests
```

Result: **12 passed in 2.38s**. `python -m compileall -q app` also passed.

The test module covers staff feature flags, invite hash normalization, alias parsing, some bill payment validation, staff allowed-app enforcement, and one SQLite staff-bill creation/idempotency path. It does not exercise FastAPI routes, admin auth, Firebase verification, tenant/branch isolation, normal transactions, inventory adjustment/deletion, KOT transitions/conversion rollback, held bills, subscriptions/Razorpay, WebSocket, sync cursoring, manual migration DDL, rate limiting, or concurrent requests.

An initial SQLite-configured test invocation failed during collection because `database.py` always passes `pool_size`, `max_overflow`, and `pool_timeout`, which SQLite’s `SingletonThreadPool` rejects. The passing command uses a PostgreSQL URL only to construct the application engine; individual DB tests create a separate in-memory SQLite engine.

## 13. Bug register

| ID | Severity | Type / area | Evidence | Impact | Recommended fix |
|---|---|---|---|---|---|
| SEC-01 | CRITICAL | Security risk: staff Firebase auth | `firebase_login` finds profile by UID; `_firebase_uid_from_payload` accepts caller UID or unverified token claims | Impersonation of an active staff UID and staff JWT issuance | Verify Firebase ID token with Admin SDK, require issuer/audience/signature, bind verified UID, add auth tests |
| FIN-01 | CRITICAL | Data integrity: client-authoritative bills | `CreateTransactionRequest` and `StaffBillCreate` accept totals/taxes/prices; only partial calculations/validation occur | Manipulated bill amounts, tax, discounts, payments, and receipt values | Centralize Decimal pricing/tax/discount calculation from server product snapshots |
| INV-01 | CRITICAL | Data integrity: admin stock | Admin transaction uses no lock, records no movement, and clamps negative stock | Overselling and irreconcilable inventory | Row-lock products, reject insufficient stock, add movement and transactional outbox |
| FIN-02 | HIGH | Accounting reversal | Transaction deletion/queue deletion physically remove records without restoring stock/credit/movements | Historical and inventory corruption | Disallow deletion of finalized bills; create void/refund compensating entries |
| KOT-01 | HIGH | KOT integrity | KOT has free-form Text items/totals/table token and arbitrary status changes | No reliable order/table/KOT lifecycle; values can be altered | Normalize order/KOT items, legal transition guard, server calculated totals |
| SYNC-01 | HIGH | Offline sync | Staff pull ignores `since`; queue upload is arbitrary JSON and independent commits | Duplicate/lost/conflicting writes and inefficient full sync | Cursor/event sequence, schemas, idempotency, transactional batch behavior |
| RT-01 | HIGH | Realtime isolation/scale | in-process manager keyed only by business; Docker runs two workers | Branch leakage and missed messages across workers | Branch authorization plus DB outbox and Redis/shared pub-sub |
| PAY-01 | HIGH | Subscription payment | Verify signature does not persist/order-bind server-created order; direct `/subscribe` activates paid plan; usage is client reported | Plan activation and metering can be spoofed | Persist provider order intent and status, bind plan/business, remove paid direct activation, server-meter use |
| IDP-01 | MEDIUM | Idempotency | runtime-only indexes; lookup scopes differ; no replay/expiry | Race errors/duplicate side effects and inconsistent offline retries | Metadata/Alembic constraints and universal idempotency service |
| INV-02 | MEDIUM | Manual inventory atomicity | product save commits before movement insert | Stock changed with no audit movement on second failure | One unit of work, row lock/version, movement constraint |
| FIN-03 | MEDIUM | Customer balance | CRUD permits arbitrary balance; admin credit does not update it | Credit ledger not authoritative | Append-only customer ledger and restricted service updates |
| AUTH-01 | MEDIUM | Session control | 24-hour default staff/admin token, no revocation; logout only clears timestamp | Lost tokens remain usable | Short access / rotating refresh tokens, session records/revocation |
| MIG-01 | MEDIUM | Schema deployment | `create_all` plus runtime ALTER/DROP DDL; zero Alembic revisions | Drift and unsafe production startup | Establish Alembic baseline and deploy migrations once |
| VAL-01 | MEDIUM | Open JSON / contracts | queue, event payloads, item JSON and raw dict response paths | Mass-assignment-like ambiguity and client contract drift | Strict envelope/item models; `extra=forbid`; response models |
| CON-01 | LOW | Process lock races | claim is read-then-write, no row lock/retry | Competing staff claims can conflict | Unique business/branch/process key and `FOR UPDATE`/upsert |
| QA-01 | LOW | Test portability/coverage | SQLite engine config fails on collection; only 12 service tests | Regression risk, no route/security coverage | Test configuration engine and broaden integration/concurrency suite |

Finding tally: **3 Critical, 5 High, 6 Medium, 2 Low**.

## 14. Production readiness snapshot

| Area | Status | Verified reason |
|---|---|---|
| Authentication | PARTIAL | bcrypt/JWT exist; staff Firebase flow is unsafe and no revocation |
| Authorization | PARTIAL | staff permission map exists; no user roles and inconsistent endpoint checks |
| Tenant isolation | PARTIAL | business filters common; branch is free text/no RLS and WebSocket is business-wide |
| Billing | NOT READY | separate engines and client-authoritative financial values |
| Payments | PARTIAL | Razorpay HMAC exists, but order binding/persistence and POS payment integrity are incomplete |
| Inventory | NOT READY | divergent writers, no admin lock/movement, no reversal |
| KOT | PARTIAL | basic staff KOT exists, but no normalized order/table lifecycle |
| Realtime | NOT READY | in-process manager fails with configured multi-worker deployment |
| Offline | NOT READY | snapshot pull/ignored cursor and open JSON queue |
| Migrations | NOT READY | no Alembic revisions; runtime DDL/create_all |
| Tests | PARTIAL | 12 focused passing tests only |
| Observability | PARTIAL | request/error logging and health check, no metrics/tracing/audit outbox |
| Concurrency | PARTIAL | staff bill locks products/customer; other critical flows do not |
| Data integrity | NOT READY | Float money, client totals, destructive transaction deletion |

## 15. Current workflow diagrams

```text
ADMIN BILLING
Flutter → POST /transactions → admin JWT → TransactionService
→ optional product reads + in-memory stock decrement → commit → response

STAFF BILLING
Flutter → POST /staff/bills → staff JWT + permissions → validate request
→ create transaction + flush → lock products/create items/movements
→ create StaffPayment → lock/update customer credit → commit → response

KOT CREATION
Flutter → POST /staff/kots → staff feature/permission → save JSON snapshot/totals
→ commit → response

KOT → BILL
Flutter → convert endpoint → load KOT → fill bill payload from KOT
→ staff bill (commit) → mark KOT converted (second commit) → response

HELD BILL
Flutter → POST held-bill → save snapshot/totals → commit
→ POST resume → status=resumed → commit; no linked finalization flow

CREDIT / PAY LATER
Staff bill with credit → require credit permission + customer id
→ lock customer → increment float balance → same bill commit

INVENTORY
Admin bill: decrement/no movement/no lock
Staff bill: lock product → decrement → append SALE movement → commit
Manual adjustment: commit product → commit movement

REALTIME
Client WS → JWT query token → per-process business socket list
→ optional persisted staff event → broadcast to same process/business sockets

OFFLINE SYNC
Admin queue → POST arbitrary list → per-item service commits/errors
Staff pull with `since` → ignored → current snapshots/events
```
