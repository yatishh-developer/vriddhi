from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, OAuth2PasswordBearer
from jose import ExpiredSignatureError, JWTError, jwt
from sqlalchemy.orm import Session

from auth.authorization import permissions_from_legacy_map
from auth.errors import AuthError
from auth.principal import ActorType, PrincipalContext
from auth.sessions import refresh_jti_is_valid, utc_now
from core.config import settings
from database.dependencies import get_db
from models.auth_session_model import AuthSession
from models.business_model import Business
from models.staff_billing_model import StaffProfile
from models.user_model import User


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
bearer_scheme = HTTPBearer(auto_error=False)


def _decode_jwt(token: str) -> dict[str, Any]:
    if not token:
        raise AuthError(401, "TOKEN_MISSING", "Authentication token is required.")
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except ExpiredSignatureError as exc:
        raise AuthError(401, "TOKEN_EXPIRED", "Authentication token has expired.") from exc
    except JWTError as exc:
        raise AuthError(401, "TOKEN_INVALID", "Authentication token is invalid.") from exc


def _normalise_actor_type(payload: dict[str, Any]) -> ActorType:
    raw = str(payload.get("actor_type") or "").upper()
    if raw in {member.value for member in ActorType}:
        return ActorType(raw)
    # Legacy staff tokens use `role: staff`; old owner tokens omit actor type.
    if str(payload.get("role") or "").lower() == "staff":
        return ActorType.WORKER
    return ActorType.OWNER


def _session_for_payload(
    db: Session,
    payload: dict[str, Any],
    actor_type: ActorType,
    required_token_type: Literal["access", "refresh"],
) -> AuthSession | None:
    token_type = payload.get("token_type")
    if token_type is not None and token_type != required_token_type:
        raise AuthError(401, "TOKEN_INVALID", "Authentication token has the wrong token type.")
    # Old tokens have neither a session id nor token type. They remain usable
    # during migration, but cannot be explicitly revoked.
    session_id = payload.get("session_id")
    if not session_id:
        return None
    session = db.query(AuthSession).filter(AuthSession.id == session_id).first()
    if not session or session.status != "ACTIVE":
        raise AuthError(401, "SESSION_REVOKED", "Authentication session is no longer active.")
    expires_at = session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= utc_now():
        raise AuthError(401, "SESSION_REVOKED", "Authentication session has expired.")
    if session.actor_type != actor_type.value or session.business_id != payload.get("business_id"):
        raise AuthError(401, "TOKEN_INVALID", "Authentication token is invalid.")
    if required_token_type == "refresh" and not refresh_jti_is_valid(session, payload.get("jti")):
        raise AuthError(401, "SESSION_REVOKED", "Refresh token is no longer active.")
    session.last_seen_at = datetime.now(timezone.utc)
    return session


def resolve_principal_from_token(
    db: Session,
    token: str,
    required_token_type: Literal["access", "refresh"] = "access",
) -> PrincipalContext:
    """Decode once, validate session state, then resolve current DB identity."""
    payload = _decode_jwt(token)
    actor_type = _normalise_actor_type(payload)
    session = _session_for_payload(db, payload, actor_type, required_token_type)
    principal_id = str(payload.get("sub") or "")
    business_id = str(payload.get("business_id") or "")
    if not principal_id or not business_id:
        raise AuthError(401, "TOKEN_INVALID", "Authentication token is invalid.")

    if actor_type == ActorType.WORKER:
        staff = db.query(StaffProfile).filter(StaffProfile.id == principal_id).first()
        if not staff or staff.status != "active":
            raise AuthError(401, "ACCOUNT_DISABLED", "Worker account is disabled or unavailable.")
        if staff.business_id != business_id or (session and session.staff_id != staff.id):
            raise AuthError(401, "TOKEN_INVALID", "Authentication token is invalid.")
        from services.staff_billing_service import STAFF_SOURCE_APP, StaffBillingService, safe_json_loads

        allowed_apps = safe_json_loads(staff.allowed_apps, [STAFF_SOURCE_APP])
        if STAFF_SOURCE_APP not in allowed_apps:
            raise AuthError(403, "ACCOUNT_DISABLED", "Worker billing access is disabled.")
        feature_flags = StaffBillingService._feature_flags_for_staff(db, staff)
        permissions_map = {
            **StaffBillingService.default_permissions_for_staff(feature_flags),
            **safe_json_loads(staff.permissions_json, {}),
        }
        return PrincipalContext(
            principal_id=staff.id,
            actor_type=actor_type,
            business_id=staff.business_id,
            branch_id=staff.branch_id or "main",
            staff_id=staff.id,
            membership_id=staff.id,
            role=staff.role,
            permissions=permissions_from_legacy_map(permissions_map),
            capabilities=frozenset(key for key, value in feature_flags.items() if value is True),
            device_id=payload.get("device_id"),
            session_id=session.id if session else None,
            token_jti=payload.get("jti"),
        )

    user = db.query(User).filter(User.id == principal_id).first()
    if not user or user.business_id != business_id or (session and session.user_id != user.id):
        raise AuthError(401, "TOKEN_INVALID", "Authentication token is invalid.")
    if not db.query(Business).filter(Business.id == business_id).first():
        raise AuthError(401, "ACCOUNT_DISABLED", "Business account is unavailable.")
    return PrincipalContext(
        principal_id=user.id,
        actor_type=actor_type,
        business_id=user.business_id,
        user_id=user.id,
        role="owner" if actor_type == ActorType.OWNER else "admin",
        permissions=frozenset({"*"}),
        capabilities=frozenset({"*"}),
        device_id=payload.get("device_id"),
        session_id=session.id if session else None,
        token_jti=payload.get("jti"),
    )


def get_principal_context(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> PrincipalContext:
    return resolve_principal_from_token(db, credentials.credentials if credentials else "")


def get_current_user(
    principal: PrincipalContext = Depends(get_principal_context),
    db: Session = Depends(get_db),
) -> User:
    if principal.actor_type == ActorType.WORKER or not principal.user_id:
        raise AuthError(403, "PERMISSION_DENIED", "Owner access is required.")
    return db.query(User).filter(User.id == principal.user_id).first()


def get_current_staff(
    principal: PrincipalContext = Depends(get_principal_context),
    db: Session = Depends(get_db),
) -> StaffProfile:
    if principal.actor_type != ActorType.WORKER or not principal.staff_id:
        raise AuthError(403, "PERMISSION_DENIED", "Worker access is required.")
    return db.query(StaffProfile).filter(StaffProfile.id == principal.staff_id).first()
