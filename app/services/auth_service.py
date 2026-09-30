import uuid

from auth.errors import AuthError

from auth.principal import ActorType
from auth.security import hash_password, verify_password, create_access_token
from auth.sessions import create_session
from models.business_model import Business
from models.user_model import User
from repositories.user_repository import UserRepository


class AuthService:

    @staticmethod
    def signup(db, payload):
        existing_user = UserRepository.get_by_email(db, payload.email)
        if existing_user:
            raise AuthError(400, "SIGNUP_INVALID", "Unable to create this account.")

        business = Business(
            id=str(uuid.uuid4()),
            name=payload.business_name,
            business_type=payload.business_type,
            gst_number=payload.gst_number
        )
        db.add(business)
        db.flush()

        user = User(
            id=str(uuid.uuid4()),
            business_id=business.id,
            email=payload.email,
            password_hash=hash_password(payload.password)
        )
        db.add(user)
        db.commit()

        session = create_session(
            db,
            actor_type=ActorType.OWNER,
            business_id=business.id,
            user_id=user.id,
        )
        db.commit()
        token = create_access_token({
            "sub": user.id,
            "actor_type": ActorType.OWNER.value,
            "business_id": business.id,
            "session_id": session.id,
            "token_type": "access",
        })

        return {
            "access_token": token,
            "token_type": "bearer",
            "business_id": business.id,
            "business_name": business.name
        }

    @staticmethod
    def login(db, email, password):
        user = UserRepository.get_by_email(db, email)
        if not user or not verify_password(password, user.password_hash):
            raise AuthError(401, "TOKEN_INVALID", "Invalid email or password.")

        business = db.query(Business).filter(Business.id == user.business_id).first()

        session = create_session(
            db,
            actor_type=ActorType.OWNER,
            business_id=user.business_id,
            user_id=user.id,
        )
        db.commit()
        token = create_access_token({
            "sub": user.id,
            "actor_type": ActorType.OWNER.value,
            "business_id": user.business_id,
            "session_id": session.id,
            "token_type": "access",
        })

        return {
            "access_token": token,
            "token_type": "bearer",
            "business_id": user.business_id,
            "business_name": business.name if business else ""
        }
