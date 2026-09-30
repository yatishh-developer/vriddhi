from datetime import timedelta

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from auth.authorization import (
    require_branch_access,
    require_business_access,
    require_permission,
)
from auth.dependencies import resolve_principal_from_token
from auth.errors import AuthError
from auth.firebase import VerifiedFirebaseIdentity
from auth.principal import ActorType
from auth.security import create_access_token
from auth.sessions import issue_session_tokens, revoke_session, utc_now
from core.config import settings
from database.database import Base
from models.auth_session_model import AuthSession
from models.business_model import Business
from models.staff_billing_model import StaffInvite, StaffProfile
from models.user_model import User
from schemas.staff_billing_schema import (
    StaffFirebaseInviteAcceptRequest,
    StaffFirebaseLoginRequest,
)
from services.staff_billing_service import StaffBillingService, hash_invite_code


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    business = Business(id="business-a", name="Cafe", business_type="Restaurant")
    owner = User(
        id="owner-a",
        business_id=business.id,
        email="owner@example.com",
        password_hash="hash",
    )
    worker = StaffProfile(
        id="worker-a",
        business_id=business.id,
        branch_id="branch-a",
        staff_name="Counter",
        role="cashier",
        permissions_json='{"create_bill": true}',
        allowed_apps='["staff_billing_app"]',
        status="active",
        created_by=owner.id,
    )
    session.add_all([business, owner, worker])
    session.commit()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _owner_tokens(db):
    access, refresh, _ = issue_session_tokens(
        db,
        actor_type=ActorType.OWNER,
        principal_id="owner-a",
        business_id="business-a",
        user_id="owner-a",
    )
    db.commit()
    return access, refresh


def _worker_tokens(db):
    access, refresh, _ = issue_session_tokens(
        db,
        actor_type=ActorType.WORKER,
        principal_id="worker-a",
        business_id="business-a",
        staff_id="worker-a",
        branch_id="branch-a",
        device_id="device-a",
    )
    db.commit()
    return access, refresh


def test_valid_admin_token_resolves_principal_context(db):
    access, _ = _owner_tokens(db)
    principal = resolve_principal_from_token(db, access)
    assert principal.actor_type == ActorType.OWNER
    assert principal.user_id == "owner-a"
    assert principal.business_id == "business-a"
    assert "*" in principal.permissions


def test_valid_worker_token_resolves_principal_context(db):
    access, _ = _worker_tokens(db)
    principal = resolve_principal_from_token(db, access)
    assert principal.actor_type == ActorType.WORKER
    assert principal.staff_id == "worker-a"
    assert principal.branch_id == "branch-a"
    assert "create_bill" in principal.permissions


def test_invalid_and_expired_jwts_are_rejected(db):
    with pytest.raises(AuthError) as invalid:
        resolve_principal_from_token(db, "not-a-jwt")
    assert invalid.value.code == "TOKEN_INVALID"

    expired = create_access_token(
        {"sub": "owner-a", "business_id": "business-a", "actor_type": "OWNER"},
        expires_minutes=-1,
    )
    with pytest.raises(AuthError) as expired_error:
        resolve_principal_from_token(db, expired)
    assert expired_error.value.code == "TOKEN_EXPIRED"


def test_disabled_worker_and_revoked_session_are_rejected(db):
    access, _ = _worker_tokens(db)
    db.query(StaffProfile).filter(StaffProfile.id == "worker-a").update({"status": "disabled"})
    db.commit()
    with pytest.raises(AuthError) as disabled:
        resolve_principal_from_token(db, access)
    assert disabled.value.code == "ACCOUNT_DISABLED"

    db.query(StaffProfile).filter(StaffProfile.id == "worker-a").update({"status": "active"})
    db.commit()
    access, _ = _worker_tokens(db)
    session_id = jwt.decode(access, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])["session_id"]
    session = db.query(AuthSession).filter(AuthSession.id == session_id).first()
    revoke_session(db, session)
    db.commit()
    with pytest.raises(AuthError) as revoked:
        resolve_principal_from_token(db, access)
    assert revoked.value.code == "SESSION_REVOKED"


def test_business_branch_and_permission_helpers(db):
    worker_access, _ = _worker_tokens(db)
    worker = resolve_principal_from_token(db, worker_access)
    with pytest.raises(AuthError) as business_error:
        require_business_access(worker, "business-b")
    assert business_error.value.code == "BUSINESS_ACCESS_DENIED"
    with pytest.raises(AuthError) as branch_error:
        require_branch_access(worker, "branch-b")
    assert branch_error.value.code == "BRANCH_ACCESS_DENIED"
    with pytest.raises(AuthError) as permission_error:
        require_permission(worker, "tables.open")
    assert permission_error.value.code == "PERMISSION_DENIED"

    owner_access, _ = _owner_tokens(db)
    owner = resolve_principal_from_token(db, owner_access)
    assert require_permission(owner, "anything") == owner
    assert require_branch_access(owner, "branch-b") == owner


def test_firebase_login_uses_verified_identity_only(db, monkeypatch):
    staff = db.query(StaffProfile).filter(StaffProfile.id == "worker-a").first()
    staff.firebase_uid = "verified-uid"
    db.commit()
    monkeypatch.setattr(
        "services.staff_billing_service.verify_firebase_id_token",
        lambda _token: VerifiedFirebaseIdentity(uid="verified-uid", email="staff@example.com"),
    )
    response = StaffBillingService.firebase_login(db, StaffFirebaseLoginRequest(id_token="verified-token"))
    assert response["staff_id"] == "worker-a"

    def _reject_missing_token(_token):
        raise HTTPException(status_code=401, detail="invalid")

    monkeypatch.setattr("services.staff_billing_service.verify_firebase_id_token", _reject_missing_token)
    with pytest.raises(AuthError) as forged_uid:
        StaffBillingService.firebase_login(
            db,
            StaffFirebaseLoginRequest(uid="verified-uid", id_token=None),
        )
    assert forged_uid.value.code == "FIREBASE_TOKEN_INVALID"


def test_unverified_firebase_claims_are_not_accepted(db, monkeypatch):
    forged = jwt.encode({"sub": "worker-a"}, "attacker", algorithm="HS256")
    def _reject_unverified(_token):
        raise HTTPException(status_code=401, detail="invalid signature")

    monkeypatch.setattr("services.staff_billing_service.verify_firebase_id_token", _reject_unverified)
    with pytest.raises(AuthError) as error:
        StaffBillingService.firebase_login(db, StaffFirebaseLoginRequest(id_token=forged))
    assert error.value.code == "FIREBASE_TOKEN_INVALID"


def test_expired_revoked_and_duplicate_firebase_invite_acceptance(db, monkeypatch):
    now = utc_now()
    expired = StaffInvite(
        id="invite-expired",
        business_id="business-a",
        branch_id="branch-a",
        staff_name="Expired",
        invite_code_hash=hash_invite_code("111111"),
        expires_at=now - timedelta(seconds=1),
        status="active",
        created_by="owner-a",
    )
    revoked = StaffInvite(
        id="invite-revoked",
        business_id="business-a",
        branch_id="branch-a",
        staff_name="Revoked",
        invite_code_hash=hash_invite_code("222222"),
        expires_at=now + timedelta(minutes=5),
        status="revoked",
        created_by="owner-a",
    )
    accepted = StaffInvite(
        id="invite-accepted",
        business_id="business-a",
        branch_id="branch-a",
        staff_name="Accepted",
        invite_code_hash=hash_invite_code("333333"),
        expires_at=now + timedelta(minutes=5),
        status="active",
        created_by="owner-a",
    )
    db.add_all([expired, revoked, accepted])
    db.commit()

    with pytest.raises(AuthError) as expired_error:
        StaffBillingService.verify_invite_code(db, "111111")
    assert expired_error.value.code == "INVITE_EXPIRED"
    with pytest.raises(AuthError) as revoked_error:
        StaffBillingService.verify_invite_code(db, "222222")
    assert revoked_error.value.code == "INVITE_INVALID"

    monkeypatch.setattr(
        "services.staff_billing_service.verify_firebase_id_token",
        lambda _token: VerifiedFirebaseIdentity(uid="new-verified-uid"),
    )
    payload = StaffFirebaseInviteAcceptRequest(id_token="verified", invite_code="333333")
    first = StaffBillingService.accept_firebase_invite(db, payload)
    second = StaffBillingService.accept_firebase_invite(db, payload)
    assert first["staff_id"] == second["staff_id"]
    assert db.query(StaffProfile).filter(StaffProfile.firebase_uid == "new-verified-uid").count() == 1


def test_refresh_rejects_revoked_sessions_and_access_tokens(db):
    access, refresh = _worker_tokens(db)
    with pytest.raises(AuthError):
        resolve_principal_from_token(db, access, required_token_type="refresh")
    session = db.query(AuthSession).order_by(AuthSession.created_at.desc()).first()
    revoke_session(db, session)
    db.commit()
    with pytest.raises(AuthError) as revoked:
        resolve_principal_from_token(db, refresh, required_token_type="refresh")
    assert revoked.value.code == "SESSION_REVOKED"


def test_request_id_and_safe_auth_error_response():
    from main import app

    with TestClient(app) as client:
        response = client.get("/products/", headers={"X-Request-ID": "audit-request-1"})
    assert response.status_code == 401
    assert response.headers["X-Request-ID"] == "audit-request-1"
    body = response.json()
    assert body["error"]["code"] == "TOKEN_MISSING"
    assert body["error"]["request_id"] == "audit-request-1"
    assert "audit-request-1" not in body["error"]["message"]

    with TestClient(app) as client:
        firebase_error = client.post(
            "/staff/auth/firebase-login",
            json={"id_token": "sensitive-firebase-token"},
        )
    assert firebase_error.status_code == 503
    assert firebase_error.json()["error"]["code"] == "FIREBASE_NOT_CONFIGURED"
    assert "sensitive-firebase-token" not in firebase_error.text


def test_auth_request_schemas_forbid_unknown_fields():
    with pytest.raises(Exception):
        StaffFirebaseLoginRequest(id_token="token", unexpected="value")
