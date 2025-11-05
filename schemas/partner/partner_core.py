# schemas/partner/partner_core.py
from __future__ import annotations
from typing import Optional
from datetime import datetime
from pydantic import EmailStr
from schemas.base import ORMBase


# ========== partner.partners ==========
class PartnerCreate(ORMBase):
    name: str
    code: str
    status: str = "active"
    timezone: str = "UTC"


class PartnerUpdate(ORMBase):
    name: Optional[str] = None
    code: Optional[str] = None
    status: Optional[str] = None
    timezone: Optional[str] = None


class PartnerResponse(ORMBase):
    id: int
    name: str
    code: str
    status: str
    timezone: str
    created_at: datetime
    updated_at: datetime


# ========== partner.partner_users ==========
class PartnerUserCreate(ORMBase):
    partner_id: int
    user_id: Optional[int] = None  # supervisor.users.user_id
    full_name: str
    email: EmailStr
    phone: Optional[str] = None
    role: str = "partner_admin"
    is_active: bool = True
    last_login_at: Optional[datetime] = None


class PartnerUserUpdate(ORMBase):
    user_id: Optional[int] = None
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    last_login_at: Optional[datetime] = None


class PartnerUserResponse(ORMBase):
    id: int
    partner_id: int
    user_id: Optional[int] = None
    full_name: str
    email: EmailStr
    phone: Optional[str] = None
    role: str
    is_active: bool
    last_login_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
