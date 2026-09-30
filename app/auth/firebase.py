from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException

from core.config import settings


@dataclass(frozen=True)
class VerifiedFirebaseIdentity:
    uid: str
    email: str | None = None
    display_name: str | None = None
    phone_number: str | None = None
    provider: str | None = None


def _firebase_app():
    """Return a configured Firebase Admin app or fail closed.

    Firebase Admin performs signature, issuer, audience/project and expiration
    validation in ``verify_id_token``. This function deliberately has no UID
    or unverified-claims fallback, and is small enough to mock in tests.
    """
    if not settings.FIREBASE_PROJECT_ID and not settings.FIREBASE_CREDENTIALS_PATH:
        raise HTTPException(status_code=503, detail="Firebase authentication is not configured")
    try:
        import firebase_admin
        from firebase_admin import credentials
    except ImportError as exc:  # pragma: no cover - packaging failure
        raise HTTPException(status_code=503, detail="Firebase authentication is unavailable") from exc

    try:
        return firebase_admin.get_app()
    except ValueError:
        options: dict[str, str] = {}
        credential = None
        if settings.FIREBASE_PROJECT_ID:
            options["projectId"] = settings.FIREBASE_PROJECT_ID
        if settings.FIREBASE_CREDENTIALS_PATH:
            credential = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
        return firebase_admin.initialize_app(credential, options or None)


def verify_firebase_id_token(id_token: str) -> VerifiedFirebaseIdentity:
    if not id_token or not id_token.strip():
        raise HTTPException(status_code=401, detail="Firebase ID token is required")
    try:
        from firebase_admin import auth

        claims: dict[str, Any] = auth.verify_id_token(
            id_token,
            app=_firebase_app(),
            check_revoked=settings.FIREBASE_CHECK_REVOKED,
        )
    except HTTPException:
        raise
    except Exception as exc:
        # Deliberately do not include a token or verifier details in the response.
        raise HTTPException(status_code=401, detail="Firebase ID token is invalid") from exc

    uid = str(claims.get("uid") or claims.get("sub") or "").strip()
    if not uid:
        raise HTTPException(status_code=401, detail="Firebase ID token is invalid")
    firebase_claims = claims.get("firebase") or {}
    return VerifiedFirebaseIdentity(
        uid=uid,
        email=claims.get("email"),
        display_name=claims.get("name"),
        phone_number=claims.get("phone_number"),
        provider=firebase_claims.get("sign_in_provider") if isinstance(firebase_claims, dict) else None,
    )
