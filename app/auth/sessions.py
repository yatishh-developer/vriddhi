import hashlib
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from auth.principal import ActorType
from auth.security import create_access_token, create_refresh_token
from core.config import settings
from models.auth_session_model import AuthSession


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def hash_refresh_jti(jti: str) -> str:
    return hashlib.sha256(f"{jti}:{settings.JWT_SECRET}".encode("utf-8")).hexdigest()


def create_session(
    db,
    *,
    actor_type: ActorType,
    business_id: str,
    user_id: str | None = None,
    staff_id: str | None = None,
    device_id: str | None = None,
    refresh_jti: str | None = None,
) -> AuthSession:
    now = utc_now()
    session = AuthSession(
        id=str(uuid4()),
        actor_type=actor_type.value,
        user_id=user_id,
        staff_id=staff_id,
        business_id=business_id,
        device_id=device_id,
        refresh_token_hash=hash_refresh_jti(refresh_jti) if refresh_jti else None,
        status="ACTIVE",
        last_seen_at=now,
        expires_at=now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    db.add(session)
    return session


def issue_session_tokens(db, *, actor_type: ActorType, principal_id: str, business_id: str,
                         user_id: str | None = None, staff_id: str | None = None,
                         branch_id: str | None = None, device_id: str | None = None) -> tuple[str, str, AuthSession]:
    refresh_jti = str(uuid4())
    session = create_session(
        db,
        actor_type=actor_type,
        business_id=business_id,
        user_id=user_id,
        staff_id=staff_id,
        device_id=device_id,
        refresh_jti=refresh_jti,
    )
    db.flush()
    claims = {
        "sub": principal_id,
        "actor_type": actor_type.value,
        "business_id": business_id,
        "branch_id": branch_id,
        "session_id": session.id,
        "device_id": device_id,
    }
    access_token = create_access_token({**claims, "token_type": "access"})
    refresh_token = create_refresh_token({**claims, "jti": refresh_jti})
    return access_token, refresh_token, session


def revoke_session(db, session: AuthSession) -> None:
    session.status = "REVOKED"
    session.revoked_at = utc_now()
    session.last_seen_at = session.revoked_at


def refresh_jti_is_valid(session: AuthSession, jti: str | None) -> bool:
    return bool(jti and session.refresh_token_hash and hash_refresh_jti(jti) == session.refresh_token_hash)
