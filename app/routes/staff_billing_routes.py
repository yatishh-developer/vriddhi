from typing import List

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Query
from fastapi import WebSocket
from fastapi import WebSocketDisconnect
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session

from auth.dependencies import get_current_user
from database.dependencies import get_db
from models.staff_billing_model import StaffHeldBill
from models.staff_billing_model import StaffKot
from models.staff_billing_model import StaffPayment
from models.staff_billing_model import StaffProcessLock
from models.staff_billing_model import StaffRealtimeEvent
from models.transaction_model import Transaction
from models.user_model import User
from schemas.product_schema import ProductResponse
from schemas.staff_billing_schema import RealtimeEventEnvelope
from schemas.staff_billing_schema import StaffAuthResponse
from schemas.staff_billing_schema import StaffBillCreate
from schemas.staff_billing_schema import StaffBillResponse
from schemas.staff_billing_schema import StaffHeldBillCreate
from schemas.staff_billing_schema import StaffHeldBillResponse
from schemas.staff_billing_schema import StaffInviteCreate
from schemas.staff_billing_schema import StaffInviteResponse
from schemas.staff_billing_schema import StaffInviteVerifyRequest
from schemas.staff_billing_schema import StaffKotCreate
from schemas.staff_billing_schema import StaffKotResponse
from schemas.staff_billing_schema import StaffKotUpdate
from schemas.staff_billing_schema import StaffMeResponse
from schemas.staff_billing_schema import StaffProcessClaimRequest
from schemas.staff_billing_schema import StaffProcessHeartbeatRequest
from schemas.staff_billing_schema import StaffProcessLockResponse
from schemas.staff_billing_schema import StaffProcessReleaseRequest
from schemas.staff_billing_schema import StaffRefreshRequest
from schemas.staff_billing_schema import StaffSyncPullResponse
from schemas.staff_billing_schema import StaffSyncPushRequest
from schemas.staff_billing_schema import StaffSyncPushResponse
from schemas.staff_billing_schema import StaffTokenResponse
from services.staff_billing_service import STAFF_SOURCE_APP
from services.staff_billing_service import StaffBillingService
from services.staff_billing_service import staff_realtime_manager


router = APIRouter(tags=["Staff Billing"])
bearer_scheme = HTTPBearer(auto_error=True)


def get_current_staff(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
):
    return StaffBillingService.staff_from_token(db, credentials.credentials)


def _invite_response(invite, invite_code=None):
    return {
        "id": invite.id,
        "business_id": invite.business_id,
        "business_name": invite.business_name,
        "business_type": invite.business_type_snapshot,
        "branch_id": invite.branch_id,
        "staff_name": invite.staff_name,
        "staff_role": invite.staff_role,
        "invite_code": invite_code,
        "expires_at": invite.expires_at,
        "max_uses": invite.max_uses,
        "used_count": invite.used_count,
        "status": invite.status,
    }


@router.post("/staff/admin/invites", response_model=StaffInviteResponse)
def create_staff_invite(
    payload: StaffInviteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    invite, invite_code = StaffBillingService.create_invite(db, current_user, payload)
    return _invite_response(invite, invite_code)


@router.get("/staff/admin/invites", response_model=List[StaffInviteResponse])
def list_staff_invites(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return [_invite_response(invite) for invite in StaffBillingService.list_invites(db, current_user)]


@router.post("/staff/admin/invites/{invite_id}/revoke", response_model=StaffInviteResponse)
def revoke_staff_invite(
    invite_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    invite = StaffBillingService.revoke_invite(db, current_user, invite_id)
    return _invite_response(invite)


@router.get("/staff/admin/bills", response_model=List[StaffBillResponse])
def admin_staff_bills(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return (
        db.query(Transaction)
        .filter(
            Transaction.business_id == current_user.business_id,
            Transaction.source_app == STAFF_SOURCE_APP,
        )
        .order_by(Transaction.created_at.desc())
        .limit(300)
        .all()
    )


@router.get("/staff/admin/kots", response_model=List[StaffKotResponse])
def admin_staff_kots(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return (
        db.query(StaffKot)
        .filter(StaffKot.business_id == current_user.business_id)
        .order_by(StaffKot.created_at.desc())
        .limit(300)
        .all()
    )


@router.get("/staff/admin/held-bills", response_model=List[StaffHeldBillResponse])
def admin_staff_held_bills(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return (
        db.query(StaffHeldBill)
        .filter(StaffHeldBill.business_id == current_user.business_id)
        .order_by(StaffHeldBill.created_at.desc())
        .limit(300)
        .all()
    )


@router.get("/staff/admin/payments")
def admin_staff_payments(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    payments = (
        db.query(StaffPayment)
        .filter(StaffPayment.business_id == current_user.business_id)
        .order_by(StaffPayment.created_at.desc())
        .limit(300)
        .all()
    )
    return [StaffBillingService._sa_to_dict(payment) for payment in payments]


@router.get("/staff/admin/processes", response_model=List[StaffProcessLockResponse])
def admin_staff_processes(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return (
        db.query(StaffProcessLock)
        .filter(StaffProcessLock.business_id == current_user.business_id)
        .order_by(StaffProcessLock.updated_at.desc())
        .limit(300)
        .all()
    )


@router.get("/staff/admin/events")
def admin_staff_events(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    events = (
        db.query(StaffRealtimeEvent)
        .filter(StaffRealtimeEvent.business_id == current_user.business_id)
        .order_by(StaffRealtimeEvent.created_at.desc())
        .limit(300)
        .all()
    )
    return [StaffBillingService._sa_to_dict(event) for event in events]


@router.post("/staff/auth/verify-invite-code", response_model=StaffAuthResponse)
def verify_staff_invite_code(
    payload: StaffInviteVerifyRequest,
    db: Session = Depends(get_db),
):
    return StaffBillingService.verify_invite_code(
        db,
        payload.invite_code,
        payload.device_id,
    )


@router.post("/staff/auth/refresh", response_model=StaffTokenResponse)
def refresh_staff_access_token(
    payload: StaffRefreshRequest,
    db: Session = Depends(get_db),
):
    return {
        "access_token": StaffBillingService.refresh_staff_token(db, payload.refresh_token),
        "token_type": "bearer",
    }


@router.post("/staff/auth/logout")
def staff_logout(
    staff=Depends(get_current_staff),
    db: Session = Depends(get_db),
):
    staff.last_seen_at = None
    db.commit()
    return {"message": "Logged out"}


@router.get("/staff/me", response_model=StaffMeResponse)
def staff_me(
    staff=Depends(get_current_staff),
    db: Session = Depends(get_db),
):
    return StaffBillingService.staff_profile_payload(db, staff)


@router.get("/staff/products", response_model=List[ProductResponse])
def staff_products(
    staff=Depends(get_current_staff),
    db: Session = Depends(get_db),
):
    return StaffBillingService.list_products(db, staff)


@router.get("/staff/categories", response_model=List[str])
def staff_categories(
    staff=Depends(get_current_staff),
    db: Session = Depends(get_db),
):
    return StaffBillingService.list_categories(db, staff)


@router.get("/staff/kots", response_model=List[StaffKotResponse])
def staff_kots(
    staff=Depends(get_current_staff),
    db: Session = Depends(get_db),
):
    return StaffBillingService.list_kots(db, staff)


@router.post("/staff/kots", response_model=StaffKotResponse)
def create_staff_kot(
    payload: StaffKotCreate,
    staff=Depends(get_current_staff),
    db: Session = Depends(get_db),
):
    return StaffBillingService.create_kot(db, staff, payload)


@router.patch("/staff/kots/{kot_id}", response_model=StaffKotResponse)
def update_staff_kot(
    kot_id: str,
    payload: StaffKotUpdate,
    staff=Depends(get_current_staff),
    db: Session = Depends(get_db),
):
    return StaffBillingService.update_kot(db, staff, kot_id, payload)


@router.post("/staff/kots/{kot_id}/convert-to-bill", response_model=StaffBillResponse)
def convert_staff_kot_to_bill(
    kot_id: str,
    payload: StaffBillCreate,
    staff=Depends(get_current_staff),
    db: Session = Depends(get_db),
):
    return StaffBillingService.convert_kot_to_bill(db, staff, kot_id, payload)


@router.get("/staff/bills", response_model=List[StaffBillResponse])
def staff_bills(
    staff=Depends(get_current_staff),
    db: Session = Depends(get_db),
):
    return StaffBillingService.list_bills(db, staff)


@router.post("/staff/bills", response_model=StaffBillResponse)
def create_staff_bill(
    payload: StaffBillCreate,
    staff=Depends(get_current_staff),
    db: Session = Depends(get_db),
):
    return StaffBillingService.create_bill(db, staff, payload)


@router.get("/staff/held-bills", response_model=List[StaffHeldBillResponse])
def staff_held_bills(
    staff=Depends(get_current_staff),
    db: Session = Depends(get_db),
):
    return StaffBillingService.list_held_bills(db, staff)


@router.post("/staff/held-bills", response_model=StaffHeldBillResponse)
def create_staff_held_bill(
    payload: StaffHeldBillCreate,
    staff=Depends(get_current_staff),
    db: Session = Depends(get_db),
):
    return StaffBillingService.create_held_bill(db, staff, payload)


@router.post("/staff/held-bills/{held_bill_id}/resume", response_model=StaffHeldBillResponse)
def resume_staff_held_bill(
    held_bill_id: str,
    staff=Depends(get_current_staff),
    db: Session = Depends(get_db),
):
    return StaffBillingService.resume_held_bill(db, staff, held_bill_id)


@router.post("/staff/sync/push", response_model=StaffSyncPushResponse)
def staff_sync_push(
    payload: StaffSyncPushRequest,
    staff=Depends(get_current_staff),
    db: Session = Depends(get_db),
):
    accepted = 0
    duplicates = 0
    errors = []
    for event in payload.events:
        try:
            created = StaffBillingService.persist_realtime_event(db, staff, event)
            if created:
                accepted += 1
            else:
                duplicates += 1
        except HTTPException as exc:
            db.rollback()
            errors.append(f"{event.event_id}: {exc.detail}")
        except Exception as exc:
            db.rollback()
            errors.append(f"{event.event_id}: {exc}")
    return {"accepted": accepted, "duplicates": duplicates, "errors": errors}


@router.get("/staff/sync/pull", response_model=StaffSyncPullResponse)
def staff_sync_pull(
    since: str | None = Query(None),
    staff=Depends(get_current_staff),
    db: Session = Depends(get_db),
):
    # The first production sync returns the current branch payload. Incremental
    # `since` filtering can be enabled after every sync entity has indexed
    # updated_at metadata.
    return StaffBillingService.pull_sync_payload(db, staff)


@router.post("/staff/processes/claim", response_model=StaffProcessLockResponse)
def claim_staff_process(
    payload: StaffProcessClaimRequest,
    staff=Depends(get_current_staff),
    db: Session = Depends(get_db),
):
    return StaffBillingService.claim_process(db, staff, payload)


@router.post("/staff/processes/release", response_model=StaffProcessLockResponse)
def release_staff_process(
    payload: StaffProcessReleaseRequest,
    staff=Depends(get_current_staff),
    db: Session = Depends(get_db),
):
    return StaffBillingService.release_process(db, staff, payload.process_id, payload.status)


@router.post("/staff/processes/heartbeat", response_model=StaffProcessLockResponse)
def heartbeat_staff_process(
    payload: StaffProcessHeartbeatRequest,
    staff=Depends(get_current_staff),
    db: Session = Depends(get_db),
):
    return StaffBillingService.heartbeat_process(db, staff, payload.process_id, payload.ttl_seconds)


@router.get("/staff/processes/active", response_model=List[StaffProcessLockResponse])
def active_staff_processes(
    staff=Depends(get_current_staff),
    db: Session = Depends(get_db),
):
    return StaffBillingService.list_active_processes(db, staff)


@router.websocket("/ws/staff")
async def staff_websocket(
    websocket: WebSocket,
    token: str = Query(...),
    db: Session = Depends(get_db),
):
    try:
        principal = StaffBillingService.websocket_principal_from_token(db, token)
    except HTTPException:
        await websocket.close(code=4401)
        return

    business_id = principal["business_id"]
    await staff_realtime_manager.connect(websocket, business_id)
    await websocket.send_json(
        {
            "event_type": "connection.ready",
            "business_id": business_id,
            "branch_id": principal.get("branch_id", "main"),
            "principal_type": principal["principal_type"],
        }
    )
    try:
        while True:
            message = await websocket.receive_json()
            if message.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
                continue

            if "event_id" in message and principal["principal_type"] == "staff":
                staff = principal["staff"]
                event = RealtimeEventEnvelope(
                    event_id=message["event_id"],
                    event_type=message.get("event_type", "sync.required"),
                    entity_type=message.get("entity_type", "unknown"),
                    entity_id=message.get("entity_id", message["event_id"]),
                    business_id=message.get("business_id"),
                    branch_id=message.get("branch_id"),
                    staff_id=message.get("staff_id"),
                    device_id=message.get("device_id"),
                    occurred_at=message.get("occurred_at"),
                    payload=message.get("payload") or {},
                )
                created = StaffBillingService.persist_realtime_event(db, staff, event)
                message["duplicate"] = not created

            await staff_realtime_manager.broadcast_business(business_id, message)
    except WebSocketDisconnect:
        staff_realtime_manager.disconnect(websocket)
    except Exception as exc:
        db.rollback()
        await websocket.send_json({"event_type": "connection.error", "detail": str(exc)})
        staff_realtime_manager.disconnect(websocket)
