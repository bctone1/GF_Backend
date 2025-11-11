# schemas/auth.py
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, EmailStr

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class SupervisorLoginRequest(BaseModel):
    email: EmailStr
    password: str


class SupervisorSignupRequest(BaseModel):
    email: EmailStr
    password: str
    name: str
    organization_id: Optional[int] = None

class SupervisorSignupResponse(BaseModel):
    supervisor_user_id: int
    organization_id: int
    email: EmailStr
    name: str
    role: str
    status: str
