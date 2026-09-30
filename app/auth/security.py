import bcrypt
from jose import jwt
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from core.config import settings


def hash_password(password: str) -> str:
    """Hash a plain-text password using bcrypt."""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against a bcrypt hash."""
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


def create_access_token(data: dict[str, Any], expires_minutes: int | None = None) -> str:
    """Create a JWT access token with normalized temporal and jti claims."""
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    expire = now + timedelta(
        minutes=expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    to_encode.update({"iat": now, "exp": expire, "jti": to_encode.get("jti") or str(uuid4())})
    return jwt.encode(
        to_encode,
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )


def create_refresh_token(data: dict[str, Any], expires_days: int | None = None) -> str:
    """Create a refresh token; callers must supply/retain its session id."""
    return create_access_token(
        {**data, "token_type": "refresh"},
        expires_minutes=(expires_days or settings.REFRESH_TOKEN_EXPIRE_DAYS) * 24 * 60,
    )
