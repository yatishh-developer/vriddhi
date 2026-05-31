from fastapi import APIRouter
from fastapi import Depends
from fastapi.security import OAuth2PasswordRequestForm

from sqlalchemy.orm import Session

from database.dependencies import get_db

from schemas.auth_schema import SignupRequest
from schemas.auth_schema import TokenResponse

from services.auth_service import AuthService


router = APIRouter(
    prefix="/auth",
    tags=["Auth"]
)


@router.post(
    "/signup",
    response_model=TokenResponse
)
def signup(
    payload: SignupRequest,
    db: Session = Depends(get_db)
):

    return AuthService.signup(
        db,
        payload
    )


@router.post(
    "/login"
)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):

    return AuthService.login(
        db,
        form_data.username,
        form_data.password
    )