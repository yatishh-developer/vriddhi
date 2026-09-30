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
from sqlalchemy.orm import Session

from auth.authorization import permissions_from_legacy_map
from auth.dependencies import resolve_principal_from_token
from auth.errors import AuthError
from auth.firebase import VerifiedFirebaseIdentity, verify_firebase_id_token
from auth.principal import ActorType, PrincipalContext
from auth.sessions import issue_session_tokens
from auth.security import create_access_token
from core.config import settings
from models.business_model import Business
from models.customer_model import Customer
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
from schemas.staff_billing_schema import StaffFirebaseInviteAcceptRequest
from schemas.staff_billing_schema import StaffFirebaseLoginRequest
from schemas.staff_billing_schema import StaffHeldBillCreate
from schemas.staff_billing_schema import StaffInviteCreate
from schemas.staff_billing_schema import StaffKotCreate
from schemas.staff_billing_schema import StaffKotUpdate
from schemas.staff_billing_schema import StaffProcessClaimRequest
from schemas.checkout_schema import CheckoutItemInput, CheckoutPaymentInput, CheckoutRequest
from services.checkout_service import CheckoutService


STAFF_SOURCE_APP = "staff_billing_app"
ADMIN_SOURCE_APP = "admin_app"
KOT_STATUSES = {"pending", "preparing", "ready", "served", "converted", "cancelled"}
HELD_BILL_STATUSES = {"held", "resumed", "completed", "cancelled"}


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
        "orders": True,
        "inventory": True,
        "credit": False,
        "table_management": False,
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
            "table_management": True,
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
        "cancel_kot": False,
        "cancel_bill": False,
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
        "tables.create": False,
        "tables.update": False,
        "tables.move": False,
        "tables.merge": False,
    }


def normalize_invite_code(invite_code: str) -> str:
    raw = (invite_code or "").strip()
    if raw.startswith("vabos-staff-invite://"):
        raw = raw.rsplit("/", 1)[-1]
    normalized = "".join(ch for ch in raw if ch.isdigit())
    return normalized


def hash_invite_code(invite_code: str) -> str:
    normalized = normalize_invite_code(invite_code)
    return hashlib.sha256(
        f"{normalized}:{settings.JWT_SECRET}".encode("utf-8")
    ).hexdigest()


class StaffBillingService:
    default_permissions_for_staff = staticmethod(default_staff_permissions)

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
    def get_invite(db: Session, current_user: User, invite_id: str) -> StaffInvite:
        StaffBillingService.expire_old_invites(db, current_user.business_id)
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
        return invite

    @staticmethod
    def update_invite(
        db: Session,
        current_user: User,
        invite_id: str,
        payload: Any,
    ) -> StaffInvite:
        invite = StaffBillingService.get_invite(db, current_user, invite_id)
        if invite.status != "active":
            raise HTTPException(
                status_code=400,
                detail=f"Cannot edit invite because it is {invite.status}",
            )

        if payload.staff_name is not None and payload.staff_name.strip():
            invite.staff_name = payload.staff_name.strip()
        if payload.staff_role is not None and payload.staff_role.strip():
            invite.staff_role = payload.staff_role.strip()
        if payload.branch_id is not None and payload.branch_id.strip():
            invite.branch_id = payload.branch_id.strip()
        if payload.permissions is not None:
            feature_flags = safe_json_loads(invite.feature_flags_snapshot, {})
            invite.permissions_json = safe_json_dumps(
                {
                    **default_staff_permissions(feature_flags),
                    **payload.permissions,
                }
            )
        if payload.allowed_apps is not None:
            invite.allowed_apps = safe_json_dumps(payload.allowed_apps or [STAFF_SOURCE_APP])
        if payload.expires_in_seconds is not None:
            invite.expires_at = utc_now() + timedelta(
                seconds=max(60, min(payload.expires_in_seconds, 86400))
            )
        if payload.max_uses is not None:
            invite.max_uses = max(1, payload.max_uses)

        invite.sync_status = "pending"
        db.commit()
        db.refresh(invite)
        return invite

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
    def list_staff_profiles(db: Session, current_user: User) -> List[StaffProfile]:
        return (
            db.query(StaffProfile)
            .filter(StaffProfile.business_id == current_user.business_id)
            .order_by(StaffProfile.created_at.desc())
            .limit(300)
            .all()
        )

    @staticmethod
    def get_staff_profile_admin(
        db: Session,
        current_user: User,
        staff_id: str,
    ) -> StaffProfile:
        staff = (
            db.query(StaffProfile)
            .filter(
                StaffProfile.id == staff_id,
                StaffProfile.business_id == current_user.business_id,
            )
            .first()
        )
        if not staff:
            raise HTTPException(status_code=404, detail="Staff account not found")
        return staff

    @staticmethod
    def update_staff_profile_admin(
        db: Session,
        current_user: User,
        staff_id: str,
        payload: Any,
    ) -> StaffProfile:
        staff = StaffBillingService.get_staff_profile_admin(db, current_user, staff_id)

        permission_or_status_changed = payload.permissions is not None or payload.status is not None
        if payload.staff_name is not None and payload.staff_name.strip():
            staff.staff_name = payload.staff_name.strip()
        if payload.role is not None and payload.role.strip():
            staff.role = payload.role.strip()
        if payload.branch_id is not None and payload.branch_id.strip():
            staff.branch_id = payload.branch_id.strip()
        if payload.permissions is not None:
            feature_flags = StaffBillingService._feature_flags_for_staff(db, staff)
            staff.permissions_json = safe_json_dumps(
                {
                    **default_staff_permissions(feature_flags),
                    **payload.permissions,
                }
            )
        if payload.allowed_apps is not None:
            staff.allowed_apps = safe_json_dumps(payload.allowed_apps or [STAFF_SOURCE_APP])
        if payload.status is not None:
            status = payload.status.strip().lower()
            if status not in {"active", "disabled", "revoked"}:
                raise HTTPException(status_code=400, detail="Invalid staff status")
            staff.status = status

        staff.sync_status = "pending"
        if permission_or_status_changed:
            from services.domain_event_service import DomainEventService
            DomainEventService.enqueue(
                db, event_type="membership.permissions_changed", aggregate_type="membership", aggregate_id=staff.id,
                business_id=staff.business_id, branch_id=staff.branch_id,
                data={"membership_id": staff.id, "status": staff.status, "refresh_access": True}, actor_id=current_user.id,
            )
        db.commit()
        db.refresh(staff)
        return staff

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
        normalized_code = normalize_invite_code(invite_code)
        if len(normalized_code) not in {6, 8}:
            raise AuthError(400, "INVITE_INVALID", "Invite code is invalid.")
        StaffBillingService.expire_old_invites(db)
        invite_hash = hash_invite_code(normalized_code)
        invite = db.query(StaffInvite).filter(
            StaffInvite.invite_code_hash == invite_hash,
        ).with_for_update().first()
        if not invite:
            raise AuthError(400, "INVITE_INVALID", "Invite code is invalid.")
        if invite.status != "active":
            code = "INVITE_EXPIRED" if invite.status == "expired" else "INVITE_INVALID"
            raise AuthError(400, code, "Invite code is unavailable.")
        if ensure_aware(invite.expires_at) <= utc_now():
            invite.status = "expired"
            invite.sync_status = "pending"
            db.commit()
            raise AuthError(400, "INVITE_EXPIRED", "Invite code has expired.")
        if invite.used_count >= invite.max_uses:
            invite.status = "used"
            invite.sync_status = "pending"
            db.commit()
            raise AuthError(400, "INVITE_INVALID", "Invite code is unavailable.")

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
            # Device metadata is not a verified Firebase identity. Legacy
            # invite verification remains supported, but only Firebase token
            # verification may populate firebase_uid.
            firebase_uid=None,
            auth_provider=None,
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

        return StaffBillingService._auth_payload_for_staff(
            db,
            staff,
            device_id=device_id,
        )

    @staticmethod
    def firebase_login(
        db: Session,
        payload: StaffFirebaseLoginRequest,
    ) -> Dict[str, Any]:
        identity = StaffBillingService._verified_firebase_identity(payload)
        firebase_uid = identity.uid
        staff = (
            db.query(StaffProfile)
            .filter(StaffProfile.firebase_uid == firebase_uid)
            .first()
        )
        if not staff or staff.status != "active":
            return {
                "status": "invite_required",
                "requiresInvite": True,
                "requires_invite": True,
            }

        StaffBillingService._apply_firebase_identity(staff, identity)
        staff.last_seen_at = utc_now()
        db.commit()
        db.refresh(staff)
        return StaffBillingService._auth_payload_for_staff(
            db,
            staff,
            device_id=firebase_uid,
        )

    @staticmethod
    def accept_firebase_invite(
        db: Session,
        payload: StaffFirebaseInviteAcceptRequest,
    ) -> Dict[str, Any]:
        identity = StaffBillingService._verified_firebase_identity(payload)
        firebase_uid = identity.uid
        existing = (
            db.query(StaffProfile)
            .filter(StaffProfile.firebase_uid == firebase_uid)
            .first()
        )
        if existing and existing.status == "active":
            StaffBillingService._apply_firebase_identity(existing, identity)
            existing.last_seen_at = utc_now()
            db.commit()
            db.refresh(existing)
            return StaffBillingService._auth_payload_for_staff(
                db,
                existing,
            device_id=firebase_uid,
            )

        response = StaffBillingService.verify_invite_code(
            db,
            payload.invite_code,
            None,
        )
        staff = (
            db.query(StaffProfile)
            .filter(StaffProfile.id == response["staff_id"])
            .first()
        )
        if staff:
            StaffBillingService._apply_firebase_identity(staff, identity)
            staff.last_seen_at = utc_now()
            db.commit()
        return response

    @staticmethod
    def _auth_payload_for_staff(
        db: Session,
        staff: StaffProfile,
        device_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        StaffBillingService._ensure_staff_billing_allowed(staff)
        business = db.query(Business).filter(Business.id == staff.business_id).first()
        if not business:
            raise HTTPException(status_code=404, detail="Business not found")
        feature_flags = feature_flags_for_business_type(business.business_type)
        permissions = {
            **default_staff_permissions(feature_flags),
            **safe_json_loads(staff.permissions_json, {}),
        }
        access_token, refresh_token, _session = issue_session_tokens(
            db,
            actor_type=ActorType.WORKER,
            principal_id=staff.id,
            business_id=staff.business_id,
            staff_id=staff.id,
            branch_id=staff.branch_id,
            device_id=device_id,
        )
        db.commit()
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
            "business_address": business.address or "",
            "business_phone": business.phone or "",
            "upi_id": business.upi_id or "",
            "businessProfile": {
                "business_id": business.id,
                "business_name": business.name,
                "business_type": business.business_type,
                "address": business.address or "",
                "phone": business.phone or "",
                "upi_id": business.upi_id or "",
                "branch_id": staff.branch_id,
            },
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
        }

    @staticmethod
    def _verified_firebase_identity(
        payload: StaffFirebaseLoginRequest,
    ) -> VerifiedFirebaseIdentity:
        """Return identity only from a Firebase Admin verified ID token."""
        try:
            return verify_firebase_id_token(payload.id_token or "")
        except HTTPException as exc:
            if exc.status_code == 503:
                raise AuthError(
                    503,
                    "FIREBASE_NOT_CONFIGURED",
                    "Firebase authentication is not configured.",
                ) from exc
            raise AuthError(401, "FIREBASE_TOKEN_INVALID", "Firebase ID token is invalid.") from exc

    @staticmethod
    def _apply_firebase_identity(
        staff: StaffProfile,
        identity: VerifiedFirebaseIdentity,
    ) -> None:
        staff.firebase_uid = identity.uid
        staff.auth_provider = identity.provider or staff.auth_provider or "firebase"
        if identity.email:
            staff.auth_email = identity.email
        if identity.display_name:
            staff.auth_display_name = identity.display_name
        if identity.phone_number:
            staff.auth_phone_number = identity.phone_number

    @staticmethod
    def refresh_staff_token(db: Session, refresh_token: str) -> str:
        principal = resolve_principal_from_token(db, refresh_token, required_token_type="refresh")
        if principal.actor_type != ActorType.WORKER or not principal.staff_id:
            raise HTTPException(status_code=401, detail="Invalid or expired staff token")
        staff = db.query(StaffProfile).filter(StaffProfile.id == principal.staff_id).first()
        staff.last_seen_at = utc_now()
        db.commit()
        return create_access_token(
            {
                "sub": staff.id,
                "actor_type": ActorType.WORKER.value,
                "role": "staff",
                "token_type": "access",
                "business_id": staff.business_id,
                "branch_id": staff.branch_id,
                "staff_id": staff.id,
                "session_id": principal.session_id,
                "device_id": principal.device_id,
            }
        )

    @staticmethod
    def staff_from_token(
        db: Session,
        token: str,
        required_token_type: str = "access",
    ) -> StaffProfile:
        principal = resolve_principal_from_token(db, token, required_token_type=required_token_type)
        if principal.actor_type != ActorType.WORKER or not principal.staff_id:
            raise HTTPException(status_code=401, detail="Invalid or expired staff token")
        return db.query(StaffProfile).filter(StaffProfile.id == principal.staff_id).first()

    @staticmethod
    def staff_profile_payload(db: Session, staff: StaffProfile) -> Dict[str, Any]:
        StaffBillingService._ensure_staff_billing_allowed(staff)
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
    def create_bill(
        db: Session,
        staff: StaffProfile,
        payload: StaffBillCreate,
        principal: PrincipalContext | None = None,
        after_create=None,
    ) -> Transaction:
        """Legacy staff adapter; CheckoutService owns all financial writes."""
        StaffBillingService._ensure_staff_billing_allowed(staff)
        principal = principal or StaffBillingService._principal_for_staff(db, staff)
        if not payload.items and payload.items_json:
            raw_items = safe_json_loads(payload.items_json, []) if isinstance(payload.items_json, str) else payload.items_json
            if isinstance(raw_items, list):
                payload.items = [StaffBillingService._bill_item_from_dict(item) for item in raw_items if isinstance(item, dict)]
        items = []
        for item in payload.items:
            product_id = item.product_id
            if not product_id and item.product_name:
                matches = db.query(Product).filter(
                    Product.business_id == staff.business_id,
                    Product.name == item.product_name,
                    Product.is_deleted == False,
                ).limit(2).all()
                if len(matches) == 1:
                    product_id = matches[0].id
            if not product_id:
                raise HTTPException(status_code=400, detail="Staff bill item requires a valid product")
            items.append(CheckoutItemInput(product_id=product_id, quantity=item.quantity))
        request = CheckoutRequest(
            items=items,
            payment=CheckoutPaymentInput(
                cash_amount=str(payload.cash_amount or 0),
                upi_amount=str(payload.upi_amount or 0),
                card_amount=str(payload.card_amount or 0),
                other_paid_amount=str(payload.other_paid_amount or 0),
                credit_amount=str(payload.credit_amount or 0),
                payment_method=payload.payment_method or "Cash",
                payment_option=payload.payment_option or payload.payment_method or "Cash",
            ),
            customer_id=payload.customer_id,
            discount=str(payload.discount or 0),
            branch_id=staff.branch_id,
            idempotency_key=payload.idempotency_key,
            device_id=payload.device_id,
            bill_no=payload.bill_no,
            bill_date=payload.bill_date,
            bill_date_text=payload.bill_date_text,
            is_parcel=payload.is_parcel,
        )
        return CheckoutService.checkout(
            db,
            principal=principal,
            request=request,
            source_app=STAFF_SOURCE_APP,
            legacy_transaction_id=payload.id,
            after_create=after_create,
        )

    @staticmethod
    def list_bills(db: Session, staff: StaffProfile) -> List[Transaction]:
        staff_branch_id = StaffBillingService._normalize_branch_id(staff.branch_id)
        return (
            db.query(Transaction)
            .filter(
                Transaction.business_id == staff.business_id,
                Transaction.branch_id == staff_branch_id,
                Transaction.source_app == STAFF_SOURCE_APP,
            )
            .order_by(Transaction.created_at.desc())
            .limit(200)
            .all()
        )

    @staticmethod
    def create_kot(db: Session, staff: StaffProfile, payload: StaffKotCreate) -> StaffKot:
        StaffBillingService._ensure_staff_billing_allowed(staff)
        staff_branch_id = StaffBillingService._normalize_branch_id(staff.branch_id)
        feature_flags = StaffBillingService._feature_flags_for_staff(db, staff)
        permissions = StaffBillingService._permissions_for_staff(db, staff)
        if not feature_flags.get("kot") or not permissions.get("create_kot"):
            raise HTTPException(status_code=403, detail="KOT is not enabled for this staff")

        if payload.idempotency_key:
            existing = (
                db.query(StaffKot)
                .filter(
                    StaffKot.business_id == staff.business_id,
                    StaffKot.branch_id == staff_branch_id,
                    StaffKot.idempotency_key == payload.idempotency_key,
                )
                .first()
            )
            if existing:
                return existing

        kot = StaffKot(
            id=payload.id or str(uuid.uuid4()),
            business_id=staff.business_id,
            branch_id=staff_branch_id,
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
        staff_branch_id = StaffBillingService._normalize_branch_id(staff.branch_id)
        return (
            db.query(StaffKot)
            .filter(
                StaffKot.business_id == staff.business_id,
                StaffKot.branch_id == staff_branch_id,
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
            status = payload.status.strip().lower()
            if status not in KOT_STATUSES:
                raise HTTPException(status_code=400, detail="Invalid KOT status")
            if status == "cancelled":
                permissions = StaffBillingService._permissions_for_staff(db, staff)
                if not permissions.get("cancel_kot"):
                    raise HTTPException(status_code=403, detail="Staff cannot cancel KOT")
            kot.status = status
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
        principal: PrincipalContext | None = None,
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

        def mark_kot_converted(transaction: Transaction) -> None:
            kot.status = "converted"
            kot.bill_transaction_id = transaction.id
            kot.sync_status = "pending"

        return StaffBillingService.create_bill(
            db,
            staff,
            payload,
            principal=principal,
            after_create=mark_kot_converted,
        )

    @staticmethod
    def create_held_bill(
        db: Session,
        staff: StaffProfile,
        payload: StaffHeldBillCreate,
    ) -> StaffHeldBill:
        StaffBillingService._ensure_staff_billing_allowed(staff)
        staff_branch_id = StaffBillingService._normalize_branch_id(staff.branch_id)
        feature_flags = StaffBillingService._feature_flags_for_staff(db, staff)
        permissions = StaffBillingService._permissions_for_staff(db, staff)
        if not feature_flags.get("hold_bill") or not permissions.get("hold_bill"):
            raise HTTPException(status_code=403, detail="Hold bill is not enabled for this staff")

        if payload.idempotency_key:
            existing = (
                db.query(StaffHeldBill)
                .filter(
                    StaffHeldBill.business_id == staff.business_id,
                    StaffHeldBill.branch_id == staff_branch_id,
                    StaffHeldBill.idempotency_key == payload.idempotency_key,
                )
                .first()
            )
            if existing:
                return existing

        held_bill = StaffHeldBill(
            id=payload.id or str(uuid.uuid4()),
            business_id=staff.business_id,
            branch_id=staff_branch_id,
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
        staff_branch_id = StaffBillingService._normalize_branch_id(staff.branch_id)
        return (
            db.query(StaffHeldBill)
            .filter(
                StaffHeldBill.business_id == staff.business_id,
                StaffHeldBill.branch_id == staff_branch_id,
            )
            .order_by(StaffHeldBill.created_at.desc())
            .limit(200)
            .all()
        )

    @staticmethod
    def resume_held_bill(db: Session, staff: StaffProfile, held_bill_id: str) -> StaffHeldBill:
        permissions = StaffBillingService._permissions_for_staff(db, staff)
        if not permissions.get("resume_held_bill"):
            raise HTTPException(status_code=403, detail="Staff cannot resume held bills")
        held_bill = (
            db.query(StaffHeldBill)
            .filter(
                StaffHeldBill.id == held_bill_id,
                StaffHeldBill.business_id == staff.business_id,
                StaffHeldBill.branch_id == StaffBillingService._normalize_branch_id(staff.branch_id),
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
        staff_branch_id = StaffBillingService._normalize_branch_id(staff.branch_id)
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
            lock.branch_id = staff_branch_id
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
                branch_id=staff_branch_id,
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
        staff_branch_id = StaffBillingService._normalize_branch_id(staff.branch_id)
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
                StaffProcessLock.branch_id == staff_branch_id,
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
        staff_branch_id = StaffBillingService._normalize_branch_id(staff.branch_id)
        if event.business_id and event.business_id != staff.business_id:
            raise HTTPException(status_code=403, detail="Event business does not match staff")
        if (
            event.branch_id
            and StaffBillingService._normalize_branch_id(event.branch_id) != staff_branch_id
        ):
            raise HTTPException(status_code=403, detail="Event branch does not match staff")
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
            branch_id=staff_branch_id,
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
        staff_branch_id = StaffBillingService._normalize_branch_id(staff.branch_id)
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
                    StaffRealtimeEvent.branch_id == staff_branch_id,
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
        try:
            principal = resolve_principal_from_token(db, token)
        except AuthError as exc:
            raise HTTPException(status_code=401, detail="Invalid websocket token") from exc

        if principal.actor_type == ActorType.WORKER and principal.staff_id:
            staff = db.query(StaffProfile).filter(StaffProfile.id == principal.staff_id).first()
            return {
                "principal_type": "staff",
                "principal_id": staff.id,
                "business_id": staff.business_id,
                "branch_id": staff.branch_id,
                "staff": staff,
            }

        user = db.query(User).filter(User.id == principal.user_id).first()
        if not user:
            raise HTTPException(status_code=401, detail="Invalid websocket token")
        return {
            "principal_type": "admin",
            "principal_id": user.id,
            "business_id": user.business_id,
            "branch_id": principal.branch_id or "main",
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
    def _ensure_staff_billing_allowed(staff: StaffProfile) -> None:
        allowed_apps = safe_json_loads(staff.allowed_apps, [STAFF_SOURCE_APP])
        if STAFF_SOURCE_APP not in allowed_apps:
            raise HTTPException(
                status_code=403,
                detail="Staff billing app access is not enabled for this staff",
            )

    @staticmethod
    def _normalize_branch_id(branch_id: Optional[str]) -> str:
        branch = (branch_id or "main").strip()
        return branch or "main"

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
    def _principal_for_staff(db: Session, staff: StaffProfile) -> PrincipalContext:
        feature_flags = StaffBillingService._feature_flags_for_staff(db, staff)
        permission_map = StaffBillingService._permissions_for_staff(db, staff)
        return PrincipalContext(
            principal_id=staff.id,
            actor_type=ActorType.WORKER,
            business_id=staff.business_id,
            branch_id=StaffBillingService._normalize_branch_id(staff.branch_id),
            staff_id=staff.id,
            membership_id=staff.id,
            role=staff.role,
            permissions=permissions_from_legacy_map(permission_map),
            capabilities=frozenset(key for key, enabled in feature_flags.items() if enabled),
        )

    @staticmethod
    def _validate_bill_payload(payload: StaffBillCreate, permissions: Dict[str, Any]) -> None:
        if not payload.items and not payload.items_json:
            raise HTTPException(status_code=400, detail="Cart is empty")
        amounts = [
            payload.cash_amount or 0.0,
            payload.upi_amount or 0.0,
            payload.card_amount or 0.0,
            payload.other_paid_amount or 0.0,
            payload.credit_amount or 0.0,
            payload.discount or 0.0,
        ]
        if any(amount < 0 for amount in amounts):
            raise HTTPException(status_code=400, detail="Paid amount cannot be negative")
        if payload.discount > payload.subtotal and not permissions.get("allow_discount_above_subtotal"):
            raise HTTPException(status_code=400, detail="Discount cannot exceed subtotal")
        if payload.credit_amount > 0:
            if not permissions.get("credit_sale"):
                raise HTTPException(status_code=403, detail="Credit sale is not enabled for this staff")
            if not payload.customer_id:
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
                .with_for_update()
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
                    branch_id=StaffBillingService._normalize_branch_id(staff.branch_id),
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
            branch_id=StaffBillingService._normalize_branch_id(staff.branch_id),
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
    def _apply_customer_credit(
        db: Session,
        staff: StaffProfile,
        payload: StaffBillCreate,
    ) -> None:
        credit_amount = payload.credit_amount or 0.0
        if credit_amount <= 0:
            return
        customer = (
            db.query(Customer)
            .filter(
                Customer.id == payload.customer_id,
                Customer.business_id == staff.business_id,
                Customer.is_deleted == False,
            )
            .with_for_update()
            .first()
        )
        if not customer:
            raise HTTPException(status_code=404, detail="Credit customer not found")
        customer.balance_remaining = (customer.balance_remaining or 0.0) + credit_amount

    @staticmethod
    def _get_kot(db: Session, staff: StaffProfile, kot_id: str) -> StaffKot:
        kot = (
            db.query(StaffKot)
            .filter(
                StaffKot.id == kot_id,
                StaffKot.business_id == staff.business_id,
                StaffKot.branch_id == StaffBillingService._normalize_branch_id(staff.branch_id),
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
                StaffProcessLock.branch_id == StaffBillingService._normalize_branch_id(staff.branch_id),
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
