import hashlib
import json
import secrets
import uuid
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

from fastapi import HTTPException
from fastapi import WebSocket
from jose import JWTError
from jose import jwt
from sqlalchemy.orm import Session

from auth.security import create_access_token
from core.config import settings
from models.business_model import Business
from models.inventory_movement_model import InventoryMovement
from models.inventory_movement_model import InventoryMovementType
from models.product_model import Product
from models.staff_billing_model import StaffHeldBill
from models.staff_billing_model import StaffInvite
from models.staff_billing_model import StaffKot
from models.staff_billing_model import StaffPayment
from models.staff_billing_model import StaffProcessLock
from models.staff_billing_model import StaffProfile
from models.staff_billing_model import StaffRealtimeEvent
from models.transaction_item_model import TransactionItem
from models.transaction_model import Transaction
from models.user_model import User
from schemas.staff_billing_schema import RealtimeEventEnvelope
from schemas.staff_billing_schema import StaffBillCreate
from schemas.staff_billing_schema import StaffHeldBillCreate
from schemas.staff_billing_schema import StaffInviteCreate
from schemas.staff_billing_schema import StaffKotCreate
from schemas.staff_billing_schema import StaffKotUpdate
from schemas.staff_billing_schema import StaffProcessClaimRequest


STAFF_SOURCE_APP = "staff_billing_app"
ADMIN_SOURCE_APP = "admin_app"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def safe_json_loads(raw: Optional[str], default: Any) -> Any:
    if not raw:
        return default
    try:
        return json.loads(raw)
    except Exception:
        return default


def safe_json_dumps(value: Any) -> str:
    return json.dumps(value, default=str, separators=(",", ":"))


def feature_flags_for_business_type(business_type: Optional[str]) -> Dict[str, Any]:
    normalized = (business_type or "general").strip().lower().replace(" ", "_")
    base = {
        "billing": True,
        "cart": True,
        "bill_history": True,
        "sync_status": True,
        "basic_payment": True,
        "discount": False,
        "credit_sale": False,
        "barcode_scan": False,
        "kot": False,
        "pending_kot": False,
        "table_token": False,
        "kitchen_flow": False,
        "hold_bill": True,
        "resume_held_bill": True,
    }

    if any(key in normalized for key in ["restaurant", "cafe", "hotel", "food"]):
        return {
            **base,
            "kot": True,
            "pending_kot": True,
            "table_token": True,
            "kitchen_flow": True,
            "hold_bill": True,
            "resume_held_bill": True,
            "barcode_scan": False,
        }

    if any(key in normalized for key in ["retail", "kirana", "grocery", "shop", "store"]):
        return {
            **base,
            "barcode_scan": True,
            "kot": False,
            "pending_kot": False,
            "table_token": False,
            "kitchen_flow": False,
            "hold_bill": True,
            "resume_held_bill": True,
        }

    return base


def default_staff_permissions(feature_flags: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "create_bill": True,
        "create_kot": bool(feature_flags.get("kot")),
        "convert_kot_to_bill": bool(feature_flags.get("kot")),
        "hold_bill": bool(feature_flags.get("hold_bill")),
        "resume_held_bill": bool(feature_flags.get("resume_held_bill")),
        "collect_payment": True,
        "apply_discount": False,
        "credit_sale": False,
        "void_bill": False,
        "refund_bill": False,
        "manage_products": False,
        "view_reports": False,
        "manage_staff": False,
    }


def hash_invite_code(invite_code: str) -> str:
    normalized = "".join(invite_code.split())
    return hashlib.sha256(
        f"{normalized}:{settings.JWT_SECRET}".encode("utf-8")
    ).hexdigest()


class StaffBillingService:
    @staticmethod
    def create_invite(
        db: Session,
        current_user: User,
        payload: StaffInviteCreate,
    ) -> Tuple[StaffInvite, str]:
        business = db.query(Business).filter(Business.id == current_user.business_id).first()
        if not business:
            raise HTTPException(status_code=404, detail="Business not found")

        code_length = 8 if payload.code_length >= 8 else 6
        expires_in_seconds = max(30, min(payload.expires_in_seconds, 86400))
        max_uses = max(1, payload.max_uses)
        feature_flags = feature_flags_for_business_type(business.business_type)
        permissions = {
            **default_staff_permissions(feature_flags),
            **(payload.permissions or {}),
        }

        invite_code = StaffBillingService._generate_unique_invite_code(db, code_length)
        invite = StaffInvite(
            id=str(uuid.uuid4()),
            business_id=current_user.business_id,
            branch_id=payload.branch_id or "main",
            staff_name=payload.staff_name.strip(),
            staff_role=payload.staff_role or "cashier",
            invite_code_hash=hash_invite_code(invite_code),
            code_length=code_length,
            allowed_apps=safe_json_dumps(payload.allowed_apps or [STAFF_SOURCE_APP]),
            permissions_json=safe_json_dumps(permissions),
            feature_flags_snapshot=safe_json_dumps(feature_flags),
            business_type_snapshot=business.business_type,
            business_name=business.name,
            expires_at=utc_now() + timedelta(seconds=expires_in_seconds),
            max_uses=max_uses,
            used_count=0,
            status="active",
            created_by=current_user.id,
            source_app=ADMIN_SOURCE_APP,
            sync_status="pending",
        )
        db.add(invite)
        db.commit()
        db.refresh(invite)
        return invite, invite_code

    @staticmethod
    def list_invites(db: Session, current_user: User) -> List[StaffInvite]:
        StaffBillingService.expire_old_invites(db, current_user.business_id)
        return (
            db.query(StaffInvite)
            .filter(StaffInvite.business_id == current_user.business_id)
            .order_by(StaffInvite.created_at.desc())
            .limit(100)
            .all()
        )

    @staticmethod
    def revoke_invite(db: Session, current_user: User, invite_id: str) -> StaffInvite:
        invite = (
            db.query(StaffInvite)
            .filter(
                StaffInvite.id == invite_id,
                StaffInvite.business_id == current_user.business_id,
            )
            .first()
        )
        if not invite:
            raise HTTPException(status_code=404, detail="Staff invite not found")
        invite.status = "revoked"
        invite.sync_status = "pending"
        db.commit()
        db.refresh(invite)
        return invite

    @staticmethod
    def expire_old_invites(db: Session, business_id: Optional[str] = None) -> int:
        query = db.query(StaffInvite).filter(
            StaffInvite.status == "active",
            StaffInvite.expires_at <= utc_now(),
        )
        if business_id:
            query = query.filter(StaffInvite.business_id == business_id)
        invites = query.all()
        for invite in invites:
            invite.status = "expired"
            invite.sync_status = "pending"
        if invites:
            db.commit()
        return len(invites)

    @staticmethod
    def verify_invite_code(
        db: Session,
        invite_code: str,
        device_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        StaffBillingService.expire_old_invites(db)
        invite_hash = hash_invite_code(invite_code)
        invite = db.query(StaffInvite).filter(
            StaffInvite.invite_code_hash == invite_hash,
        ).first()
        if not invite:
            raise HTTPException(status_code=400, detail="Invalid invite code")
        if invite.status != "active":
            raise HTTPException(status_code=400, detail=f"Invite code is {invite.status}")
        if ensure_aware(invite.expires_at) <= utc_now():
            invite.status = "expired"
            invite.sync_status = "pending"
            db.commit()
            raise HTTPException(status_code=400, detail="Invite code expired")
        if invite.used_count >= invite.max_uses:
            invite.status = "used"
            invite.sync_status = "pending"
            db.commit()
            raise HTTPException(status_code=400, detail="Invite code already used")

        business = db.query(Business).filter(Business.id == invite.business_id).first()
        if not business:
            raise HTTPException(status_code=404, detail="Business not found")

        feature_flags = safe_json_loads(invite.feature_flags_snapshot, {})
        if not feature_flags:
            feature_flags = feature_flags_for_business_type(business.business_type)
        permissions = {
            **default_staff_permissions(feature_flags),
            **safe_json_loads(invite.permissions_json, {}),
        }
        allowed_apps = safe_json_loads(invite.allowed_apps, [STAFF_SOURCE_APP])

        staff = StaffProfile(
            id=str(uuid.uuid4()),
            business_id=invite.business_id,
            branch_id=invite.branch_id or "main",
            invite_id=invite.id,
            staff_name=invite.staff_name,
            role=invite.staff_role,
            permissions_json=safe_json_dumps(permissions),
            allowed_apps=safe_json_dumps(allowed_apps),
            status="active",
            last_seen_at=utc_now(),
            created_by=invite.created_by,
            created_by_staff_id=invite.created_by_staff_id,
            source_app=ADMIN_SOURCE_APP,
            sync_status="pending",
        )
        db.add(staff)

        invite.used_count += 1
        if invite.used_count >= invite.max_uses:
            invite.status = "used"
        invite.sync_status = "pending"

        db.commit()
        db.refresh(staff)
        db.refresh(invite)

        access_token = create_access_token(
            {
                "sub": staff.id,
                "role": "staff",
                "token_type": "access",
                "business_id": staff.business_id,
                "branch_id": staff.branch_id,
                "staff_id": staff.id,
                "device_id": device_id,
            }
        )
        refresh_token = create_access_token(
            {
                "sub": staff.id,
                "role": "staff",
                "token_type": "refresh",
                "business_id": staff.business_id,
                "branch_id": staff.branch_id,
                "staff_id": staff.id,
                "device_id": device_id,
            }
        )

        return {
            "staff_id": staff.id,
            "staff_name": staff.staff_name,
            "business_id": business.id,
            "business_name": business.name,
            "business_type": business.business_type,
            "branch_id": staff.branch_id,
            "role": staff.role,
            "permissions": permissions,
            "feature_flags": feature_flags,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
        }

    @staticmethod
    def refresh_staff_token(db: Session, refresh_token: str) -> str:
        staff = StaffBillingService.staff_from_token(
            db,
            refresh_token,
            required_token_type="refresh",
        )
        staff.last_seen_at = utc_now()
        db.commit()
        return create_access_token(
            {
                "sub": staff.id,
                "role": "staff",
                "token_type": "access",
                "business_id": staff.business_id,
                "branch_id": staff.branch_id,
                "staff_id": staff.id,
            }
        )

    @staticmethod
    def staff_from_token(
        db: Session,
        token: str,
        required_token_type: str = "access",
    ) -> StaffProfile:
        credentials_exception = HTTPException(
            status_code=401,
            detail="Invalid or expired staff token",
            headers={"WWW-Authenticate": "Bearer"},
        )
        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET,
                algorithms=[settings.JWT_ALGORITHM],
            )
        except JWTError:
            raise credentials_exception

        if payload.get("role") != "staff":
            raise credentials_exception
        if payload.get("token_type", "access") != required_token_type:
            raise credentials_exception

        staff_id = payload.get("staff_id") or payload.get("sub")
        if not staff_id:
            raise credentials_exception
        staff = db.query(StaffProfile).filter(StaffProfile.id == staff_id).first()
        if not staff or staff.status != "active":
            raise credentials_exception
        return staff

    @staticmethod
    def staff_profile_payload(db: Session, staff: StaffProfile) -> Dict[str, Any]:
        business = db.query(Business).filter(Business.id == staff.business_id).first()
        if not business:
            raise HTTPException(status_code=404, detail="Business not found")
        feature_flags = feature_flags_for_business_type(business.business_type)
        permissions = {
            **default_staff_permissions(feature_flags),
            **safe_json_loads(staff.permissions_json, {}),
        }
        return {
            "staff_id": staff.id,
            "staff_name": staff.staff_name,
            "business_id": business.id,
            "business_name": business.name,
            "business_type": business.business_type,
            "branch_id": staff.branch_id,
            "role": staff.role,
            "permissions": permissions,
            "feature_flags": feature_flags,
            "allowed_apps": safe_json_loads(staff.allowed_apps, [STAFF_SOURCE_APP]),
            "status": staff.status,
        }

    @staticmethod
    def list_products(db: Session, staff: StaffProfile) -> List[Product]:
        return (
            db.query(Product)
            .filter(Product.business_id == staff.business_id, Product.is_deleted == False)
            .order_by(Product.name.asc())
            .all()
        )

    @staticmethod
    def list_categories(db: Session, staff: StaffProfile) -> List[str]:
        rows = (
            db.query(Product.category)
            .filter(
                Product.business_id == staff.business_id,
                Product.is_deleted == False,
                Product.category.isnot(None),
            )
            .distinct()
            .order_by(Product.category.asc())
            .all()
        )
        return [row[0] for row in rows if row[0]]

    @staticmethod
    def create_bill(db: Session, staff: StaffProfile, payload: StaffBillCreate) -> Transaction:
        permissions = StaffBillingService._permissions_for_staff(db, staff)
        if not permissions.get("create_bill", True):
            raise HTTPException(status_code=403, detail="Staff cannot create bills")

        if not payload.items and payload.items_json:
            raw_items = (
                safe_json_loads(payload.items_json, [])
                if isinstance(payload.items_json, str)
                else payload.items_json
            )
            if isinstance(raw_items, list):
                payload.items = [
                    StaffBillingService._bill_item_from_dict(item)
                    for item in raw_items
                    if isinstance(item, dict)
                ]

        StaffBillingService._validate_bill_payload(payload, permissions)

        if payload.idempotency_key:
            existing = (
                db.query(Transaction)
                .filter(
                    Transaction.business_id == staff.business_id,
                    Transaction.idempotency_key == payload.idempotency_key,
                )
                .first()
            )
            if existing:
                return existing

        transaction_id = payload.id or str(uuid.uuid4())
        existing = (
            db.query(Transaction)
            .filter(
                Transaction.id == transaction_id,
                Transaction.business_id == staff.business_id,
            )
            .first()
        )
        if existing:
            return existing

        items_json = StaffBillingService._serialize_items(payload.items_json, payload.items)
        transaction = Transaction(
            id=transaction_id,
            business_id=staff.business_id,
            branch_id=staff.branch_id,
            customer_id=payload.customer_id,
            flow="Staff",
            bill_no=payload.bill_no,
            bill_date=payload.bill_date,
            bill_date_text=payload.bill_date_text,
            customer_name=payload.customer_name or "",
            customer_phone=payload.customer_phone or "",
            customer_address=payload.customer_address or "",
            payment_method=payload.payment_method or "Cash",
            payment_option=payload.payment_option or payload.payment_method or "Cash",
            cash_amount=payload.cash_amount or 0.0,
            upi_amount=payload.upi_amount or 0.0,
            card_amount=payload.card_amount or 0.0,
            other_paid_amount=payload.other_paid_amount or 0.0,
            credit_amount=payload.credit_amount or 0.0,
            discount=payload.discount or 0.0,
            is_parcel=payload.is_parcel or False,
            is_hold=False,
            items_json=items_json,
            total_amount=payload.total or 0.0,
            subtotal=payload.subtotal or 0.0,
            total_cgst=payload.total_cgst or 0.0,
            total_sgst=payload.total_sgst or 0.0,
            total_igst=payload.total_igst or 0.0,
            total_tax=payload.total_tax or 0.0,
            old_balance=payload.old_balance or 0.0,
            is_intra_state=payload.is_intra_state,
            status="completed",
            created_by=staff.created_by,
            created_by_staff_id=staff.id,
            source_app=STAFF_SOURCE_APP,
            sync_status=payload.sync_status or "pending",
            idempotency_key=payload.idempotency_key,
            device_id=payload.device_id,
        )
        db.add(transaction)
        StaffBillingService._apply_stock_movements(db, staff, transaction, payload.items)
        StaffBillingService._create_staff_payment(db, staff, transaction, payload)

        db.commit()
        db.refresh(transaction)
        return transaction

    @staticmethod
    def list_bills(db: Session, staff: StaffProfile) -> List[Transaction]:
        return (
            db.query(Transaction)
            .filter(
                Transaction.business_id == staff.business_id,
                Transaction.branch_id == staff.branch_id,
                Transaction.source_app == STAFF_SOURCE_APP,
            )
            .order_by(Transaction.created_at.desc())
            .limit(200)
            .all()
        )

    @staticmethod
    def create_kot(db: Session, staff: StaffProfile, payload: StaffKotCreate) -> StaffKot:
        feature_flags = StaffBillingService._feature_flags_for_staff(db, staff)
        permissions = StaffBillingService._permissions_for_staff(db, staff)
        if not feature_flags.get("kot") or not permissions.get("create_kot"):
            raise HTTPException(status_code=403, detail="KOT is not enabled for this staff")

        if payload.idempotency_key:
            existing = (
                db.query(StaffKot)
                .filter(
                    StaffKot.business_id == staff.business_id,
                    StaffKot.idempotency_key == payload.idempotency_key,
                )
                .first()
            )
            if existing:
                return existing

        kot = StaffKot(
            id=payload.id or str(uuid.uuid4()),
            business_id=staff.business_id,
            branch_id=staff.branch_id,
            staff_id=staff.id,
            staff_name=staff.staff_name,
            status="pending",
            order_type=payload.order_type,
            table_token=payload.table_token,
            items_json=StaffBillingService._serialize_items(payload.items_json, payload.items),
            subtotal=payload.subtotal or 0.0,
            total_tax=payload.total_tax or 0.0,
            total_amount=payload.total_amount or 0.0,
            idempotency_key=payload.idempotency_key,
            created_by=staff.created_by,
            created_by_staff_id=staff.id,
            source_app=STAFF_SOURCE_APP,
            sync_status="pending",
        )
        db.add(kot)
        db.commit()
        db.refresh(kot)
        return kot

    @staticmethod
    def list_kots(db: Session, staff: StaffProfile) -> List[StaffKot]:
        return (
            db.query(StaffKot)
            .filter(
                StaffKot.business_id == staff.business_id,
                StaffKot.branch_id == staff.branch_id,
            )
            .order_by(StaffKot.created_at.desc())
            .limit(200)
            .all()
        )

    @staticmethod
    def update_kot(db: Session, staff: StaffProfile, kot_id: str, payload: StaffKotUpdate) -> StaffKot:
        kot = StaffBillingService._get_kot(db, staff, kot_id)
        if kot.status in ["converted", "completed", "cancelled"]:
            raise HTTPException(status_code=409, detail="Completed KOT cannot be edited")

        if payload.status is not None:
            kot.status = payload.status
        if payload.order_type is not None:
            kot.order_type = payload.order_type
        if payload.table_token is not None:
            kot.table_token = payload.table_token
        if payload.items is not None or payload.items_json is not None:
            kot.items_json = StaffBillingService._serialize_items(payload.items_json, payload.items or [])
        if payload.subtotal is not None:
            kot.subtotal = payload.subtotal
        if payload.total_tax is not None:
            kot.total_tax = payload.total_tax
        if payload.total_amount is not None:
            kot.total_amount = payload.total_amount
        kot.sync_status = "pending"
        db.commit()
        db.refresh(kot)
        return kot

    @staticmethod
    def convert_kot_to_bill(
        db: Session,
        staff: StaffProfile,
        kot_id: str,
        payload: StaffBillCreate,
    ) -> Transaction:
        permissions = StaffBillingService._permissions_for_staff(db, staff)
        if not permissions.get("convert_kot_to_bill"):
            raise HTTPException(status_code=403, detail="Staff cannot convert KOT to bill")

        kot = StaffBillingService._get_kot(db, staff, kot_id)
        if kot.bill_transaction_id:
            existing = (
                db.query(Transaction)
                .filter(
                    Transaction.id == kot.bill_transaction_id,
                    Transaction.business_id == staff.business_id,
                )
                .first()
            )
            if existing:
                return existing
        if kot.status in ["cancelled"]:
            raise HTTPException(status_code=409, detail="Cancelled KOT cannot be converted")

        if not payload.items:
            payload.items = [
                StaffBillingService._bill_item_from_dict(item)
                for item in safe_json_loads(kot.items_json, [])
            ]
        if not payload.items_json:
            payload.items_json = safe_json_loads(kot.items_json, [])
        if payload.subtotal == 0:
            payload.subtotal = kot.subtotal
        if payload.total_tax == 0:
            payload.total_tax = kot.total_tax
        if payload.total == 0:
            payload.total = kot.total_amount
        if not payload.idempotency_key:
            payload.idempotency_key = f"kot:{kot.id}:bill"

        transaction = StaffBillingService.create_bill(db, staff, payload)
        kot.status = "converted"
        kot.bill_transaction_id = transaction.id
        kot.sync_status = "pending"
        db.commit()
        db.refresh(transaction)
        return transaction

    @staticmethod
    def create_held_bill(
        db: Session,
        staff: StaffProfile,
        payload: StaffHeldBillCreate,
    ) -> StaffHeldBill:
        feature_flags = StaffBillingService._feature_flags_for_staff(db, staff)
        permissions = StaffBillingService._permissions_for_staff(db, staff)
        if not feature_flags.get("hold_bill") or not permissions.get("hold_bill"):
            raise HTTPException(status_code=403, detail="Hold bill is not enabled for this staff")

        if payload.idempotency_key:
            existing = (
                db.query(StaffHeldBill)
                .filter(
                    StaffHeldBill.business_id == staff.business_id,
                    StaffHeldBill.idempotency_key == payload.idempotency_key,
                )
                .first()
            )
            if existing:
                return existing

        held_bill = StaffHeldBill(
            id=payload.id or str(uuid.uuid4()),
            business_id=staff.business_id,
            branch_id=staff.branch_id,
            staff_id=staff.id,
            staff_name=staff.staff_name,
            status="held",
            customer_id=payload.customer_id,
            customer_name=payload.customer_name,
            items_json=StaffBillingService._serialize_items(payload.items_json, payload.items),
            subtotal=payload.subtotal or 0.0,
            total_tax=payload.total_tax or 0.0,
            total_amount=payload.total_amount or 0.0,
            idempotency_key=payload.idempotency_key,
            created_by=staff.created_by,
            created_by_staff_id=staff.id,
            source_app=STAFF_SOURCE_APP,
            sync_status="pending",
        )
        db.add(held_bill)
        db.commit()
        db.refresh(held_bill)
        return held_bill

    @staticmethod
    def list_held_bills(db: Session, staff: StaffProfile) -> List[StaffHeldBill]:
        return (
            db.query(StaffHeldBill)
            .filter(
                StaffHeldBill.business_id == staff.business_id,
                StaffHeldBill.branch_id == staff.branch_id,
            )
            .order_by(StaffHeldBill.created_at.desc())
            .limit(200)
            .all()
        )

    @staticmethod
    def resume_held_bill(db: Session, staff: StaffProfile, held_bill_id: str) -> StaffHeldBill:
        held_bill = (
            db.query(StaffHeldBill)
            .filter(
                StaffHeldBill.id == held_bill_id,
                StaffHeldBill.business_id == staff.business_id,
                StaffHeldBill.branch_id == staff.branch_id,
            )
            .first()
        )
        if not held_bill:
            raise HTTPException(status_code=404, detail="Held bill not found")
        if held_bill.status == "completed":
            raise HTTPException(status_code=409, detail="Completed held bill cannot be resumed")
        held_bill.status = "resumed"
        held_bill.sync_status = "pending"
        db.commit()
        db.refresh(held_bill)
        return held_bill

    @staticmethod
    def claim_process(
        db: Session,
        staff: StaffProfile,
        payload: StaffProcessClaimRequest,
    ) -> StaffProcessLock:
        process_id = payload.process_id or f"{payload.process_type}:{payload.entity_id}"
        now = utc_now()
        expires_at = now + timedelta(seconds=max(30, payload.ttl_seconds))
        lock = (
            db.query(StaffProcessLock)
            .filter(
                StaffProcessLock.process_id == process_id,
                StaffProcessLock.business_id == staff.business_id,
            )
            .first()
        )
        if lock:
            lock_expired = ensure_aware(lock.expires_at) <= now
            if lock.status == "completed":
                raise HTTPException(status_code=409, detail="Process is completed")
            if (
                lock.status == "active"
                and not lock_expired
                and lock.handled_by_staff_id != staff.id
            ):
                raise HTTPException(
                    status_code=409,
                    detail=f"Process is being handled by {lock.handled_by_staff_name}",
                )
            if lock_expired:
                lock.status = "expired"

            lock.process_type = payload.process_type
            lock.entity_id = payload.entity_id
            lock.branch_id = staff.branch_id
            lock.handled_by_staff_id = staff.id
            lock.handled_by_staff_name = staff.staff_name
            lock.status = "active"
            lock.locked_at = now
            lock.last_heartbeat_at = now
            lock.expires_at = expires_at
            lock.created_by_staff_id = staff.id
            lock.sync_status = "pending"
        else:
            lock = StaffProcessLock(
                process_id=process_id,
                process_type=payload.process_type,
                entity_id=payload.entity_id,
                business_id=staff.business_id,
                branch_id=staff.branch_id,
                handled_by_staff_id=staff.id,
                handled_by_staff_name=staff.staff_name,
                status="active",
                locked_at=now,
                last_heartbeat_at=now,
                expires_at=expires_at,
                created_by=staff.created_by,
                created_by_staff_id=staff.id,
                source_app=STAFF_SOURCE_APP,
                sync_status="pending",
            )
            db.add(lock)

        db.commit()
        db.refresh(lock)
        return lock

    @staticmethod
    def release_process(db: Session, staff: StaffProfile, process_id: str, status: str) -> StaffProcessLock:
        lock = StaffBillingService._get_process_lock(db, staff, process_id)
        if lock.handled_by_staff_id != staff.id:
            raise HTTPException(status_code=403, detail="Only handler can release this process")
        lock.status = status if status in ["released", "completed"] else "released"
        lock.last_heartbeat_at = utc_now()
        lock.expires_at = utc_now()
        lock.sync_status = "pending"
        db.commit()
        db.refresh(lock)
        return lock

    @staticmethod
    def heartbeat_process(
        db: Session,
        staff: StaffProfile,
        process_id: str,
        ttl_seconds: int,
    ) -> StaffProcessLock:
        lock = StaffBillingService._get_process_lock(db, staff, process_id)
        now = utc_now()
        if lock.handled_by_staff_id != staff.id:
            raise HTTPException(status_code=403, detail="Only handler can heartbeat this process")
        if lock.status != "active" or ensure_aware(lock.expires_at) <= now:
            lock.status = "expired"
            lock.sync_status = "pending"
            db.commit()
            raise HTTPException(status_code=409, detail="Process lock expired")
        lock.last_heartbeat_at = now
        lock.expires_at = now + timedelta(seconds=max(30, ttl_seconds))
        lock.sync_status = "pending"
        db.commit()
        db.refresh(lock)
        return lock

    @staticmethod
    def list_active_processes(db: Session, staff: StaffProfile) -> List[StaffProcessLock]:
        now = utc_now()
        expired = (
            db.query(StaffProcessLock)
            .filter(
                StaffProcessLock.business_id == staff.business_id,
                StaffProcessLock.status == "active",
                StaffProcessLock.expires_at <= now,
            )
            .all()
        )
        for lock in expired:
            lock.status = "expired"
            lock.sync_status = "pending"
        if expired:
            db.commit()

        return (
            db.query(StaffProcessLock)
            .filter(
                StaffProcessLock.business_id == staff.business_id,
                StaffProcessLock.branch_id == staff.branch_id,
                StaffProcessLock.status.in_(["active", "released", "expired"]),
            )
            .order_by(StaffProcessLock.updated_at.desc())
            .limit(200)
            .all()
        )

    @staticmethod
    def persist_realtime_event(
        db: Session,
        staff: StaffProfile,
        event: RealtimeEventEnvelope,
    ) -> bool:
        if event.business_id and event.business_id != staff.business_id:
            raise HTTPException(status_code=403, detail="Event business does not match staff")
        if event.staff_id and event.staff_id != staff.id:
            raise HTTPException(status_code=403, detail="Event staff does not match token")

        existing = db.query(StaffRealtimeEvent).filter(
            StaffRealtimeEvent.event_id == event.event_id,
        ).first()
        if existing:
            return False

        row = StaffRealtimeEvent(
            event_id=event.event_id,
            event_type=event.event_type,
            entity_type=event.entity_type,
            entity_id=event.entity_id,
            business_id=staff.business_id,
            branch_id=event.branch_id or staff.branch_id,
            staff_id=staff.id,
            device_id=event.device_id,
            occurred_at=event.occurred_at or utc_now(),
            payload_json=safe_json_dumps(event.payload),
            processed=False,
            created_by=staff.created_by,
            created_by_staff_id=staff.id,
            source_app=STAFF_SOURCE_APP,
            sync_status="pending",
        )
        db.add(row)
        db.commit()
        return True

    @staticmethod
    def pull_sync_payload(db: Session, staff: StaffProfile) -> Dict[str, Any]:
        products = [StaffBillingService._sa_to_dict(product) for product in StaffBillingService.list_products(db, staff)]
        kots = [StaffBillingService._sa_to_dict(kot) for kot in StaffBillingService.list_kots(db, staff)]
        held = [StaffBillingService._sa_to_dict(row) for row in StaffBillingService.list_held_bills(db, staff)]
        bills = [StaffBillingService._sa_to_dict(row) for row in StaffBillingService.list_bills(db, staff)]
        events = [
            StaffBillingService._sa_to_dict(row)
            for row in (
                db.query(StaffRealtimeEvent)
                .filter(
                    StaffRealtimeEvent.business_id == staff.business_id,
                    StaffRealtimeEvent.branch_id == staff.branch_id,
                )
                .order_by(StaffRealtimeEvent.created_at.desc())
                .limit(200)
                .all()
            )
        ]
        return {
            "products": products,
            "kots": kots,
            "held_bills": held,
            "bills": bills,
            "events": events,
        }

    @staticmethod
    def websocket_principal_from_token(db: Session, token: str) -> Dict[str, Any]:
        credentials_exception = HTTPException(status_code=401, detail="Invalid websocket token")
        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET,
                algorithms=[settings.JWT_ALGORITHM],
            )
        except JWTError:
            raise credentials_exception

        if payload.get("role") == "staff":
            staff_id = payload.get("staff_id") or payload.get("sub")
            staff = db.query(StaffProfile).filter(StaffProfile.id == staff_id).first()
            if not staff or staff.status != "active":
                raise credentials_exception
            return {
                "principal_type": "staff",
                "principal_id": staff.id,
                "business_id": staff.business_id,
                "branch_id": staff.branch_id,
                "staff": staff,
            }

        user_id = payload.get("sub")
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise credentials_exception
        return {
            "principal_type": "admin",
            "principal_id": user.id,
            "business_id": user.business_id,
            "branch_id": payload.get("branch_id", "main"),
            "user": user,
        }

    @staticmethod
    def _generate_unique_invite_code(db: Session, code_length: int) -> str:
        lower = 10 ** (code_length - 1)
        upper = (10 ** code_length) - 1
        for _ in range(20):
            code = str(secrets.randbelow(upper - lower + 1) + lower)
            if not db.query(StaffInvite).filter(
                StaffInvite.invite_code_hash == hash_invite_code(code)
            ).first():
                return code
        raise HTTPException(status_code=500, detail="Could not generate unique invite code")

    @staticmethod
    def _feature_flags_for_staff(db: Session, staff: StaffProfile) -> Dict[str, Any]:
        business = db.query(Business).filter(Business.id == staff.business_id).first()
        return feature_flags_for_business_type(business.business_type if business else None)

    @staticmethod
    def _permissions_for_staff(db: Session, staff: StaffProfile) -> Dict[str, Any]:
        feature_flags = StaffBillingService._feature_flags_for_staff(db, staff)
        return {
            **default_staff_permissions(feature_flags),
            **safe_json_loads(staff.permissions_json, {}),
        }

    @staticmethod
    def _validate_bill_payload(payload: StaffBillCreate, permissions: Dict[str, Any]) -> None:
        if not payload.items and not payload.items_json:
            raise HTTPException(status_code=400, detail="Cart is empty")
        amounts = [
            payload.cash_amount,
            payload.upi_amount,
            payload.card_amount,
            payload.other_paid_amount,
            payload.credit_amount,
            payload.discount,
        ]
        if any(amount < 0 for amount in amounts):
            raise HTTPException(status_code=400, detail="Paid amount cannot be negative")
        if payload.discount > payload.subtotal and not permissions.get("allow_discount_above_subtotal"):
            raise HTTPException(status_code=400, detail="Discount cannot exceed subtotal")
        if payload.credit_amount > 0:
            if not permissions.get("credit_sale"):
                raise HTTPException(status_code=403, detail="Credit sale is not enabled for this staff")
            if not payload.customer_id and not payload.customer_name:
                raise HTTPException(status_code=400, detail="Credit payment requires customer")

        payable_total = payload.total or (
            payload.subtotal + payload.total_tax - payload.discount + payload.old_balance
        )
        paid_amount = (
            payload.cash_amount
            + payload.upi_amount
            + payload.card_amount
            + payload.other_paid_amount
        )
        if paid_amount - payable_total > 0.01:
            raise HTTPException(status_code=400, detail="Paid amount exceeds payable total")
        if payable_total - (paid_amount + payload.credit_amount) > 0.01:
            raise HTTPException(status_code=400, detail="Payment split does not cover payable total")
        for item in payload.items:
            if item.quantity <= 0:
                raise HTTPException(status_code=400, detail="Item quantity must be positive")

    @staticmethod
    def _serialize_items(items_json: Optional[Any], items: Iterable[Any]) -> str:
        if isinstance(items_json, str):
            return items_json
        if items_json is not None:
            return safe_json_dumps(items_json)
        return safe_json_dumps([
            item.model_dump() if hasattr(item, "model_dump") else dict(item)
            for item in items
        ])

    @staticmethod
    def _bill_item_from_dict(raw: Dict[str, Any]):
        from schemas.staff_billing_schema import StaffBillItemPayload

        return StaffBillItemPayload(
            product_id=raw.get("product_id"),
            product_name=raw.get("product_name") or raw.get("name") or "Item",
            quantity=int(raw.get("quantity") or 1),
            price=float(raw.get("price") or 0.0),
            gst_percentage=float(raw.get("gst_percentage") or raw.get("gstPercent") or 0.0),
            subtotal=float(raw.get("subtotal") or 0.0),
        )

    @staticmethod
    def _apply_stock_movements(
        db: Session,
        staff: StaffProfile,
        transaction: Transaction,
        items: Iterable[Any],
    ) -> None:
        for item in items:
            if not item.product_id:
                continue
            product = (
                db.query(Product)
                .filter(
                    Product.id == item.product_id,
                    Product.business_id == staff.business_id,
                    Product.is_deleted == False,
                )
                .first()
            )
            if not product:
                raise HTTPException(status_code=404, detail=f"Product {item.product_id} not found")
            quantity = int(item.quantity)
            if not product.is_stockless and product.stock_quantity < quantity:
                raise HTTPException(status_code=400, detail="Stock not available")

            subtotal = item.subtotal or (item.price * quantity)
            db.add(
                TransactionItem(
                    id=str(uuid.uuid4()),
                    transaction_id=transaction.id,
                    product_id=product.id,
                    product_name=product.name,
                    quantity=quantity,
                    price=item.price or product.price,
                    subtotal=subtotal,
                )
            )

            if product.is_stockless:
                continue
            before_stock = product.stock_quantity
            after_stock = before_stock - quantity
            product.stock_quantity = after_stock
            product.in_stock = after_stock > 0
            db.add(
                InventoryMovement(
                    business_id=staff.business_id,
                    branch_id=staff.branch_id,
                    product_id=product.id,
                    movement_type=InventoryMovementType.SALE,
                    quantity=quantity,
                    before_stock=before_stock,
                    after_stock=after_stock,
                    reference_id=transaction.id,
                    notes=f"Staff bill created by {staff.staff_name}",
                    created_by=StaffBillingService._created_by_user_id(db, staff),
                    created_by_staff_id=staff.id,
                    source_app=STAFF_SOURCE_APP,
                    sync_status="pending",
                )
            )

    @staticmethod
    def _create_staff_payment(
        db: Session,
        staff: StaffProfile,
        transaction: Transaction,
        payload: StaffBillCreate,
    ) -> None:
        paid_amount = (
            payload.cash_amount
            + payload.upi_amount
            + payload.card_amount
            + payload.other_paid_amount
        )
        payment = StaffPayment(
            id=str(uuid.uuid4()),
            business_id=staff.business_id,
            branch_id=staff.branch_id,
            staff_id=staff.id,
            staff_name=staff.staff_name,
            bill_transaction_id=transaction.id,
            cash_amount=payload.cash_amount,
            upi_amount=payload.upi_amount,
            card_amount=payload.card_amount,
            other_paid_amount=payload.other_paid_amount,
            credit_amount=payload.credit_amount,
            total_paid_amount=paid_amount,
            payment_json=safe_json_dumps(
                {
                    "payment_method": payload.payment_method,
                    "payment_option": payload.payment_option,
                    "cash_amount": payload.cash_amount,
                    "upi_amount": payload.upi_amount,
                    "card_amount": payload.card_amount,
                    "other_paid_amount": payload.other_paid_amount,
                    "credit_amount": payload.credit_amount,
                }
            ),
            created_by=staff.created_by,
            created_by_staff_id=staff.id,
            source_app=STAFF_SOURCE_APP,
            sync_status="pending",
        )
        db.add(payment)

    @staticmethod
    def _get_kot(db: Session, staff: StaffProfile, kot_id: str) -> StaffKot:
        kot = (
            db.query(StaffKot)
            .filter(
                StaffKot.id == kot_id,
                StaffKot.business_id == staff.business_id,
                StaffKot.branch_id == staff.branch_id,
            )
            .first()
        )
        if not kot:
            raise HTTPException(status_code=404, detail="KOT not found")
        return kot

    @staticmethod
    def _get_process_lock(db: Session, staff: StaffProfile, process_id: str) -> StaffProcessLock:
        lock = (
            db.query(StaffProcessLock)
            .filter(
                StaffProcessLock.process_id == process_id,
                StaffProcessLock.business_id == staff.business_id,
                StaffProcessLock.branch_id == staff.branch_id,
            )
            .first()
        )
        if not lock:
            raise HTTPException(status_code=404, detail="Process lock not found")
        return lock

    @staticmethod
    def _created_by_user_id(db: Session, staff: StaffProfile) -> str:
        if staff.created_by:
            return staff.created_by
        user = db.query(User).filter(User.business_id == staff.business_id).first()
        if user:
            return user.id
        raise HTTPException(
            status_code=500,
            detail="Inventory movement requires an admin user for this business",
        )

    @staticmethod
    def _sa_to_dict(row: Any) -> Dict[str, Any]:
        data = {}
        for column in row.__table__.columns:
            value = getattr(row, column.name)
            if isinstance(value, datetime):
                value = value.isoformat()
            data[column.name] = value
        return data


class StaffRealtimeConnectionManager:
    """In-process realtime fan-out for single-worker deployments.

    Multi-worker deployments should use a shared pub/sub adapter so events
    fan out across worker processes.
    """

    def __init__(self) -> None:
        self._business_connections: Dict[str, List[WebSocket]] = {}
        self._socket_business: Dict[WebSocket, str] = {}

    async def connect(self, websocket: WebSocket, business_id: str) -> None:
        await websocket.accept()
        self._business_connections.setdefault(business_id, []).append(websocket)
        self._socket_business[websocket] = business_id

    def disconnect(self, websocket: WebSocket) -> None:
        business_id = self._socket_business.pop(websocket, None)
        if not business_id:
            return
        sockets = self._business_connections.get(business_id, [])
        if websocket in sockets:
            sockets.remove(websocket)
        if not sockets:
            self._business_connections.pop(business_id, None)

    async def broadcast_business(self, business_id: str, message: Dict[str, Any]) -> None:
        stale: List[WebSocket] = []
        for websocket in list(self._business_connections.get(business_id, [])):
            try:
                await websocket.send_json(message)
            except Exception:
                stale.append(websocket)
        for websocket in stale:
            self.disconnect(websocket)


staff_realtime_manager = StaffRealtimeConnectionManager()
