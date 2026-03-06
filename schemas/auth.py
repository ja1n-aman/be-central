import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class GoogleAuthRequest(BaseModel):
    id_token: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserOut"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    email: str
    google_id: str
    created_at: datetime


# Resolve forward reference
AuthResponse.model_rebuild()
