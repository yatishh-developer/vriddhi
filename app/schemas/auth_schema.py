from pydantic import BaseModel
from pydantic import EmailStr
from typing import Optional


class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    business_name: str
    business_type: str
    gst_number: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    business_id: Optional[str] = None
    business_name: Optional[str] = None
