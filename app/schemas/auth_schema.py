from pydantic import BaseModel, ConfigDict
from pydantic import EmailStr
from typing import Optional


class SignupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    password: str
    business_name: str
    business_type: str
    gst_number: Optional[str] = None


class TokenResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    access_token: str
    token_type: str
    business_id: Optional[str] = None
    business_name: Optional[str] = None
