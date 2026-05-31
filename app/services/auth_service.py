import uuid

from fastapi import HTTPException

from auth.security import hash_password, verify_password, create_access_token
from models.business_model import Business
from models.user_model import User
from repositories.user_repository import UserRepository


class AuthService:

    @staticmethod
    def signup(db, payload):
        existing_user = UserRepository.get_by_email(db, payload.email)
        if existing_user:
            raise HTTPException(status_code=400, detail="User already exists")

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

        token = create_access_token({
            "sub": user.id,
            "business_id": business.id
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
            raise HTTPException(status_code=401, detail="Invalid credentials")

        business = db.query(Business).filter(Business.id == user.business_id).first()

        token = create_access_token({
            "sub": user.id,
            "business_id": user.business_id
        })

        return {
            "access_token": token,
            "token_type": "bearer",
            "business_id": user.business_id,
            "business_name": business.name if business else ""
        }
